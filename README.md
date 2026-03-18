# tesla-charge

Dépôt unique pour deux composants complémentaires :

- `raspberry/` : service Python léger qui tourne en continu sur une Raspberry Pi et ajuste la charge Tesla selon le surplus solaire ;
- `tesla.opcoach.com/` : mini site PHP pour Tesla Fleet API, utilisé pour l’autorisation OAuth, le callback et le key pairing.
- `tesla-refresh-token.json` : fichier local généré après l’autorisation OAuth, à copier sur la Raspberry hors du webroot.

## Arborescence

```text
tesla-charge/
├── tesla-refresh-token.json
├── deploy/
│   └── systemd/
│       ├── README.md
│       ├── tesla-charge.env.example
│       ├── tesla-charge.service
│       └── tesla-command-proxy.service.example
├── raspberry/
│   ├── app.py
│   ├── api_server.py
│   ├── config.py
│   ├── control_loop.py
│   ├── proxy/
│   │   └── README.md
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

La boucle solaire tourne toutes les `5` secondes par défaut.
La lecture Tesla est mise en cache `30` secondes par défaut pour éviter de solliciter inutilement le véhicule.
Si le proxy local de commandes n’est pas disponible, un nouvel essai n’est tenté qu’après `60` secondes par défaut.

### Variables d’environnement

- `ENPHASE_TOKEN` : obligatoire
- `TESLA_CLIENT_ID` : recommandé, sinon lu depuis `tesla-refresh-token.json` s’il contient déjà `client_id`
- `ENVOY_URL` : défaut `https://192.168.68.57/ivp/meters/readings`
- `TESLA_REFRESH_TOKEN_FILE` : défaut `../tesla-refresh-token.json`
- `TESLA_API_BASE_URL` : défaut `https://fleet-api.prd.eu.vn.cloud.tesla.com`
- `TESLA_AUTH_URL` : défaut `https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token`
- `TESLA_PROXY_URL` : défaut `https://localhost:4443`
- `TESLA_PROXY_VERIFY_SSL` : défaut `false`
- `TESLA_PROXY_CA_FILE` : optionnel, chemin vers un certificat local si tu veux vérifier TLS
- `TESLA_VEHICLE_NAME` : optionnel
- `TESLA_VEHICLE_INDEX` : défaut `0`
- `CONTROL_INTERVAL_SEC` : défaut `5`
- `TESLA_STATUS_INTERVAL_SEC` : défaut `30`
- `TESLA_PROXY_RETRY_SEC` : défaut `60`
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

### Composants système nécessaires

Sur une installation Raspberry Pi OS Lite récente, les composants suivants ont été nécessaires :

- `python3-venv` pour créer l’environnement virtuel Python
- `openssl` pour générer le certificat TLS local du proxy
- `go` uniquement si tu compiles `tesla-http-proxy` directement sur la Raspberry

Exemple :

```bash
sudo apt update
sudo apt install -y python3-venv openssl golang
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

Tant que rien n’écoute sur `TESLA_PROXY_URL` (par défaut `https://localhost:4443`), l’application reste utile pour la supervision solaire et Tesla, mais passe de fait en lecture seule pour les commandes de charge.

### Vérifications utiles

Vérifier l’application web :

```bash
curl http://127.0.0.1:8080/status
```

Vérifier le proxy local Tesla :

```bash
ss -ltnp | grep 4443
```

Vérifier le service principal :

```bash
sudo systemctl status tesla-charge --no-pager
```

Vérifier le proxy :

```bash
sudo systemctl status tesla-command-proxy --no-pager
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

### Fichiers systemd versionnés

Le dépôt contient maintenant les fichiers prêts à copier dans `deploy/systemd/` :

- `deploy/systemd/tesla-charge.service`
- `deploy/systemd/tesla-charge.env.example`
- `deploy/systemd/tesla-command-proxy.service.example`
- `deploy/systemd/README.md`

Les unités `systemd` sont à installer dans :

```text
/etc/systemd/system/
```

Les fichiers versionnés supposent un utilisateur Raspberry nommé `olivier`. Si besoin, adapte `User=` et les chemins `/home/olivier/...`.

L’application Python ne doit pas démarrer elle-même le proxy local. Le proxy de commandes Tesla doit rester un service séparé, plus simple à superviser et redémarrer.

Le proxy local Tesla officiel est `tesla-http-proxy`. Il écoute en HTTPS, pas en HTTP.

### Clés et certificats du proxy

Le proxy local Tesla a besoin de trois fichiers :

- une clé privée Fleet API, correspondant à la clé publique publiée sur le sous-domaine web ;
- un certificat TLS local ;
- une clé privée TLS locale.

Exemple de préparation :

```bash
mkdir -p "$HOME/git/tesla-charge/raspberry/proxy"

