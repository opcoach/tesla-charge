<?php
declare(strict_types=1);

function tesla_config_candidates(): array
{
    $docRoot = dirname(__DIR__);
    $parentDir = dirname($docRoot);

    return [
        $parentDir . '/tesla-oauth-config.php',
        $docRoot . '/tesla-oauth-config.php',
    ];
}

function load_tesla_oauth_config(bool $required = true): ?array
{
    foreach (tesla_config_candidates() as $candidate) {
        if (!is_file($candidate)) {
            continue;
        }

        $config = require $candidate;
        if (!is_array($config)) {
            throw new RuntimeException('Le fichier de configuration Tesla doit retourner un tableau PHP.');
        }

        $requiredKeys = [
            'client_id',
            'client_secret',
            'redirect_uri',
            'logout_redirect_uri',
            'audience',
            'scope',
            'token_file',
            'developer_domain',
        ];

        foreach ($requiredKeys as $key) {
            if (!array_key_exists($key, $config) || $config[$key] === '') {
                throw new RuntimeException("Clé de configuration Tesla manquante : {$key}");
            }
        }

        return $config;
    }

    if ($required) {
        $paths = implode(' ou ', tesla_config_candidates());
        throw new RuntimeException(
            "Fichier de configuration Tesla introuvable. Créez {$paths} à partir de tesla-oauth-config.php.example."
        );
    }

    return null;
}

function tesla_render_page(string $title, string $bodyHtml, int $status = 200): never
{
    http_response_code($status);
    header('Content-Type: text/html; charset=utf-8');
    header('Cache-Control: no-store');

    echo '<!doctype html>';
    echo '<html lang="fr"><head><meta charset="utf-8">';
    echo '<meta name="viewport" content="width=device-width, initial-scale=1">';
    echo '<title>' . htmlspecialchars($title, ENT_QUOTES, 'UTF-8') . '</title>';
    echo '<style>';
    echo 'body{font-family:system-ui,-apple-system,sans-serif;background:#f7f5ef;color:#201c17;margin:0;padding:32px;}';
    echo 'main{max-width:760px;margin:0 auto;background:#fffdf8;border:1px solid #ddd4c8;border-radius:18px;padding:28px;box-shadow:0 10px 30px rgba(0,0,0,.06);}';
    echo 'h1{margin-top:0;font-size:2rem;}';
    echo 'p,li{line-height:1.6;}';
    echo 'code{background:#f1ece2;padding:.15rem .35rem;border-radius:6px;}';
    echo 'a{color:#005d46;text-decoration:none;font-weight:600;}';
    echo '.actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px;}';
    echo '.button{display:inline-block;padding:12px 16px;border-radius:12px;background:#005d46;color:#fff;}';
    echo '.muted{color:#6b645c;}';
    echo '.error{color:#9b1c1c;}';
    echo '</style></head><body><main>';
    echo $bodyHtml;
    echo '</main></body></html>';
    exit;
}

function tesla_fail(string $message, int $status = 400): never
{
    $body = '<h1>Erreur Tesla OAuth</h1>'
        . '<p class="error">' . htmlspecialchars($message, ENT_QUOTES, 'UTF-8') . '</p>'
        . '<p class="muted">Vérifiez la configuration du sous-domaine et le fichier de configuration privé.</p>';

    tesla_render_page('Erreur Tesla OAuth', $body, $status);
}
