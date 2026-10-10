# CETACER — sitio web y panel de capacitación

Sitio público y panel de administración para la Cámara Empresaria del Transporte
Automotor de Cargas de Entre Ríos. Reemplaza el sitio anterior y suma un panel
para mantener los cursos y subir sus fechas, marcando cuáles están completas.

El sitio no lleva el registro de quienes cursan: CETACER lo carga en el sistema
nacional de la fundación.

## Puesta en marcha

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py cargar_datos --demo    # catálogo real + datos de prueba
python manage.py runserver
```

- Web pública: http://127.0.0.1:8000/
- Panel: http://127.0.0.1:8000/panel/

`cargar_datos` crea un usuario por rol con la contraseña `cetacer2024`
(`direccion` y `administracion`). Sin `--demo` sólo carga el catálogo y los
usuarios, sin fechas de prueba.

**Cambiá esas contraseñas antes de poner el sitio en producción.**

## Comandos propios

| Comando | Para qué sirve |
|---|---|
| `python manage.py init_roles` | Crea o actualiza los grupos de los dos roles con sus permisos. Es idempotente: corrélo de nuevo después de agregar modelos. |
| `python manage.py cargar_datos` | Carga el catálogo real de cursos y un usuario por rol. |
| `python manage.py cargar_datos --demo` | Suma fechas de prueba, pasadas y futuras. |
| `python manage.py test` | Corre las pruebas. |

## Estructura

```
config/          Configuración del proyecto
cuentas/         Usuario propio y jerarquía de roles (grupos de Django)
cursos/          Categorías, cursos, fechas y configuración del sitio
contenido/       Páginas institucionales de enlaces, editables desde el panel
inscripciones/   Sólo migraciones históricas: el registro de personas se eliminó
panel/           Panel de administración (vistas y formularios)
web/             Sitio público
templates/       Plantillas (web/ y panel/)
static/css/      web.css y panel.css
```

### Cómo se relacionan los datos

- **Categoría** — un bloque de la web (Cargas Generales, Mercancías Peligrosas).
- **Curso** — lo que se dicta: nombre, precio, requisitos. No tiene día. Su
  «nombre corto» es el texto de su botón en la web.
- **Fecha** — un día concreto en que se dicta ese curso. En el código es el
  modelo `Comision`; el nombre quedó de cuando además llevaba cupo e inscriptos.

Cada fecha tiene dos casillas: **visible en la web** y **completo**. La web la
muestra como «Disponible» hasta que se marca completa, y deja de mostrarla sola
cuando pasa su día de inicio.

## Jerarquía de usuarios

Se apoya en los grupos nativos de Django. La matriz de permisos vive en
`cuentas/permisos.py` y se aplica con `init_roles`.

| Rol | Alcance |
|---|---|
| Dirección | Todo, incluidos usuarios y configuración del sitio. |
| Administración | Cursos, categorías, fechas y páginas. |

## Páginas de contenido

Legislación e Información útil son páginas cargadas desde el panel
(**Páginas**), no código. Cada una es un título, una bajada y una lista de
enlaces que pueden ser externos o documentos subidos.

Subí como documento todo lo que importe. Los enlaces a sitios ajenos se
pudren: de los 17 que tenía el sitio anterior, 9 ya estaban muertos cuando se
migró el contenido, incluido un PDF de FADEEAC.

Los archivos van a `media/documentos/`, que está fuera del control de versiones:
en una instalación nueva hay que volver a subirlos desde el panel.

`cargar_datos` siembra sólo las páginas que no existen: si la página ya está en
la base, el comando no la toca ni a ella ni a sus enlaces. Esto protege lo que
el administrador haya curado desde el panel. Un enlace nuevo agregado a la
constante de páginas no se propaga automáticamente a una base ya sembrada: hay
que cargarlo desde el panel.

## Producción

Definí las variables de `.env.example` como variables de entorno. Con
`DJANGO_DEBUG=False` el proyecto activa HSTS, cookies seguras y sirve los estáticos
con whitenoise (hay que correr `collectstatic`).

```bash
export DJANGO_SECRET_KEY="una-clave-larga-y-aleatoria-de-50-caracteres-o-mas"
export DJANGO_DEBUG=False
export DJANGO_ALLOWED_HOSTS=cetacer.com,www.cetacer.com
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Por defecto usa SQLite. Para PostgreSQL, definí `DATABASE_URL`.

### Sitio sin certificado

`DJANGO_HTTPS=False` apaga HSTS, la redirección a HTTPS y las cookies seguras.
Hace falta sólo mientras el sitio se sirve por IP: con las cookies marcadas como
seguras el navegador no las manda por HTTP y no se puede ni entrar al panel ni
enviar un formulario. Mientras esté apagado **la sesión viaja sin cifrar**. En
cuanto el dominio tenga certificado hay que volver a ponerlo en `True`.

### Servidor

`deploy/` tiene lo necesario para un VPS con nginx, gunicorn y PostgreSQL:

| Archivo | Para qué |
| --- | --- |
| `cetacer.service` | Unidad de systemd. Va a `/etc/systemd/system/`. |
| `nginx-cetacer.conf` | Proxy inverso. Va a `/etc/nginx/sites-available/cetacer`. |
| `actualizar.sh` | Despliega una versión nueva: pull, dependencias, migraciones, estáticos y reinicio. |
| `backup.sh` | Copia la base y `media/`, verifica que se puedan leer y rota las viejas. |
| `cetacer-backup.service` y `.timer` | Disparan esa copia todos los días a las 3:30. |
| `monitor.sh` | Chequea disco, aplicación, base, certificado y copias, y avisa por Telegram. |
| `cetacer-monitor.service` y `.timer` | Disparan esos chequeos cada 10 minutos. |