cp /chemin/vers/la_vraie_cle_privee_fleet.pem \
  "$HOME/git/tesla-charge/raspberry/proxy/fleet-key.pem"
chmod 600 "$HOME/git/tesla-charge/raspberry/proxy/fleet-key.pem"

openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$HOME/git/tesla-charge/raspberry/proxy/tls-key.pem" \
  -out "$HOME/git/tesla-charge/raspberry/proxy/tls-cert.pem" \
  -days 3650 \
  -subj "/CN=localhost"

chmod 600 "$HOME/git/tesla-charge/raspberry/proxy/tls-key.pem"
```

Important :

- `fleet-key.pem` doit contenir une clé privée, pas une clé publique ;
- si `openssl pkey -in .../fleet-key.pem -noout` échoue, le fichier n’est pas le bon ;
- si tu perds la vraie clé privée Fleet, il faut régénérer une paire, republier la clé publique et refaire le pairing Tesla.

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

De manière générique, si le domaine change plus tard :

- origine : `https://<app-domain>`
- callback OAuth : `https://<app-domain>/auth/callback/`
- logout callback : `https://<app-domain>/logout/callback/`
- clé publique : `https://<app-domain>/.well-known/appspecific/com.tesla.3p.public-key.pem`

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

### Enregistrement partner account

Après création de l’application et publication de la clé publique, il faut enregistrer le domaine auprès de Fleet API.

Exemple pour la région Europe :

```bash
CLIENT_ID='...'
CLIENT_SECRET='...'
AUDIENCE='https://fleet-api.prd.eu.vn.cloud.tesla.com'

PARTNER_TOKEN=$(
  curl -s --request POST \
    --url 'https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token' \
    --header 'Content-Type: application/x-www-form-urlencoded' \
    --data-urlencode 'grant_type=client_credentials' \
    --data-urlencode "client_id=${CLIENT_ID}" \
    --data-urlencode "client_secret=${CLIENT_SECRET}" \
    --data-urlencode "audience=${AUDIENCE}" \
    --data-urlencode 'scope=openid vehicle_device_data vehicle_cmds vehicle_charging_cmds' \
  | jq -r '.access_token'
)

curl --request POST \
  --url "${AUDIENCE}/api/1/partner_accounts" \
  --header "Authorization: Bearer ${PARTNER_TOKEN}" \
  --header 'Content-Type: application/json' \
  --data '{"domain":"tesla.opcoach.com"}'
```

Une fois le domaine enregistré, il reste à faire le key pairing pour les commandes signées.

## 3. Développement

Validation syntaxique Python :

```bash
cd raspberry
python3 -m py_compile app.py api_server.py config.py control_loop.py solar_monitor.py tesla_controller.py
```

## 4. Git

Le dépôt ignore notamment :

- `tesla-refresh-token.json`
- `deploy/systemd/*.env`
- les artefacts Python
- les environnements virtuels
- les fichiers `.env`
- les fichiers privés OAuth et les tokens de `tesla.opcoach.com`

Le cache Tesla, les secrets OAuth et les tokens ne doivent pas être versionnés.

### Dépôt public et valeurs locales

Si le dépôt est rendu public, il est recommandé de ne laisser dans Git que des valeurs d’exemple ou génériques.

Les vraies valeurs doivent rester uniquement :

- dans `/etc/default/tesla-charge` pour le service principal ;
- dans `/etc/systemd/system/tesla-charge.service` si tu l’as adapté localement ;
- dans `/etc/systemd/system/tesla-command-proxy.service` si tu l’as adapté localement ;
- dans `deploy/systemd/tesla-charge.env` en local seulement, non versionné ;
- dans `tesla-refresh-token.json`, non versionné ;
- dans `raspberry/proxy/*.pem`, non versionnés ;
- dans `tesla-oauth-config.php`, hors Git et hors webroot.

Exemple de workflow :

```bash
cp deploy/systemd/tesla-charge.env.example deploy/systemd/tesla-charge.env
nano deploy/systemd/tesla-charge.env
sudo cp deploy/systemd/tesla-charge.env /etc/default/tesla-charge
```

Dans ce modèle :

- le dépôt peut contenir des exemples génériques ;
- `git pull` met à jour le code et les exemples ;
- les vraies valeurs restent en dehors des fichiers versionnés ;
- un `git pull` n’écrase pas `/etc/default/tesla-charge`.

Si tu modifies un fichier versionné pour y mettre une vraie valeur, il faudra la remettre après un `git pull`. Il vaut donc mieux éviter ce mode de fonctionnement.
