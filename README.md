# CETACER — sitio web y panel de capacitación

Sitio público y panel de administración para la Cámara Empresaria del Transporte
Automotor de Cargas de Entre Ríos. Reemplaza el sitio actual (cetacer.com) y suma
la gestión de cursos, fechas, inscriptos y exportación de listas de participantes.

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
(`direccion`, `administracion`, `coordinacion`, `recepcion`, `instructor`).
Sin `--demo` sólo carga el catálogo y los usuarios, sin inscriptos de prueba.

**Cambiá esas contraseñas antes de poner el sitio en producción.**

## Comandos propios

| Comando | Para qué sirve |
|---|---|
| `python manage.py init_roles` | Crea o actualiza los cinco grupos con sus permisos. Es idempotente: corrélo de nuevo después de agregar modelos. |
| `python manage.py cargar_datos` | Carga el catálogo real de cursos y un usuario por rol. |
| `python manage.py cargar_datos --demo` | Suma comisiones, participantes e inscripciones de prueba. |
| `python manage.py test` | Corre las 94 pruebas. |

## Estructura

```
config/          Configuración del proyecto
cuentas/         Usuario propio y jerarquía de roles (grupos de Django)
cursos/          Categorías, cursos, comisiones y configuración del sitio
contenido/       Páginas institucionales de enlaces, editables desde el panel
inscripciones/   Empresas, participantes e inscripciones
panel/           Panel de administración (vistas, formularios, exportaciones)
web/             Sitio público
templates/       Plantillas (web/ y panel/)
static/css/      web.css y panel.css
```

### Cómo se relacionan los datos

- **Curso** — lo que se dicta: nombre, precio, requisitos. No tiene fecha.
- **Comisión** — un dictado concreto de ese curso: fecha, horario, cupo e instructor.
- **Participante** — la persona, identificada por DNI y reutilizada entre cursos.
- **Inscripción** — une un participante con una comisión, con su estado y su pago.

Separar curso de comisión es lo que permite repetir el mismo curso todos los meses
sin volver a cargar precio ni requisitos, y tener el historial de quién cursó qué.

## Jerarquía de usuarios

Se apoya en los grupos nativos de Django. La matriz de permisos vive en
`cuentas/permisos.py` y se aplica con `init_roles`.

| Rol | Alcance |
|---|---|
| Dirección | Todo, incluidos usuarios y configuración del sitio. |
| Administración | Catálogo completo, precios, comisiones, inscripciones y exportaciones. |
| Coordinación | Comisiones, instructores e inscripciones. No toca precios ni usuarios. |
| Recepción | Carga participantes, toma inscripciones y descarga listas. |
| Instructor | Sólo sus comisiones asignadas, para tomar asistencia. |

Un instructor no ve las comisiones de otros: la consulta se filtra en
`panel/accesos.py::comisiones_visibles`.

## Exportaciones

Todas salen en Excel (.xlsx) y en CSV, y siempre respetan los filtros que haya
puestos en pantalla.

- **Lista de participantes de una comisión** — con encabezado institucional, curso,
  fecha, lugar y cupo.
- **Planilla de firmas** — la misma lista con columnas en blanco para firmar el día
  del curso.
- **Listado general de inscripciones** — con filtros por curso, estado, pago y fechas.
- **Padrón de participantes** — una fila por persona, con la cantidad de cursos hechos.

El CSV se genera con punto y coma y un único BOM para que Excel en español lo abra
bien al hacer doble clic.

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
encarga de `/media/`, que whitenoise no cubre. `media/` no está en el
repositorio: lo que se sube desde el panel vive únicamente en el servidor y hay
que respaldarlo aparte, junto con la base.

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
