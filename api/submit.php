<?php
declare(strict_types=1);

/**
 * ЖК Lakeview — universal lead form handler.
 *
 * Handles 5 form types (callback, apartment, catalog, commercial, footer) from 6 forms
 * on the page — `form_place` tells the two `commercial` forms apart.
 * Validates honeypot, time-trap, origin, fields. Rate-limits per IP.
 * Delivers via Telegram Bot API. Logs to /logs/submissions.log.
 *
 * @see /api/config.example.php for config schema
 */

// ─── Hard error suppression for client (errors go to log only) ───────────────
ini_set('display_errors', '0');
ini_set('log_errors', '1');
error_reporting(E_ALL);

// ─── Load config ─────────────────────────────────────────────────────────────
$configPath = __DIR__ . '/config.php';
if (!is_file($configPath)) {
    http_response_code(500);
    error_log('[lakeview/submit] Missing config.php');
    echo json_encode(['ok' => false, 'error' => 'Помилка конфігурації сервера']);
    exit;
}
$CONF = require $configPath;

// ─── Setup paths ─────────────────────────────────────────────────────────────
$LOG_DIR  = __DIR__ . '/../logs';
$LOG_FILE = $LOG_DIR . '/submissions.log';
$RATE_DIR = $LOG_DIR . '/rate';

if (!is_dir($LOG_DIR))  { @mkdir($LOG_DIR,  0775, true); }
if (!is_dir($RATE_DIR)) { @mkdir($RATE_DIR, 0775, true); }

ini_set('error_log', $LOG_DIR . '/php-errors.log');

// ─── Helpers ─────────────────────────────────────────────────────────────────
/** Strip and normalize for safe HTML inclusion in Telegram messages. */
function safe_html(string $s): string {
    return htmlspecialchars(trim($s), ENT_QUOTES | ENT_HTML5, 'UTF-8');
}

/**
 * Get client IP. Origin server is NOT behind Cloudflare — proxy headers (CF-Connecting-IP,
 * X-Forwarded-For, X-Real-IP) are user-controllable and would let an attacker rotate
 * "IPs" by header to bypass the per-IP rate limit. Use only the real socket peer.
 */
function client_ip(): string {
    return $_SERVER['REMOTE_ADDR'] ?? '0.0.0.0';
}

/** Append a structured line to /logs/submissions.log. */
function log_submission(string $logFile, string $ip, string $form, string $name, string $phone, string $result): void {
    $line = sprintf(
        "%s | %s | %s | %s | %s | %s\n",
        gmdate('Y-m-d\TH:i:s\Z'),
        $ip,
        $form,
        str_replace(['|', "\n", "\r"], ' ', $name),
        str_replace(['|', "\n", "\r"], ' ', $phone),
        $result
    );
    @file_put_contents($logFile, $line, FILE_APPEND | LOCK_EX);
}

/** AJAX detection — JSON request or X-Requested-With header. */
function is_ajax(): bool {
    $accept = $_SERVER['HTTP_ACCEPT'] ?? '';
    $xrw    = $_SERVER['HTTP_X_REQUESTED_WITH'] ?? '';
    return stripos($accept, 'application/json') !== false
        || strcasecmp($xrw, 'XMLHttpRequest') === 0;
}

/**
 * Send JSON response or 303 redirect, then exit.
 * $extra is merged into a successful JSON payload — used for lead_id, which only a
 * real lead gets. Bot fake-successes call this without it, so the front end never
 * fires a conversion for them while the response still looks like success to the bot.
 */
function respond(int $status, bool $ok, string $message, ?string $redirect = null, array $extra = []): never {
    http_response_code($status);
    if (is_ajax()) {
        header('Content-Type: application/json; charset=utf-8');
        $payload = ['ok' => $ok];
        if ($ok && $redirect) $payload['redirect'] = $redirect;
        if ($ok) $payload += $extra;
        if (!$ok) $payload['error'] = $message;
        echo json_encode($payload, JSON_UNESCAPED_UNICODE);
    } else {
        // Non-AJAX form post → redirect
        $target = $ok && $redirect ? $redirect : '/thanks.html?error=1';
        header('Location: ' . $target, true, 303);
    }
    exit;
}

