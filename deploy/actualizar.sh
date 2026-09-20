#!/usr/bin/env bash
# Actualiza el sitio ya instalado: trae el código, instala dependencias,
# aplica migraciones, recolecta estáticos y reinicia el servicio.
# Se ejecuta como root en el servidor:  bash /srv/cetacer/app/deploy/actualizar.sh
set -euo pipefail

RAIZ=/srv/cetacer
APP="$RAIZ/app"
VENV="$RAIZ/venv"
USUARIO=cetacer

como_app() { runuser -u "$USUARIO" -- "$@"; }

# Las variables de entorno del .env hacen falta para migrate y collectstatic.
set -a
# shellcheck disable=SC1091
source "$RAIZ/.env"
set +a

echo "==> Trayendo el código"
como_app git -C "$APP" pull --ff-only

echo "==> Dependencias"
como_app "$VENV/bin/pip" install --quiet --upgrade -r "$APP/requirements.txt"

echo "==> Migraciones"
como_app "$VENV/bin/python" "$APP/manage.py" migrate --noinput

echo "==> Estáticos"
como_app "$VENV/bin/python" "$APP/manage.py" collectstatic --noinput

echo "==> Comprobaciones de producción"
como_app "$VENV/bin/python" "$APP/manage.py" check --deploy

echo "==> Reiniciando"
systemctl restart cetacer
sleep 2
systemctl is-active --quiet cetacer && echo "Listo: servicio activo" || {
    echo "El servicio no quedó activo. Últimas líneas del log:" >&2
    journalctl -u cetacer -n 30 --no-pager >&2
    exit 1
}
