# Hooks Git locaux

Ce dossier contient un hook `post-merge` versionné pour rappeler les commandes à lancer après un `git pull`.

## Installation locale

Dans le dépôt cloné sur la Raspberry :

```bash
chmod +x deploy/git-hooks/post-merge
git config core.hooksPath deploy/git-hooks
```

Ensuite, chaque `git pull` déclenchera le hook `post-merge`.

## Raccourcis shell conseillés

Ajoute ces fonctions dans `~/.bashrc` ou `~/.bash_profile` sur la Raspberry :

```bash
tesla-status() {
  sudo systemctl status tesla-command-proxy --no-pager
  sudo systemctl status tesla-charge --no-pager
}

tesla-restart() {
  sudo systemctl daemon-reload
  sudo systemctl restart tesla-command-proxy
  sudo systemctl restart tesla-charge
  tesla-status
}

tesla-restart-proxy() {
  sudo systemctl daemon-reload
  sudo systemctl restart tesla-command-proxy
  sudo systemctl status tesla-command-proxy --no-pager
}

tesla-restart-charge() {
  sudo systemctl restart tesla-charge
  sudo systemctl status tesla-charge --no-pager
}
```

Usage :

```bash
tesla-status
tesla-restart
tesla-restart-charge
```
