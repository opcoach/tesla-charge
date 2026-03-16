# Installation sur `tesla.opcoach.com`

Déployer sur le sous-domaine uniquement le contenu du répertoire `tesla.opcoach.com/`.

## Arborescence attendue

```text
tesla.opcoach.com/
├── .well-known/
│   └── appspecific/
│       └── com.tesla.3p.public-key.pem
├── auth/
│   ├── callback/
│   │   └── index.php
│   └── start/
│       └── index.php
├── lib/
│   └── tesla_oauth.php
├── logout/
│   └── callback/
│       └── index.php
├── index.php
├── tesla-oauth-config.php
└── tesla-oauth-config.php.example
```

## Fichier de configuration

Le dépôt contient déjà `tesla-oauth-config.php` avec des placeholders. Il faut remplacer :

- `REMPLACER_PAR_LE_CLIENT_ID_TESLA`
- `REMPLACER_PAR_LE_CLIENT_SECRET_TESLA`

Le modèle `tesla-oauth-config.php.example` reste disponible comme référence.

Pour un compte Tesla utilisé en France, l’audience par défaut à configurer est :

```text
https://fleet-api.prd.eu.vn.cloud.tesla.com
```

Le `refresh_token` est sauvegardé par défaut dans le parent du dossier web :

```text
/home/compte/tesla-charge/tesla-refresh-token.json
```

## URLs Tesla à déclarer

- `URL d'origine autorisée` : `https://tesla.opcoach.com`
- `URI de redirection autorisée` : `https://tesla.opcoach.com/auth/callback/`
- `URL de renvoi autorisée` : `https://tesla.opcoach.com/logout/callback/`

## Clé publique

La clé publique doit être publiée ici :

```text
https://tesla.opcoach.com/.well-known/appspecific/com.tesla.3p.public-key.pem
```

## Démarrage du flux OAuth

Une fois le sous-domaine déployé et la configuration privée en place :

```text
https://tesla.opcoach.com/auth/start/
```

Le callback sauvegarde ensuite le `refresh_token` dans le fichier privé configuré.
