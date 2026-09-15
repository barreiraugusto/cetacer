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
| `python manage.py test` | Corre las 51 pruebas. |

## Estructura

```
config/          Configuración del proyecto
cuentas/         Usuario propio y jerarquía de roles (grupos de Django)
cursos/          Categorías, cursos, comisiones y configuración del sitio
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

## Diseño

La web pública reproduce la maqueta aprobada: azul institucional `#0f2744`, azul de
acento `#1b55d4`, verde de WhatsApp `#16a34a`, tipografía Source Sans 3, esquinas de
4 px y ancho de contenido de 1160 px. El panel usa la misma paleta y tipografía.
Los tokens están al principio de `static/css/web.css` y `static/css/panel.css`.
