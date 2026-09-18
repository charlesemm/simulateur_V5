#!/usr/bin/env bash
# ÉCHO — sauvegarde quotidienne de la base
#
# La base est le seul élément irremplaçable du déploiement : l'image se
# retire de GHCR, la configuration se réécrit, mais une campagne perdue
# l'est définitivement. Ce script produit un dump compressé par jour et
# efface ceux de plus de trente jours.
#
# Installation (section 13 du GUIDE_DEPLOIEMENT.md) :
#   chmod +x /opt/echo/sauvegarde.sh
#   sudo crontab -e   →   15 2 * * * /opt/echo/sauvegarde.sh >> /var/log/echo-sauvegarde.log 2>&1
#
# La crontab de root, et non celle de l'utilisateur : sous Oracle Linux les
# conteneurs tournent en mode privilegie (voir section 9 du guide), et un
# podman-compose lance sans sudo ne les verrait pas.

# -e : on s'arrête à la première erreur. -u : une variable non définie est
# une erreur. -o pipefail : un échec au milieu d'un tuyau n'est pas avalé
# par le succès de la commande suivante — sans lui, un pg_dump en échec
# suivi d'un gzip réussi produirait une archive vide réputée valide.
set -euo pipefail

DOSSIER_PROJET="/opt/echo"
DOSSIER_SAUVEGARDES="/var/sauvegardes/echo"
JOURS_CONSERVES=30

horodatage=$(date +%Y%m%d_%H%M)
destination="${DOSSIER_SAUVEGARDES}/echo_${horodatage}.sql.gz"

mkdir -p "$DOSSIER_SAUVEGARDES"

cd "$DOSSIER_PROJET"

# On écrit d'abord dans un fichier temporaire, renommé seulement en cas de
# succès : une sauvegarde interrompue ne peut donc pas se faire passer pour
# une sauvegarde valide dans le dossier.
temporaire="${destination}.en_cours"

podman-compose -f compose.prod.yaml exec -T postgres \
    pg_dump -U echo -d echo_db --clean --if-exists \
    | gzip -9 > "$temporaire"

mv "$temporaire" "$destination"
chmod 600 "$destination"

echo "$(date '+%F %T') — sauvegarde écrite : ${destination} ($(du -h "$destination" | cut -f1))"

# Purge des anciennes. -mtime +N ne compte que les fichiers du motif : une
# archive en cours d'écriture (« .en_cours ») n'est jamais effacée ici.
find "$DOSSIER_SAUVEGARDES" -name 'echo_*.sql.gz' -mtime "+${JOURS_CONSERVES}" -delete

echo "$(date '+%F %T') — archives de plus de ${JOURS_CONSERVES} jours purgées"
