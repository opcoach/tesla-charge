# tesla-charge

Dépôt unique pour deux composants complémentaires :

- `raspberry/` : service Python léger qui tourne en continu sur une Raspberry Pi et ajuste la charge Tesla selon le surplus solaire ;
- `tesla.opcoach.com/` : mini site PHP pour Tesla Fleet API, utilisé pour l’autorisation OAuth, le callback et le key pairing.
- `tesla-refresh-token.json` : fichier local généré après l’autorisation OAuth, à copier sur la Raspberry hors du webroot.

## Arborescence

```text
tesla-charge/
├── tesla-refresh-token.json
├── raspberry/
│   ├── app.py
│   ├── api_server.py
│   ├── config.py
│   ├── control_loop.py
│   ├── requirements.txt
│   ├── solar_monitor.py
│   └── tesla_controller.py
└── tesla.opcoach.com/
    ├── .well-known/
    │   └── appspecific/
    │       └── com.tesla.3p.public-key.pem
    ├── auth/
    ├── lib/
    ├── logout/
    ├── index.php
    └── tesla-oauth-config.php.example
```

## 1. Raspberry Pi

Le composant `raspberry/` est une application Python 3.11 prévue pour Raspberry Pi OS Lite, avec un minimum de dépendances.

### Dépendances Python

- `requests`
- `flask`

### Fonctionnement

Le service :

- lit les données de production et de réseau via l’Envoy Enphase ;
- calcule le surplus exporté ;
- convertit ce surplus en intensité de charge Tesla ;
- lit l’état du véhicule via Tesla Fleet API à partir d’un `refresh_token` ;
- borne la consigne entre `6 A` et `32 A` ;
- n’envoie pas de commande si l’ampérage ne change pas ;
- expose une API REST ;
- affiche une page web locale de résumé.

La boucle de contrôle tourne toutes les `5` secondes par défaut.

### Variables d’environnement

- `ENPHASE_TOKEN` : obligatoire
- `TESLA_CLIENT_ID` : recommandé, sinon lu depuis `tesla-refresh-token.json` s’il contient déjà `client_id`
- `ENVOY_URL` : défaut `https://192.168.68.57/ivp/meters/readings`
- `TESLA_REFRESH_TOKEN_FILE` : défaut `../tesla-refresh-token.json`
- `TESLA_API_BASE_URL` : défaut `https://fleet-api.prd.eu.vn.cloud.tesla.com`
- `TESLA_AUTH_URL` : défaut `https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token`
- `TESLA_PROXY_URL` : défaut `http://localhost:4443`
- `TESLA_VEHICLE_NAME` : optionnel
- `TESLA_VEHICLE_INDEX` : défaut `0`
- `CONTROL_INTERVAL_SEC` : défaut `5`
- `TESLA_MIN_AMPS` : défaut `6`
- `TESLA_MAX_AMPS` : défaut `32`
- `APP_HOST` : défaut `0.0.0.0`
- `APP_PORT` : défaut `8080`
- `REQUEST_TIMEOUT_SEC` : défaut `10`
- `LOG_LEVEL` : défaut `INFO`
- `ENVOY_VERIFY_SSL` : défaut `false`

### Installation sur la Raspberry

```bash
cd "$HOME/git"
git clone <URL_DU_DEPOT> tesla-charge
cd "$HOME/git/tesla-charge/raspberry"
sudo apt update
sudo apt install -y python3-venv
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copier ensuite le fichier `tesla-refresh-token.json` généré par le callback web vers la racine du dépôt sur la Raspberry :

```bash
scp /chemin/local/vers/tesla-refresh-token.json pi@raspberrypi:git/tesla-charge/tesla-refresh-token.json
```

### Lancement manuel

```bash
cd "$HOME/git/tesla-charge/raspberry"
. .venv/bin/activate
export ENPHASE_TOKEN='...'
export TESLA_CLIENT_ID='...'
python app.py
```

L’interface locale sera disponible sur :

```text
http://<ip-de-la-raspberry>:8080/
```

### API REST

- `GET /solar`
- `GET /tesla`
- `GET /status`
- `POST /tesla/amps`

Exemple :

```bash
curl -X POST http://raspberrypi:8080/tesla/amps \
  -H 'Content-Type: application/json' \
  -d '{"amps": 10}'
```

### Exemple systemd

Créer `/etc/systemd/system/tesla-charge.service` :

```ini
[Unit]
Description=Tesla charge on solar surplus
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/git/tesla-charge/raspberry
Environment=ENPHASE_TOKEN=remplacer_par_le_token
Environment=TESLA_CLIENT_ID=remplacer_par_le_client_id
ExecStart=/home/pi/git/tesla-charge/raspberry/.venv/bin/python /home/pi/git/tesla-charge/raspberry/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Puis :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tesla-charge
sudo systemctl status tesla-charge
```

## 2. Sous-domaine `tesla.opcoach.com`

Le composant `tesla.opcoach.com/` est un petit site PHP sans framework pour :

- démarrer le flux OAuth Tesla ;
- recevoir le callback OAuth ;
- échanger le `code` contre un token ;
- sauvegarder le `refresh_token` côté serveur ;
- exposer la clé publique à l’URL attendue par Tesla.

### Déploiement

Déployer uniquement le contenu du répertoire `tesla.opcoach.com/` sur le sous-domaine web.

Important :

- ne pas publier le répertoire `raspberry/` sur le site public ;
- créer le vrai `tesla-oauth-config.php` à la racine du dépôt sur le serveur, hors du dossier web ;
- publier la clé publique ici :
  `https://tesla.opcoach.com/.well-known/appspecific/com.tesla.3p.public-key.pem`

### Valeurs Tesla Fleet API

Dans l’interface Tesla :

- `URL d'origine autorisée` : `https://tesla.opcoach.com`
- `URI de redirection autorisée` : `https://tesla.opcoach.com/auth/callback/`
- `URL de renvoi autorisée` : `https://tesla.opcoach.com/logout/callback/`

### Configuration Tesla

Ne versionne pas `tesla-oauth-config.php`. Crée `/home/compte/tesla-charge/tesla-oauth-config.php` sur le serveur à partir de `tesla.opcoach.com/tesla-oauth-config.php.example`, puis remplace :

- `REMPLACER_PAR_LE_CLIENT_ID_TESLA`
- `REMPLACER_PAR_LE_CLIENT_SECRET_TESLA`

Pour un compte Tesla utilisé en France, l’audience Fleet API à garder dans l’exemple est :

```text
https://fleet-api.prd.eu.vn.cloud.tesla.com
```

Le `refresh_token` est sauvegardé par défaut hors de la racine web, dans le parent du dossier `tesla.opcoach.com`.

Exemple d’emplacement :

```text
/home/compte/tesla-charge/
├── tesla-oauth-config.php
├── tesla-refresh-token.json
└── tesla.opcoach.com/
    └── tesla-oauth-config.php.example
```

### Démarrage du flux OAuth

```text
https://tesla.opcoach.com/auth/start/
```

Après consentement, le callback sauvegarde le `refresh_token` dans le fichier privé configuré.

## 3. Développement

Validation syntaxique Python :

```bash
cd raspberry
python3 -m py_compile app.py api_server.py config.py control_loop.py solar_monitor.py tesla_controller.py
```

## 4. Git

Le dépôt ignore notamment :

- `tesla-refresh-token.json`
- les artefacts Python
- les environnements virtuels
- les fichiers `.env`
- les fichiers privés OAuth et les tokens de `tesla.opcoach.com`

Le cache Tesla, les secrets OAuth et les tokens ne doivent pas être versionnés.
