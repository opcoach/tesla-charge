<?php
declare(strict_types=1);

session_start();

require dirname(__DIR__, 2) . '/lib/tesla_oauth.php';

try {
    $config = load_tesla_oauth_config();

    if (isset($_GET['error'])) {
        $description = (string) ($_GET['error_description'] ?? $_GET['error']);
        tesla_fail('Tesla a renvoyé une erreur : ' . $description, 400);
    }

    $code = isset($_GET['code']) ? (string) $_GET['code'] : '';
    $state = isset($_GET['state']) ? (string) $_GET['state'] : '';
    $expectedState = isset($_SESSION['tesla_oauth_state']) ? (string) $_SESSION['tesla_oauth_state'] : '';

    if ($code === '' || $state === '') {
        tesla_fail('Paramètres OAuth manquants dans le callback.', 400);
    }

    if ($expectedState === '' || !hash_equals($expectedState, $state)) {
        tesla_fail('Le paramètre state OAuth est invalide.', 400);
    }

    $postFields = http_build_query([
        'grant_type' => 'authorization_code',
        'client_id' => $config['client_id'],
        'client_secret' => $config['client_secret'],
        'code' => $code,
        'audience' => $config['audience'],
        'redirect_uri' => $config['redirect_uri'],
    ]);

    $ch = curl_init('https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $postFields,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_HTTPHEADER => [
            'Content-Type: application/x-www-form-urlencoded',
        ],
        CURLOPT_TIMEOUT => 30,
    ]);

    $responseBody = curl_exec($ch);
    if ($responseBody === false) {
        $error = curl_error($ch);
        curl_close($ch);
        tesla_fail('Erreur cURL pendant l’échange du code OAuth : ' . $error, 502);
    }

    $statusCode = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    curl_close($ch);

    $payload = json_decode($responseBody, true);
    if ($statusCode >= 400 || !is_array($payload)) {
        tesla_fail('Échec de l’échange du code OAuth. Réponse brute : ' . $responseBody, 502);
    }

    if (empty($payload['refresh_token'])) {
        tesla_fail('Aucun refresh_token reçu depuis Tesla.', 502);
    }

    $tokenDirectory = dirname($config['token_file']);
    if (!is_dir($tokenDirectory) && !mkdir($tokenDirectory, 0700, true) && !is_dir($tokenDirectory)) {
        tesla_fail('Impossible de créer le répertoire de stockage du token.', 500);
    }

    $dataToStore = [
        'saved_at' => gmdate('c'),
        'client_id' => $config['client_id'],
        'access_token' => $payload['access_token'] ?? null,
        'refresh_token' => $payload['refresh_token'],
        'expires_in' => $payload['expires_in'] ?? null,
        'scope' => $payload['scope'] ?? null,
        'token_type' => $payload['token_type'] ?? null,
        'audience' => $config['audience'],
    ];

    $written = file_put_contents(
        $config['token_file'],
        json_encode($dataToStore, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES),
        LOCK_EX
    );

    if ($written === false) {
        tesla_fail('Impossible d’écrire le fichier de tokens.', 500);
    }

    @chmod($config['token_file'], 0600);
    unset($_SESSION['tesla_oauth_state']);

    $pairingUrl = 'https://www.tesla.com/_ak/' . rawurlencode((string) $config['developer_domain']);

    $body = '<h1>Autorisation Tesla enregistrée</h1>';
    $body .= '<p>Le <code>refresh_token</code> a été sauvegardé dans le fichier privé configuré côté serveur.</p>';
    $body .= '<ul>';
    $body .= '<li>Fichier token : <code>' . htmlspecialchars((string) $config['token_file'], ENT_QUOTES, 'UTF-8') . '</code></li>';
    $body .= '<li>Domaine développeur : <code>' . htmlspecialchars((string) $config['developer_domain'], ENT_QUOTES, 'UTF-8') . '</code></li>';
    $body .= '</ul>';
    $body .= '<div class="actions">';
    $body .= '<a class="button" href="' . htmlspecialchars($pairingUrl, ENT_QUOTES, 'UTF-8') . '">Lancer le key pairing Tesla</a>';
    $body .= '<a class="button" href="/">Retour à l’accueil</a>';
    $body .= '</div>';
    $body .= '<p class="muted">Si Tesla l’exige, connectez-vous à nouveau dans l’application mobile ou ouvrez directement ce lien sur le téléphone lié au véhicule.</p>';

    tesla_render_page('Tesla OAuth OK', $body);
} catch (Throwable $exception) {
    tesla_fail($exception->getMessage(), 500);
}
