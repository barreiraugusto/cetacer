#!/usr/bin/env bash
# Chequeos de salud del VPS con aviso por Telegram. Lo ejecuta
# cetacer-monitor.timer cada 10 minutos.
#
# Chequea:
#   - uso del disco raíz por encima de UMBRAL_DISCO_PCT
#   - /salud/ pedido directo a gunicorn por su socket (aplicación + base)
#   - PostgreSQL con pg_isready
#   - /salud/ pedido a través de nginx por HTTPS (proxy + certificado válido)
#   - certificado a menos de UMBRAL_CERT_DIAS de vencer (certbot no renovó)
#   - la última copia de seguridad (cetacer-backup.service) terminó con error
#
# No manda un mensaje por corrida: guarda los problemas vigentes en un archivo
# de estado y avisa sólo cuando cambian (aparece uno nuevo o se resuelve).
# Se comparan por clave ("disco", "certificado"), no por texto: el texto lleva
# números (97%, 12 días) que cambian solos y mandarían un aviso por corrida.
# Si un problema sigue abierto, recuerda cada RECORDATORIO_MIN minutos.
#
# Necesita en /srv/cetacer/.env:
#   TELEGRAM_BOT_TOKEN=123456:ABC...
#   TELEGRAM_CHAT_ID=123456789
#
# Uso:
#   bash /srv/cetacer/app/deploy/monitor.sh            # corrida normal
#   bash /srv/cetacer/app/deploy/monitor.sh --prueba   # manda un mensaje de prueba y sale
set -uo pipefail

RAIZ=/srv/cetacer
ARCHIVO_ENV="${ARCHIVO_ENV:-$RAIZ/.env}"
# El directorio lo crea systemd (StateDirectory) a nombre del usuario cetacer.
ARCHIVO_ESTADO="${ARCHIVO_ESTADO:-/var/lib/cetacer-monitor/estado}"

UMBRAL_DISCO_PCT="${UMBRAL_DISCO_PCT:-85}"
UMBRAL_CERT_DIAS="${UMBRAL_CERT_DIAS:-14}"
RECORDATORIO_MIN="${RECORDATORIO_MIN:-120}"
SOCKET_APP="${SOCKET_APP:-/run/cetacer/gunicorn.sock}"
UNIDAD_BACKUP="${UNIDAD_BACKUP:-cetacer-backup.service}"
TELEGRAM_API="${TELEGRAM_API:-https://api.telegram.org}"

