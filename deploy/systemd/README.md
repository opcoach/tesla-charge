# Fichiers `systemd`

Les unités personnalisées `systemd` se placent dans :

```text
/etc/systemd/system/
```

Les fichiers d’environnement simples peuvent aller dans :

```text
/etc/default/
```

## 1. Service principal `tesla-charge`

Copie les fichiers versionnés :

```bash
sudo cp deploy/systemd/tesla-charge.service /etc/systemd/system/tesla-charge.service
sudo cp deploy/systemd/tesla-charge.env.example /etc/default/tesla-charge
sudo nano /etc/default/tesla-charge
```

Dans `/etc/default/tesla-charge`, remplace au minimum :

- `ENPHASE_TOKEN`
- `TESLA_CLIENT_ID`
- `TESLA_VEHICLE_NAME` si tu veux cibler explicitement `Tesla opc`
- `TESLA_NOMINAL_VOLTAGE` si tu veux ajuster le calcul de consigne
- `TESLA_CHARGE_START_AMPS` et `TESLA_CHARGE_STOP_AMPS` si tu veux ajuster les seuils de démarrage et d'arrêt
- `TESLA_CHARGE_START_CONFIRM_SEC` et `TESLA_CHARGE_STOP_CONFIRM_SEC` si tu veux ajuster les temporisations
- `TIMELINE_WINDOW_SEC` si tu veux garder plus ou moins d'historique en mémoire pour le dashboard
- `TESLA_STATUS_INTERVAL_SEC` et `TESLA_DETAIL_INTERVAL_SEC` si tu veux ajuster la fréquence des lectures Tesla et garder le coût sous contrôle

Vérifie aussi le fichier `/etc/systemd/system/tesla-charge.service` si ton utilisateur Raspberry n’est pas `olivier`.

Puis active le service :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tesla-charge
sudo systemctl status tesla-charge
```

## 2. Service du proxy local Tesla

Le proxy local n’est pas lancé par l’application Python. Il doit rester un service séparé.

Le binaire attendu est `tesla-http-proxy`, issu du dépôt officiel Tesla `vehicle-command`.

Le plus simple pour le service versionné fourni ici est d’installer ce binaire dans :

```text
/usr/local/bin/tesla-http-proxy
```

### Installer le binaire

Si ta Raspberry dispose d’une version de Go compatible, tu peux compiler directement dessus :

```bash
cd /tmp
git clone https://github.com/teslamotors/vehicle-command.git
cd vehicle-command
go build -o tesla-http-proxy ./cmd/tesla-http-proxy
sudo install -m 0755 tesla-http-proxy /usr/local/bin/tesla-http-proxy
```

Si la compilation est trop lourde ou si ta version de Go est trop ancienne sur la Raspberry, le plus pragmatique est de compiler ailleurs pour `linux/arm/v6`, puis de copier le binaire sur la Raspberry.

Le dépôt fournit ensuite un service prêt à l’emploi :

```bash
sudo cp deploy/systemd/tesla-command-proxy.service.example /etc/systemd/system/tesla-command-proxy.service
sudo nano /etc/systemd/system/tesla-command-proxy.service
```

### Préparer les fichiers locaux du proxy

Créer le dossier attendu :

```bash
mkdir -p "$HOME/git/tesla-charge/raspberry/proxy"
```

1. Copier la clé privée Fleet API correspondant à ta clé publique publiée :

```bash
cp /chemin/vers/la/cle_privee_fleet.pem "$HOME/git/tesla-charge/raspberry/proxy/fleet-key.pem"
chmod 600 "$HOME/git/tesla-charge/raspberry/proxy/fleet-key.pem"
```

2. Générer un certificat TLS local pour `localhost` :

```bash
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "$HOME/git/tesla-charge/raspberry/proxy/tls-key.pem" \
  -out "$HOME/git/tesla-charge/raspberry/proxy/tls-cert.pem" \
  -days 3650 \
  -subj "/CN=localhost"
chmod 600 "$HOME/git/tesla-charge/raspberry/proxy/tls-key.pem"
```

### Préparer le service

À vérifier dans ce fichier :

- remplacer `User=olivier` si ton utilisateur Raspberry est différent ;
- adapter les chemins `/home/olivier/...` si ton dépôt est ailleurs ;
- conserver l’écoute locale sur `127.0.0.1:4443` si tu gardes `TESLA_PROXY_URL=https://localhost:4443`.

Quand le fichier est prêt :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tesla-command-proxy
sudo systemctl status tesla-command-proxy
ss -ltnp | grep 4443
```

Si `ss -ltnp | grep 4443` ne retourne rien, le proxy n’est pas encore lancé correctement.

## 3. Variables côté application Python

Dans `/etc/default/tesla-charge`, garde en général :

```text
TESLA_PROXY_URL=https://localhost:4443
TESLA_PROXY_VERIFY_SSL=false
TESLA_NOMINAL_VOLTAGE=220
TESLA_CHARGE_START_AMPS=6
TESLA_CHARGE_STOP_AMPS=5
TESLA_CHARGE_START_CONFIRM_SEC=60
TESLA_CHARGE_STOP_CONFIRM_SEC=90
TESLA_STATUS_INTERVAL_SEC=900
TESLA_DETAIL_INTERVAL_SEC=3600
TIMELINE_WINDOW_SEC=3600
```

Le proxy Tesla officiel écoute en HTTPS. Le mode `VERIFY_SSL=false` est acceptable ici parce que le service reste lié à `localhost`.
