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
└── tesla-oauth-config.php.example
```

## Fichier de configuration privé

Le fichier réel `tesla-oauth-config.php` doit être placé de préférence au-dessus de la racine web, par exemple dans le répertoire parent du sous-domaine.

Exemple :

```text
/home/compte/
├── tesla-oauth-config.php
└── tesla.opcoach.com/
```

Le contenu du fichier peut être construit à partir de `tesla-oauth-config.php.example`.

Pour un compte Tesla utilisé en France, l’audience par défaut à configurer est :

```text
https://fleet-api.prd.eu.vn.cloud.tesla.com
```

## URLs Tesla à déclarer

- `URL d'origine autorisée` : `https://tesla.opcoach.com`
- `URI de redirection autorisée` : `https://tesla.opcoach.com/auth/callback`
- `URL de renvoi autorisée` : `https://tesla.opcoach.com/logout/callback`

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