if [[ -r "$ARCHIVO_ENV" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$ARCHIVO_ENV"
    set +a
fi

# Django rechaza (400) un Host que no esté en ALLOWED_HOSTS, así que los
# pedidos locales se hacen con el primero de la lista.
DOMINIO="${DJANGO_ALLOWED_HOSTS:-}"
DOMINIO="${DOMINIO%%,*}"
DOMINIO="${DOMINIO:-localhost}"
# Vacío (URL_SITIO=) saltea los chequeos por nginx y del certificado.
URL_SITIO="${URL_SITIO-https://$DOMINIO/salud/}"

ahora() { date '+%Y-%m-%d %H:%M:%S'; }

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
    echo "[$(ahora)] ERROR: faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID en $ARCHIVO_ENV" >&2
    exit 1
fi

enviar_telegram() {
    curl -sS -m 15 -o /dev/null -w '%{http_code}' \
        -X POST "$TELEGRAM_API/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
        --data-urlencode "text=$1" | grep -q '^200$'
}

SERVIDOR="$(hostname)"

if [[ "${1:-}" == "--prueba" ]]; then
    if enviar_telegram "🧪 Prueba del monitor de CETACER en $SERVIDOR: si ves esto, las alertas llegan."; then
        echo "[$(ahora)] Mensaje de prueba enviado."
        exit 0
    fi
    echo "[$(ahora)] ERROR: Telegram no aceptó el mensaje (revisar token y chat_id)." >&2
    exit 1
fi

# --- Chequeos: cada problema es una línea "clave|texto" en PROBLEMAS ----------
PROBLEMAS=()

USO_DISCO="$(df --output=pcent / | tail -n1 | tr -dc '0-9')"
if [[ -n "$USO_DISCO" && "$USO_DISCO" -ge "$UMBRAL_DISCO_PCT" ]]; then
    PROBLEMAS+=("disco|Disco al ${USO_DISCO}% (umbral ${UMBRAL_DISCO_PCT}%)")
fi

# X-Forwarded-Proto es el que pone nginx: sin él, SECURE_SSL_REDIRECT contesta
# 301 en vez de atender el pedido.
CODIGO_APP="$(curl -s -m 15 -o /dev/null -w '%{http_code}' \
    --unix-socket "$SOCKET_APP" \
    -H "Host: $DOMINIO" -H "X-Forwarded-Proto: https" \
    http://localhost/salud/)"
if [[ "$CODIGO_APP" != "200" ]]; then
    PROBLEMAS+=("app|La aplicación respondió ${CODIGO_APP:-000} en /salud/ (000 = gunicorn no responde, 503 = sin base)")
fi

if [[ "${DATABASE_URL:-}" == postgres* ]] && command -v pg_isready >/dev/null 2>&1; then
    if ! pg_isready -q -t 10 -d "$DATABASE_URL"; then
        PROBLEMAS+=("postgres|PostgreSQL no acepta conexiones")
    fi
fi

if [[ -n "$URL_SITIO" ]]; then
    # Con la aplicación caída nginx contesta 502 y sería el mismo problema
    # contado dos veces: por nginx se pregunta sólo si gunicorn respondió bien.
    # --resolve apunta el dominio a este mismo servidor sin soltar la
    # verificación del certificado.
    if [[ "$CODIGO_APP" == "200" ]]; then
        CODIGO_SITIO="$(curl -s -m 15 -o /dev/null -w '%{http_code}' \
            --resolve "$DOMINIO:443:127.0.0.1" "$URL_SITIO")"
        if [[ "$CODIGO_SITIO" != "200" ]]; then
            PROBLEMAS+=("sitio|$URL_SITIO respondió ${CODIGO_SITIO:-000} a través de nginx (000 = no responde o certificado inválido)")
        fi
    fi

    VENCE="$(timeout 10 openssl s_client -connect 127.0.0.1:443 -servername "$DOMINIO" </dev/null 2>/dev/null \
        | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)"
    if [[ -n "$VENCE" ]]; then
        DIAS_CERT=$(( ($(date -d "$VENCE" +%s) - $(date +%s)) / 86400 ))
        if [[ "$DIAS_CERT" -lt "$UMBRAL_CERT_DIAS" ]]; then
            PROBLEMAS+=("certificado|Al certificado de $DOMINIO le quedan ${DIAS_CERT} días (certbot no está renovando)")
        fi
    fi
fi

if systemctl is-failed --quiet "$UNIDAD_BACKUP" 2>/dev/null; then
    PROBLEMAS+=("backup|La última copia de seguridad falló (journalctl -u ${UNIDAD_BACKUP%.service})")
fi

# --- Comparar con la corrida anterior y avisar sólo si cambió -----------------
ACTUAL="$(printf '%s\n' "${PROBLEMAS[@]}" | sed '/^$/d' | sort)"
ANTERIOR="$(cat "$ARCHIVO_ESTADO" 2>/dev/null || true)"

claves() { cut -d'|' -f1 <<< "$1" | sed '/^$/d' | sort; }
vinetas() { cut -d'|' -f2- <<< "$1" | sed '/^$/d; s/^/• /'; }

MENSAJE=""
if [[ "$(claves "$ACTUAL")" != "$(claves "$ANTERIOR")" ]]; then
    if [[ -n "$ACTUAL" ]]; then
        MENSAJE="🔴 CETACER ($SERVIDOR) — problemas detectados:"$'\n'"$(vinetas "$ACTUAL")"
        CLAVES_RESUELTAS="$(comm -13 <(claves "$ACTUAL") <(claves "$ANTERIOR"))"
        if [[ -n "$CLAVES_RESUELTAS" ]]; then
            RESUELTOS="$(grep -F -f <(sed 's/$/|/' <<< "$CLAVES_RESUELTAS") <<< "$ANTERIOR")"
            MENSAJE+=$'\n\n'"✅ Resuelto:"$'\n'"$(vinetas "$RESUELTOS")"
        fi
    else
        MENSAJE="✅ CETACER ($SERVIDOR) — todo normal de nuevo. Resuelto:"$'\n'"$(vinetas "$ANTERIOR")"
    fi
elif [[ -n "$ACTUAL" && -n "$(find "$ARCHIVO_ESTADO" -mmin +"$RECORDATORIO_MIN" 2>/dev/null)" ]]; then
    MENSAJE="⏰ CETACER ($SERVIDOR) — siguen sin resolverse:"$'\n'"$(vinetas "$ACTUAL")"
fi

if [[ -z "$MENSAJE" ]]; then
    echo "[$(ahora)] Sin cambios (${#PROBLEMAS[@]} problema/s abierto/s)."
    exit 0
fi

if enviar_telegram "$MENSAJE"; then
    # El estado se guarda sólo si el aviso salió: si Telegram falla, la próxima
    # corrida lo vuelve a intentar. Escribirlo de nuevo reinicia el recordatorio.
    mkdir -p "$(dirname "$ARCHIVO_ESTADO")"
    printf '%s' "$ACTUAL" > "$ARCHIVO_ESTADO.parcial" && mv "$ARCHIVO_ESTADO.parcial" "$ARCHIVO_ESTADO"
    echo "[$(ahora)] Aviso enviado:"$'\n'"$MENSAJE"
else
    echo "[$(ahora)] ERROR: no se pudo enviar el aviso a Telegram:"$'\n'"$MENSAJE" >&2
    exit 1
fi