// ─── CORS / Origin validation ────────────────────────────────────────────────
$origin   = $_SERVER['HTTP_ORIGIN']  ?? '';
$referer  = $_SERVER['HTTP_REFERER'] ?? '';
$allowed  = $CONF['ALLOWED_ORIGINS'] ?? [];

if ($origin !== '') {
    if (in_array($origin, $allowed, true)) {
        header('Access-Control-Allow-Origin: ' . $origin);
        header('Vary: Origin');
        header('Access-Control-Allow-Methods: POST, OPTIONS');
        header('Access-Control-Allow-Headers: Content-Type, Accept, X-Requested-With');
    } else {
        // Origin sent but not in allowlist → reject
        respond(403, false, 'Заборонене джерело запиту');
    }
}

// Preflight
if (($_SERVER['REQUEST_METHOD'] ?? '') === 'OPTIONS') {
    http_response_code(204);
    exit;
}

// Only POST
if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    respond(405, false, 'Метод не підтримується');
}

// Require at least one of Origin/Referer (and matching). Empty-both is a curl/VPS bypass.
if ($origin === '' && $referer === '') {
    log_submission($LOG_FILE, client_ip(), '?', '?', '?', 'reject:no-origin-no-referer');
    respond(403, false, 'Заборонене джерело запиту');
}
if ($origin === '' && $referer !== '') {
    $refOk = false;
    foreach ($allowed as $a) {
        if (stripos($referer, $a) === 0) { $refOk = true; break; }
    }
    if (!$refOk) {
        log_submission($LOG_FILE, client_ip(), '?', '?', '?', 'reject:bad-referer');
        respond(403, false, 'Заборонене джерело запиту');
    }
}

// ─── Parse input (JSON or form-encoded) ──────────────────────────────────────
$contentType = $_SERVER['CONTENT_TYPE'] ?? '';
$input = [];

if (stripos($contentType, 'application/json') !== false) {
    $raw = file_get_contents('php://input') ?: '';
    $decoded = json_decode($raw, true);
    if (is_array($decoded)) $input = $decoded;
} else {
    $input = $_POST;
}

// Normalize all string-ish inputs. Non-strings (arrays, objects, null) coerce to default
// to prevent TypeError in strict-typed helpers like safe_html(string).
$get = static function(string $k, $default = '') use ($input) {
    $v = $input[$k] ?? $default;
    if (!is_string($v)) return is_string($default) ? $default : '';
    return trim($v);
};

// ─── Honeypot ────────────────────────────────────────────────────────────────
if ($get('website') !== '') {
    // Bot detected — fake-success silently
    log_submission($LOG_FILE, client_ip(), $get('_form', '?'), '?', '?', 'reject:honeypot');
    respond(200, true, '', '/thanks.html?form=' . urlencode($get('_form', 'fCB')));
}

// ─── Time-trap ───────────────────────────────────────────────────────────────
$tsRaw  = (string) $get('ts', '');
$tsMs   = is_numeric($tsRaw) ? (int) $tsRaw : 0;
$nowMs  = (int) (microtime(true) * 1000);
$elapsedSec = $tsMs > 0 ? max(0, ($nowMs - $tsMs) / 1000) : -1;

if ($elapsedSec < (float) ($CONF['TIME_TRAP_MIN_SECONDS'] ?? 2)
    || $elapsedSec > (float) ($CONF['TIME_TRAP_MAX_SECONDS'] ?? 86400)) {
    log_submission($LOG_FILE, client_ip(), $get('_form', '?'), '?', '?', 'reject:time-trap:' . round($elapsedSec, 1) . 's');
    // Same fake success — don't reveal logic
    respond(200, true, '', '/thanks.html?form=' . urlencode($get('_form', 'fCB')));
}

// ─── Rate-limit per IP (atomic via flock) ────────────────────────────────────
$ip      = client_ip();
$ipHash  = substr(hash('sha256', $ip . '|lakeview'), 0, 32);
$rateFile = $RATE_DIR . '/' . $ipHash . '.json';

