<?php
declare(strict_types=1);

require __DIR__ . '/lib/tesla_oauth.php';

$config = null;
$configError = null;

try {
    $config = load_tesla_oauth_config(false);
} catch (Throwable $exception) {
    $configError = $exception->getMessage();
}

$publicKeyUrl = 'https://' . $_SERVER['HTTP_HOST'] . '/.well-known/appspecific/com.tesla.3p.public-key.pem';
$body = '<h1>tesla.opcoach.com</h1>';
$body .= '<p>Point d’entrée minimal pour l’autorisation Tesla Fleet API et le key pairing.</p>';
$body .= '<ul>';
$body .= '<li>Clé publique attendue : <code>' . htmlspecialchars($publicKeyUrl, ENT_QUOTES, 'UTF-8') . '</code></li>';
$body .= '<li>Callback OAuth : <code>https://' . htmlspecialchars($_SERVER['HTTP_HOST'], ENT_QUOTES, 'UTF-8') . '/auth/callback</code></li>';
$body .= '<li>Logout callback : <code>https://' . htmlspecialchars($_SERVER['HTTP_HOST'], ENT_QUOTES, 'UTF-8') . '/logout/callback</code></li>';
$body .= '</ul>';

if ($configError !== null) {
    $body .= '<p class="error">' . htmlspecialchars($configError, ENT_QUOTES, 'UTF-8') . '</p>';
}

if ($config !== null) {
    $body .= '<p>Configuration privée détectée pour le domaine développeur <code>'
        . htmlspecialchars($config['developer_domain'], ENT_QUOTES, 'UTF-8')
        . '</code>.</p>';
}

$body .= '<div class="actions">';
$body .= '<a class="button" href="/auth/start/">Démarrer l’autorisation Tesla</a>';
$body .= '<a class="button" href="/.well-known/appspecific/com.tesla.3p.public-key.pem">Voir la clé publique</a>';
$body .= '</div>';
$body .= '<p class="muted">Le fichier privé <code>tesla-oauth-config.php</code> doit être placé de préférence au-dessus de la racine web.</p>';

tesla_render_page('Tesla OAuth', $body);
