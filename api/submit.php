<?php
declare(strict_types=1);

/**
 * ЖК Lakeview — universal lead form handler.
 *
 * Handles 5 forms (callback, apartment, catalog, commercial, footer).
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

/** Send JSON response or 303 redirect, then exit. */
function respond(int $status, bool $ok, string $message, ?string $redirect = null): never {
    http_response_code($status);
    if (is_ajax()) {
        header('Content-Type: application/json; charset=utf-8');
        $payload = ['ok' => $ok];
        if ($ok && $redirect) $payload['redirect'] = $redirect;
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
    'pricelock'  => '🔒 Фіксація ціни до 15.09',
];
$THANKS_KEY = [
    'callback'   => 'fCB',
    'apartment'  => 'fApt',
    'catalog'    => 'fR',
    'commercial' => 'fC',
    'footer'     => 'fF',
    'pricelock'  => 'fPL',
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
    'pricelock'  => ['name', 'phone'],
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
$phoneLen = strlen($phoneDigits);
if ($phoneLen < 10 || $phoneLen > 15) {
    log_submission($LOG_FILE, $ip, $formId, $name, $phoneRaw, 'reject:phone-format');
    respond(400, false, 'Некоректний номер телефону');
}
// Pretty phone: prefix + with single space chunks
$phonePretty = '+' . $phoneDigits;

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
$lines[] = '';
$lines[] = '🌐 IP: <code>' . safe_html($ip) . '</code>';
$lines[] = '⏰ ' . safe_html($nowKyiv) . ' (Kyiv)';
if ($referer !== '') {
    $lines[] = '🔗 Сторінка: ' . safe_html($referer);
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

// ─── Success ─────────────────────────────────────────────────────────────────
log_submission($LOG_FILE, $ip, $formId, $name, $phoneRaw, 'ok');

$thanksKey = $THANKS_KEY[$formId] ?? 'fCB';
$redirect  = '/thanks.html?form=' . urlencode($thanksKey);

respond(200, true, '', $redirect);