// Open with 'c+' so the file is created if missing and we hold the descriptor across read+write.
$rateFp = @fopen($rateFile, 'c+');
if ($rateFp === false) {
    error_log('[lakeview/submit] Rate-limit: fopen failed for ' . $rateFile);
    // Fail-open is acceptable here — Telegram delivery + log still gate, and we'd rather lose anti-spam than lose leads.
    $state = ['submissions' => []];
} else {
    if (!@flock($rateFp, LOCK_EX)) {
        // Couldn't lock — fail-open with empty state, reuse fp for write later.
        $state = ['submissions' => []];
    } else {
        // Read entire current contents (we own the lock).
        $raw = '';
        while (!feof($rateFp)) { $chunk = fread($rateFp, 8192); if ($chunk === false) break; $raw .= $chunk; }
        $parsed = $raw !== '' ? json_decode($raw, true) : null;
        $state = (is_array($parsed) && isset($parsed['submissions']) && is_array($parsed['submissions']))
            ? $parsed
            : ['submissions' => []];
    }
}

$cutoff = time() - 3600;
$state['submissions'] = array_values(array_filter(
    $state['submissions'],
    static fn($t) => is_numeric($t) && (int) $t >= $cutoff
));

$limit = (int) ($CONF['RATE_LIMIT_PER_IP_PER_HOUR'] ?? 5);
if (count($state['submissions']) >= $limit) {
    if ($rateFp) { @flock($rateFp, LOCK_UN); @fclose($rateFp); }
    log_submission($LOG_FILE, $ip, $get('_form', '?'), '?', '?', 'reject:rate-limit');
    respond(429, false, 'Забагато заявок. Спробуйте через годину або зателефонуйте: +38 096 990 03 90');
}

// ─── Form-id whitelist ───────────────────────────────────────────────────────
$FORM_LABELS = [
    'callback'   => 'Замовити дзвінок',
    'apartment'  => 'Запит по квартирі',
    'catalog'    => 'Каталог планувань (PDF)',
    'commercial' => 'Комерційні приміщення',
    'footer'     => 'Швидкий контакт (футер)',
];
$THANKS_KEY = [
    'callback'   => 'fCB',
    'apartment'  => 'fApt',
    'catalog'    => 'fR',
    'commercial' => 'fC',
    'footer'     => 'fF',
];

$formId = (string) $get('_form', '');
if (!isset($FORM_LABELS[$formId])) {
    log_submission($LOG_FILE, $ip, $formId, '?', '?', 'reject:unknown-form');
    respond(400, false, 'Невідома форма');
}

// ─── Field validation ────────────────────────────────────────────────────────
$name      = (string) $get('name', '');
$phoneRaw  = (string) $get('phone', '');
$messenger = (string) $get('messenger', '');
$bizType   = (string) $get('business_type', '');
$apartment = (string) $get('apartment', ''); // hidden meta field on apt + commercial forms

// Required fields per form
$requires = [
    'callback'   => ['name', 'phone'],
    'apartment'  => ['name', 'phone'],
    'catalog'    => ['name', 'phone', 'messenger'],
    'commercial' => ['name', 'phone'],
    'footer'     => ['phone'],
];

foreach ($requires[$formId] as $req) {
    $v = (string) $get($req, '');
    if ($v === '') {
        log_submission($LOG_FILE, $ip, $formId, $name, $phoneRaw, 'reject:missing:' . $req);
        respond(400, false, 'Заповніть усі обовʼязкові поля');
    }
}

// Name validation (skip if not required for this form)
if (in_array('name', $requires[$formId], true)) {
    $nameLen = mb_strlen($name, 'UTF-8');
    if ($nameLen < 2 || $nameLen > 50) {
        log_submission($LOG_FILE, $ip, $formId, $name, $phoneRaw, 'reject:name-length');
        respond(400, false, 'Імʼя має містити від 2 до 50 символів');
    }
    if (preg_match('~https?://|<|>~i', $name)) {
        log_submission($LOG_FILE, $ip, $formId, $name, $phoneRaw, 'reject:name-suspicious');
        respond(400, false, 'Некоректне імʼя');
    }
}

// Phone — strip non-digits, must be 10–15 digits
$phoneDigits = preg_replace('~\D+~', '', $phoneRaw) ?? '';
// Normalise Ukrainian numbers to 380XXXXXXXXX regardless of how they arrived (mask,
// autofill, paste): Telegram shows a dialable number and the Meta CAPI hash matches.
if (strlen($phoneDigits) === 10 && $phoneDigits[0] === '0') {
    $phoneDigits = '38' . $phoneDigits;
} elseif (strlen($phoneDigits) === 11 && str_starts_with($phoneDigits, '80')) {
    $phoneDigits = '3' . $phoneDigits;
}
$phoneLen = strlen($phoneDigits);
if ($phoneLen < 10 || $phoneLen > 15) {
    log_submission($LOG_FILE, $ip, $formId, $name, $phoneRaw, 'reject:phone-format');
    respond(400, false, 'Некоректний номер телефону');
}
// Pretty phone: prefix + with single space chunks
$phonePretty = '+' . $phoneDigits;

