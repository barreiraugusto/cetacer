#!/usr/bin/env bash
# Copia de seguridad de la base y de los archivos subidos desde el panel.
# La ejecuta cetacer-backup.timer una vez por día, y sirve igual a mano:
#   bash /srv/cetacer/app/deploy/backup.sh
#
# Las copias quedan en el mismo servidor: eso cubre un borrado accidental o una
# migración que salga mal, pero NO la pérdida del VPS. Para eso hay que
# llevárselas afuera (ver el README).
set -euo pipefail

RAIZ=/srv/cetacer
DESTINO=/var/backups/cetacer
DIAS_DIARIAS=14      # cuántas copias diarias se conservan
MESES_MENSUALES=12   # cuántas copias del día 1 se conservan

# DATABASE_URL vive en el .env; pg_dump acepta la URL tal cual.
set -a
# shellcheck disable=SC1091
source "$RAIZ/.env"
set +a

if [[ -z "${DATABASE_URL:-}" ]]; then
    echo "No hay DATABASE_URL en $RAIZ/.env: la base es SQLite y este script no la cubre." >&2
    exit 1
fi

FECHA=$(date +%F)
# El dump lleva los datos personales de todos los participantes: que nazca
# legible sólo por root, sin depender de los permisos del directorio.
umask 077
install -d -m 700 "$DESTINO" "$DESTINO/diarias" "$DESTINO/mensuales"

base="$DESTINO/diarias/base-$FECHA.dump"
medios="$DESTINO/diarias/media-$FECHA.tar.gz"

# Se escribe a un archivo temporal y recién al terminar se renombra, así una
# corrida interrumpida no deja una copia truncada con nombre de copia buena.
echo "==> Base de datos"
pg_dump "$DATABASE_URL" --format=custom --file="$base.parcial"
mv "$base.parcial" "$base"

echo "==> Archivos subidos"
tar czf "$medios.parcial" -C "$RAIZ/app" media
mv "$medios.parcial" "$medios"

# Un dump que no se puede leer no es una copia de seguridad.
echo "==> Verificando que el dump se pueda leer"
pg_restore --list "$base" > /dev/null
tar tzf "$medios" > /dev/null

# El día 1 de cada mes la copia se guarda también como mensual.
if [[ "$(date +%d)" == "01" ]]; then
    cp -a "$base" "$DESTINO/mensuales/"
    cp -a "$medios" "$DESTINO/mensuales/"
fi

echo "==> Rotación"
find "$DESTINO/diarias"   -type f -mtime "+$DIAS_DIARIAS" -delete
find "$DESTINO/mensuales" -type f -mtime "+$((MESES_MENSUALES * 31))" -delete

echo "Listo:"
echo "  $(du -h "$base"   | cut -f1)  $(basename "$base")"
echo "  $(du -h "$medios" | cut -f1)  $(basename "$medios")"
echo "  copias diarias guardadas: $(find "$DESTINO/diarias" -name 'base-*.dump' | wc -l)"
echo "  ocupación total: $(du -sh "$DESTINO" | cut -f1)"
