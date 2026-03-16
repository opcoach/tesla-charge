<?php
declare(strict_types=1);

require dirname(__DIR__, 2) . '/lib/tesla_oauth.php';

$body = '<h1>Déconnexion Tesla terminée</h1>'
    . '<p>Le retour de déconnexion a été reçu correctement.</p>'
    . '<div class="actions"><a class="button" href="/">Retour à l’accueil</a></div>';

tesla_render_page('Déconnexion Tesla', $body);