// ─── Attribution (hidden fields stamped by index.html) ───────────────────────
// Fully attacker-controlled and shown to sales in Telegram + written to the pipe-
// delimited log, so: whitelist form_place, reduce UTMs to a safe charset (no newlines,
// no "://" → no forged fields or clickable links), and drop — not truncate — click ids
// that don't fit, since a truncated fbclid produces a corrupt fbc.
$FORM_PLACES = ['callback', 'apartment', 'commercial_modal', 'catalog', 'commercial_section', 'footer'];
$formPlace = (string) $get('form_place', '');
if (!in_array($formPlace, $FORM_PLACES, true)) $formPlace = '';

$attr = [];
foreach (['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'] as $k) {
    $v = (string) $get($k, '');
    $v = str_replace('://', ' ', $v);
    $v = preg_replace('~[^\p{L}\p{N} _.+\-/]~u', '_', $v) ?? '';
    $v = trim(mb_substr($v, 0, 100, 'UTF-8'));
    if ($v !== '') $attr[$k] = $v;
}
foreach (['gclid', 'gbraid', 'wbraid', 'fbclid'] as $k) {
    $v = (string) $get($k, '');
    if ($v !== '' && preg_match('~^[A-Za-z0-9._\-]{1,500}$~', $v)) $attr[$k] = $v;
}
// When the ad click was first seen (ms) — Meta wants the click time in a built fbc.
$attrTs = (string) $get('attr_ts', '');
$attrTsMs = (ctype_digit($attrTs) && (int) $attrTs <= $nowMs && (int) $attrTs > $nowMs - 90 * 86400000) ? (int) $attrTs : $nowMs;

// Minted per lead on the server — never taken from the client — so a second lead from
// the same page load (Back from thanks, another apartment) is not deduped away by Meta.
// Returned as lead_id; the browser Pixel reuses it, so Pixel ↔ CAPI dedup still holds.
$rb = random_bytes(16);
$rb[6] = chr((ord($rb[6]) & 0x0f) | 0x40);
$rb[8] = chr((ord($rb[8]) & 0x3f) | 0x80);
$eventId = vsprintf('%s%s-%s-%s-%s-%s%s%s', str_split(bin2hex($rb), 4));

// ─── Compose Telegram message ────────────────────────────────────────────────
$kyivTz = new DateTimeZone('Europe/Kyiv');
$nowKyiv = (new DateTime('now', $kyivTz))->format('Y-m-d H:i:s');

$lines = [];
$lines[] = '🆕 <b>Нова заявка з сайту</b>';
$lines[] = '';
$lines[] = '📋 <b>Форма:</b> ' . safe_html($FORM_LABELS[$formId]);
if ($name !== '')   $lines[] = '👤 <b>Імʼя:</b> ' . safe_html($name);
$lines[] = '📞 <b>Телефон:</b> <code>' . safe_html($phonePretty) . '</code>';
if ($messenger !== '') $lines[] = '💬 <b>Месенджер:</b> ' . safe_html($messenger);
if ($bizType   !== '') $lines[] = '🏢 <b>Тип бізнесу:</b> ' . safe_html($bizType);
if ($apartment !== '' && in_array($formId, ['apartment', 'commercial'], true)) {
    $label = $formId === 'commercial' ? '🏢 <b>Приміщення:</b> ' : '🏠 <b>Квартира:</b> ';
    $lines[] = $label . safe_html($apartment);
}
if ($attr) {
    $src = [];
    if (isset($attr['utm_source']))   $src[] = $attr['utm_source'] . (isset($attr['utm_medium']) ? ' / ' . $attr['utm_medium'] : '');
    if (isset($attr['utm_campaign'])) $src[] = 'кампанія: ' . $attr['utm_campaign'];
    if (isset($attr['utm_content']))  $src[] = 'оголошення: ' . $attr['utm_content'];
    if (isset($attr['utm_term']))     $src[] = 'ключ: ' . $attr['utm_term'];
    if (isset($attr['gclid']) || isset($attr['gbraid']) || isset($attr['wbraid'])) $src[] = 'клік Google Ads';
    // fbclid is also added to organic Instagram/Facebook links — it means "came from Meta", not "from an ad"
    if (isset($attr['fbclid']))       $src[] = 'перехід з Facebook/Instagram';
    // <code> keeps Telegram from turning any leftover text into a link
    $lines[] = '📣 <b>Джерело:</b> <code>' . safe_html(implode(' · ', $src)) . '</code>';
}
$lines[] = '';
$lines[] = '🌐 IP: <code>' . safe_html($ip) . '</code>';
$lines[] = '⏰ ' . safe_html($nowKyiv) . ' (Kyiv)';
if ($referer !== '') {
    $lines[] = '🔗 Сторінка: ' . safe_html(mb_substr($referer, 0, 500, 'UTF-8'));
}

