# Proxy Tesla local

Ce dossier n’est pas versionné pour les fichiers sensibles, mais il sert d’emplacement simple pour :

- `fleet-key.pem` : clé privée Fleet API correspondant à la clé publique publiée sur `tesla.opcoach.com`
- `tls-cert.pem` : certificat TLS local du proxy
- `tls-key.pem` : clé privée TLS locale du proxy

Important :

- `fleet-key.pem` doit rester privé ;
- la clé publique dérivée de `fleet-key.pem` doit être celle publiée sur `https://tesla.opcoach.com/.well-known/appspecific/com.tesla.3p.public-key.pem` ;
- si tu n’as plus cette clé privée, il faudra régénérer une paire de clés, republier la clé publique, réenregistrer l’application et refaire le pairing.
