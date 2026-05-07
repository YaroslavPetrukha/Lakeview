<?php
declare(strict_types=1);

/**
 * Config template — copy to config.php and fill in real values.
 *
 *   cp api/config.example.php api/config.php
 *
 * config.php is .gitignored — NEVER commit real secrets.
 */

return [
    // Telegram credentials (get token from @BotFather, chat_id from /getUpdates)
    'TELEGRAM_BOT_TOKEN' => 'YOUR_BOT_TOKEN_HERE',
    'TELEGRAM_CHAT_ID'   => 'YOUR_CHAT_ID_HERE', // negative number for group chats

    // Origin allowlist for CORS + Origin header validation
    'ALLOWED_ORIGINS' => [
        'https://www.lakeview.com.ua',
        'https://lakeview.com.ua',
        'http://localhost:8765',
    ],

    // Anti-abuse limits
    'RATE_LIMIT_PER_IP_PER_HOUR' => 5,
    'TIME_TRAP_MIN_SECONDS'      => 2,    // form filled too fast = bot
    'TIME_TRAP_MAX_SECONDS'      => 7200, // page sat 2h+ = stale/replay

    // Cloudflare Turnstile (v2 — disabled for v1)
    'TURNSTILE_ENABLED'    => false,
    'TURNSTILE_SECRET_KEY' => '',
];