$message = implode("\n", $lines);

// ─── Telegram delivery ───────────────────────────────────────────────────────
$token  = (string) ($CONF['TELEGRAM_BOT_TOKEN'] ?? '');
$chatId = (string) ($CONF['TELEGRAM_CHAT_ID']   ?? '');

if ($token === '' || $chatId === '') {
    error_log('[lakeview/submit] Missing Telegram credentials');
    log_submission($LOG_FILE, $ip, $formId, $name, $phoneRaw, 'fail:no-credentials');
    respond(500, false, 'Помилка обробки. Зателефонуйте: +38 096 990 03 90');
}

$tgUrl = 'https://api.telegram.org/bot' . $token . '/sendMessage';
$tgPayload = [
    'chat_id'    => $chatId,
    'text'       => $message,
    'parse_mode' => 'HTML',
    'disable_web_page_preview' => true,
];

$ch = curl_init($tgUrl);
curl_setopt_array($ch, [
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => http_build_query($tgPayload),
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 10,
    CURLOPT_CONNECTTIMEOUT => 5,
    CURLOPT_SSL_VERIFYPEER => true,
    CURLOPT_SSL_VERIFYHOST => 2,
    CURLOPT_HTTPHEADER     => ['Accept: application/json'],
]);
$tgResp = curl_exec($ch);
$tgCode = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
$tgErr  = curl_error($ch);
curl_close($ch);

if ($tgResp === false || $tgCode !== 200) {
    error_log(sprintf(
        '[lakeview/submit] Telegram fail: code=%d err=%s resp=%s',
        $tgCode,
        (string) $tgErr,
        is_string($tgResp) ? substr($tgResp, 0, 300) : '(none)'
    ));
    log_submission($LOG_FILE, $ip, $formId, $name, $phoneRaw, 'fail:telegram:' . $tgCode);
    respond(502, false, 'Тимчасова помилка. Зателефонуйте: +38 096 990 03 90');
}

// ─── Persist rate-limit (still holding flock from above) ────────────────────
$state['submissions'][] = time();
if ($rateFp) {
    @rewind($rateFp);
    @ftruncate($rateFp, 0);
    @fwrite($rateFp, json_encode($state));
    @fflush($rateFp);
    @flock($rateFp, LOCK_UN);
    @fclose($rateFp);
}

// ─── Success log (before CAPI, so nothing after Telegram can cost the record) ─
$srcTag = '';
if ($attr) {
    $srcRaw = ($attr['utm_source'] ?? '') . '/' . ($attr['utm_campaign'] ?? '')
        . (isset($attr['gclid']) || isset($attr['gbraid']) || isset($attr['wbraid']) ? '/gclid' : '')
        . (isset($attr['fbclid']) ? '/fbclid' : '');
    $srcTag = ' src=' . (preg_replace('~[\s|\x00-\x1F\x7F]+~u', '_', $srcRaw) ?? '');
}
log_submission($LOG_FILE, $ip, $formId . ($formPlace !== '' ? ':' . $formPlace : ''), $name, $phoneRaw, 'ok' . $srcTag);

