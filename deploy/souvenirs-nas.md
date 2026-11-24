# Souvenirs : copie de nuit vers le NAS

Les photos Souvenirs sont sur le disque du serveur Party (décision du 24.11.2026), dans le volume Docker de `DATA_DIR`
(`/data/souvenirs` dans le conteneur). La sauvegarde Proxmox de la VM les contient déjà ; cette copie de nuit en garde
une seconde sur le NAS. Elle est un MIROIR (`rsync --delete`) : une photo effacée dans Party disparaît aussi du NAS la
nuit suivante (droit à l'image, 13 mois, compte supprimé). Rien n'est installé par le dépôt : à appliquer à la main.

## Ce qui a été relevé (24.11.2026, lecture seule)

- Hôte Docker : `root@192.168.50.204` (Debian 12), `rsync` et `cron` présents.
- Volumes : prod `vendrediparty_vendrediparty-data` →
  `/var/lib/docker/volumes/vendrediparty_vendrediparty-data/_data` ; test `vendrediparty-test_vendrediparty-test-data` →
  `/var/lib/docker/volumes/vendrediparty-test_vendrediparty-test-data/_data`. Le conteneur tourne en root.
- NAS `192.168.50.150` (Synology) : partage SMB `docker` (sous-dossier `transmission` monté sur `/transmission`, 995 Go
  libres), NFS `/volume2/PLEX` sur `/mnt/PLEX` (97 % plein : à éviter).
- `/etc/fstab` contient le mot de passe SMB en clair : le mettre dans un fichier de 600 (`credentials=`) au passage.

## Procédure (une fois)

1. Sur le NAS (DSM) : créer le dossier `docker/party-souvenirs` (dans le partage `docker`, comme `transmission`).
2. Sur l'hôte, un fichier d'identifiants lisible par root seul :

   ```sh
   install -m 600 /dev/null /root/.nas-smb
   printf 'username=bobycharbon\npassword=…\n' > /root/.nas-smb   # le mot de passe du compte SMB du NAS
   mkdir -p /mnt/party-souvenirs
   ```

3. Montage permanent, ajouté à `/etc/fstab` :

   ```
   //192.168.50.150/docker/party-souvenirs /mnt/party-souvenirs cifs credentials=/root/.nas-smb,iocharset=utf8,vers=3.0,uid=0,gid=0,file_mode=0600,dir_mode=0700,nofail,_netdev 0 0
   ```

   puis `mount /mnt/party-souvenirs && mountpoint /mnt/party-souvenirs`.
4. Le script (depuis le dépôt) : `install -m 755 deploy/souvenirs-nas.sh /usr/local/bin/party-souvenirs-nas`
5. La tâche de nuit, `/etc/cron.d/party-souvenirs-nas` :

   ```
   # Souvenirs : miroir de nuit vers le NAS (prod à 3 h 30, test à 3 h 45)
   30 3 * * * root /usr/local/bin/party-souvenirs-nas /var/lib/docker/volumes/vendrediparty_vendrediparty-data/_data/souvenirs /mnt/party-souvenirs/prod >> /var/log/party-souvenirs-nas.log 2>&1
   45 3 * * * root /usr/local/bin/party-souvenirs-nas /var/lib/docker/volumes/vendrediparty-test_vendrediparty-test-data/_data/souvenirs /mnt/party-souvenirs/test >> /var/log/party-souvenirs-nas.log 2>&1
   ```

6. Essai tout de suite : lancer la ligne de la prod à la main, puis Admin › Réglages › Serveur :
   « 📸 Souvenirs : N photos · X Mo sur le serveur · dernière copie NAS : <date> ».

## Garanties du script

- Partage non monté : arrêt, rien n'est effacé (jamais de `--delete` vers un dossier local vide).
- Fichiers en cours d'écriture (`*.tmp`) ignorés ; la date de la dernière copie réussie est écrite dans
  `souvenirs/.derniere-copie-nas` (lue par l'admin).
- Restauration : `rsync -rt /mnt/party-souvenirs/prod/ <volume>/_data/souvenirs/` (seules les photos dont la ligne existe
  encore dans la base sont montrées ; un fichier sans ligne n'a pas de lien).
