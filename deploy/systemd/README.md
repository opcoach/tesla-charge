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

Vérifie aussi le fichier `/etc/systemd/system/tesla-charge.service` si ton utilisateur Raspberry n’est pas `olivier`.

Puis active le service :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tesla-charge
sudo systemctl status tesla-charge
```

## 2. Service du proxy local Tesla

Le proxy local n’est pas lancé par l’application Python. Il doit rester un service séparé.

Le dépôt fournit donc un exemple à adapter :

```bash
sudo cp deploy/systemd/tesla-command-proxy.service.example /etc/systemd/system/tesla-command-proxy.service
sudo nano /etc/systemd/system/tesla-command-proxy.service
```

À faire dans ce fichier :

- remplacer `User=olivier` si ton utilisateur Raspberry est différent ;
- remplacer `ExecStart=/CHEMIN/DU/PROXY --listen 127.0.0.1:4443` par la vraie commande du proxy ;
- conserver l’écoute locale sur `127.0.0.1:4443` si tu gardes `TESLA_PROXY_URL=http://localhost:4443`.

Quand le fichier est prêt :

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now tesla-command-proxy
sudo systemctl status tesla-command-proxy
ss -ltnp | grep 4443
```

Si `ss -ltnp | grep 4443` ne retourne rien, le proxy n’est pas encore lancé correctement.
