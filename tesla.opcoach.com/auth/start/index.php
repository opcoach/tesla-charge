<?php
declare(strict_types=1);

session_start();

require dirname(__DIR__, 2) . '/lib/tesla_oauth.php';

try {
    $config = load_tesla_oauth_config();
    $state = bin2hex(random_bytes(16));
    $_SESSION['tesla_oauth_state'] = $state;

    $params = [
        'response_type' => 'code',
        'client_id' => $config['client_id'],
        'redirect_uri' => $config['redirect_uri'],
        'scope' => $config['scope'],
        'state' => $state,
        'audience' => $config['audience'],
        'prompt' => 'login',
        'prompt_missing_scopes' => 'true',
        'require_requested_scopes' => 'true',
        'show_keypair_step' => 'true',
    ];

    $url = 'https://auth.tesla.com/oauth2/v3/authorize?' . http_build_query($params);
    header('Cache-Control: no-store');
    header('Location: ' . $url, true, 302);
    exit;
} catch (Throwable $exception) {
    tesla_fail($exception->getMessage(), 500);
}