La instalación queda así:

```
/srv/cetacer/.env        variables de entorno (chmod 600)
/srv/cetacer/app/        el repositorio
/srv/cetacer/venv/       el entorno virtual
```

Para publicar cambios, desde el servidor:

```bash
bash /srv/cetacer/app/deploy/actualizar.sh
```

Los estáticos los sirve whitenoise desde la propia aplicación; nginx sólo se
encarga de `/media/`, que whitenoise no cubre.

El certificado es de Let's Encrypt y lo gestiona certbot, que agregó el bloque
443 a la copia instalada de la configuración de nginx y renueva solo con
`certbot.timer`. Si se reinstala `nginx-cetacer.conf` desde el repositorio hay
que volver a correr `certbot --nginx -d cetacer.com -d www.cetacer.com`.

### Copias de seguridad

`cetacer-backup.timer` corre `backup.sh` todos los días a las 3:30. Deja en
`/var/backups/cetacer/` un dump de PostgreSQL en formato `custom` y un `.tar.gz`
de `media/`, conserva 14 copias diarias y una por mes durante un año, y verifica
cada copia antes de darla por buena.

```bash
systemctl list-timers cetacer-backup    # cuándo corre la próxima
systemctl start cetacer-backup          # correr una ahora
journalctl -u cetacer-backup -n 30      # cómo fue la última
```

Las copias quedan **en el mismo servidor**: eso cubre un borrado accidental o
una migración que salga mal, no la pérdida del VPS. Para eso hay que bajarlas a
otra máquina, por ejemplo desde una tarea local:

```bash
rsync -az cetacer-vps:/var/backups/cetacer/ ~/backups-cetacer/
```

Para restaurar la base en el servidor:

```bash
systemctl stop cetacer
runuser -u postgres -- dropdb cetacer
runuser -u postgres -- createdb -O cetacer cetacer
runuser -u postgres -- pg_restore -d cetacer /var/backups/cetacer/diarias/base-FECHA.dump
systemctl start cetacer
```

Y los archivos subidos:

```bash
tar xzf /var/backups/cetacer/diarias/media-FECHA.tar.gz -C /srv/cetacer/app
chown -R cetacer:cetacer /srv/cetacer/app/media
```

### Monitoreo y alertas

`cetacer-monitor.timer` corre `monitor.sh` cada 10 minutos y avisa por Telegram si:

| Clave | Qué chequea | Umbral por defecto |
| --- | --- | --- |
| `disco` | Uso del disco raíz. | 85 % |
| `app` | `GET /salud/` directo a gunicorn por su socket; la vista consulta la base. | distinto de 200 |
| `postgres` | `pg_isready` contra `DATABASE_URL`. | — |
| `sitio` | `GET https://cetacer.com/salud/` pasando por nginx, con el certificado verificado. | distinto de 200 |
| `certificado` | Días que le quedan al certificado (certbot renueva a los 30). | menos de 14 |
| `backup` | `cetacer-backup.service` terminó con error. | — |

Avisa cuando un problema aparece o se resuelve, no en cada corrida; si sigue
abierto, lo recuerda cada 2 horas. Para cambiar un umbral, agregar al servicio
una línea `Environment=UMBRAL_DISCO_PCT=90` (también `UMBRAL_CERT_DIAS` y
`RECORDATORIO_MIN`).

Puesta en marcha, una sola vez:

1. En Telegram, hablarle a **@BotFather** → `/newbot` y guardar el token. Después
   mandarle cualquier mensaje al bot desde la cuenta que va a recibir las
   alertas (o agregarlo a un grupo y escribir ahí): sin eso no puede escribirte.
2. Obtener el `chat_id` (negativo si es un grupo):

   ```bash
   curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | grep -o '"chat":{"id":-\?[0-9]*'
   ```

3. Agregar `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID` a `/srv/cetacer/.env`.
4. Probar e instalar, como root:

   ```bash
   bash /srv/cetacer/app/deploy/monitor.sh --prueba    # tiene que llegar un mensaje 🧪
   cp /srv/cetacer/app/deploy/cetacer-monitor.{service,timer} /etc/systemd/system/
   systemctl daemon-reload && systemctl enable --now cetacer-monitor.timer
   ```

```bash
systemctl list-timers cetacer-monitor   # cuándo corre la próxima
systemctl start cetacer-monitor         # correr los chequeos ahora
journalctl -u cetacer-monitor -n 30     # qué encontró en las últimas corridas
```

La corrida normal conviene lanzarla con `systemctl start` y no a mano como
root, para que el archivo de estado (`/var/lib/cetacer-monitor/estado`) quede a
nombre del usuario `cetacer`.

Si el VPS entero se apaga o pierde red, el script no corre y no avisa. Para eso
hace falta un monitor externo (UptimeRobot, Better Stack) apuntando a
`https://cetacer.com/salud/`, que devuelve 503 con la base caída.

## Diseño

La web pública usa la identidad institucional: azul `#1e2869` (el mismo del logo),
azul de acento `#2b3fa8` derivado de él, verde de WhatsApp `#16a34a`, tipografía
Source Sans 3, esquinas de 4 px y ancho de contenido de 1160 px. El panel usa la
misma paleta y tipografía.

El verde `#00ff00` de la marca vive sólo dentro del logo: como fondo no llega al
contraste mínimo con texto blanco.

Los logos están en `static/img/` en SVG (`logo-cetacer-color.svg` en el encabezado,
`logo-cetacer-blanco.svg` en el pie) y la foto de portada en WebP con respaldo JPG.
Los originales quedaron en `elementos/`.
Los tokens están al principio de `static/css/web.css` y `static/css/panel.css`.