// ─── Meta Conversions API (server-side Lead) — runs AFTER the user got the response ─
// Registered as a shutdown function: respond() below sends the JSON and exits, then this
// flushes the connection (LiteSpeed / PHP-FPM) and talks to Meta, so a slow or failing
// Graph API never delays or breaks the lead. Same event_id as the browser Pixel Lead.
$capiToken = (string) ($CONF['META_CAPI_TOKEN'] ?? '');
$pixelId   = (string) ($CONF['META_PIXEL_ID']   ?? '');
if ($capiToken !== '' && preg_match('~^\d{10,20}$~', $pixelId)) {
    register_shutdown_function(static function () use (
        $CONF, $capiToken, $pixelId, $phoneDigits, $ip, $attr, $attrTsMs, $eventId, $referer, $formId, $formPlace
    ): void {
        try {
            // Detached = the browser already has its response, so Meta may take its time.
            // Without a finish function (e.g. mod_php) the user would wait on Meta, so keep it short.
            $detached = false;
            if (function_exists('litespeed_finish_request')) {
                $detached = (bool) litespeed_finish_request();
            } elseif (function_exists('fastcgi_finish_request')) {
                $detached = fastcgi_finish_request();
            }

            $userData = [
                'ph'                => [hash('sha256', $phoneDigits)],
                'country'           => [hash('sha256', 'ua')],
                'client_ip_address' => $ip,
                'client_user_agent' => substr((string) ($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 500),
            ];
            $fbp = (string) ($_COOKIE['_fbp'] ?? '');
            $fbc = (string) ($_COOKIE['_fbc'] ?? '');
            if ($fbc === '' && isset($attr['fbclid'])) {
                $fbc = 'fb.1.' . $attrTsMs . '.' . $attr['fbclid'];
            }
            if (preg_match('~^fb\.\d\.\d+\.[A-Za-z0-9._\-]+$~', $fbp)) $userData['fbp'] = $fbp;
            if (preg_match('~^fb\.\d\.\d+\.[A-Za-z0-9._\-]+$~', $fbc)) $userData['fbc'] = $fbc;

            $capiBody = [
                'data' => [[
                    'event_name'       => 'Lead',
                    'event_time'       => time(),
                    'event_id'         => $eventId,
                    'action_source'    => 'website',
                    'event_source_url' => $referer !== '' ? mb_substr($referer, 0, 1000, 'UTF-8') : 'https://www.lakeview.com.ua/',
                    'user_data'        => $userData,
                    'custom_data'      => ['form_id' => $formId, 'form_place' => $formPlace, 'content_name' => $formPlace],
                ]],
                'access_token' => $capiToken,
            ];
            $testCode = (string) ($CONF['META_TEST_EVENT_CODE'] ?? '');
            if ($testCode !== '') $capiBody['test_event_code'] = $testCode;

            $graphVer = (string) ($CONF['META_GRAPH_VERSION'] ?? 'v26.0');
            $ch = curl_init('https://graph.facebook.com/' . $graphVer . '/' . $pixelId . '/events');
            if ($ch === false) throw new RuntimeException('curl_init failed');
            curl_setopt_array($ch, [
                CURLOPT_POST           => true,
                CURLOPT_POSTFIELDS     => (string) json_encode($capiBody, JSON_INVALID_UTF8_SUBSTITUTE | JSON_UNESCAPED_SLASHES),
                CURLOPT_RETURNTRANSFER => true,
                CURLOPT_TIMEOUT        => $detached ? 8 : 3,
                CURLOPT_CONNECTTIMEOUT => $detached ? 4 : 2,
                CURLOPT_SSL_VERIFYPEER => true,
                CURLOPT_SSL_VERIFYHOST => 2,
                CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
            ]);
            $capiResp = curl_exec($ch);
            $capiCode = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
            if ($capiResp === false || $capiCode !== 200) {
                // The token travels in the POST body, never the URL, and the response doesn't echo it.
                error_log(sprintf('[lakeview/submit] CAPI fail: code=%d resp=%s',
                    $capiCode, is_string($capiResp) ? substr($capiResp, 0, 300) : '(none)'));
            }
        } catch (\Throwable $e) {
            error_log('[lakeview/submit] CAPI exception: ' . $e->getMessage());
        }
    });
}

// ─── Success ─────────────────────────────────────────────────────────────────
$thanksKey = $THANKS_KEY[$formId] ?? 'fCB';
$redirect  = '/thanks.html?form=' . urlencode($thanksKey);

respond(200, true, '', $redirect, ['lead_id' => $eventId]);
