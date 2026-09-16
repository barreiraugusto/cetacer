# Migración del contenido alojado en el dominio viejo

**Fecha:** 2026-09-15
**Estado:** aprobado, listo para plan de implementación

## Problema

Tres lugares de la web nueva sacan al visitante hacia `cetacer.com`, el dominio
que va a desaparecer. Cuando caiga, esos enlaces quedan rotos y el contenido que
había del otro lado se pierde.

| Dónde | Enlace |
|---|---|
| `templates/web/curso.html:108` | `curso.link_externo` → `cetacer.com/curso-…` |
| `templates/web/inicio.html:59` | `cetacer.com/legislacion-2` |
| `templates/web/inicio.html:64` | `cetacer.com/informacion-util` |

No hay más. Los enlaces a FADEEAC y a SICAPRO apuntan a dominios de terceros que
siguen vivos y no se tocan.

## Relevamiento

Se descargó el HTML de las dos páginas y se verificó cada enlace con `curl`.
Dos hallazgos cambiaron el diseño respecto de la hipótesis inicial:

1. **Ningún archivo estaba alojado en `cetacer.com`.** Los PDF que ofrecía viven
   en FADEEAC y en sitios de gobierno. Lo que se pierde al caer el dominio es la
   *lista curada*, no los archivos.
2. **9 de los 16 enlaces ya están rotos.** Migrarlos tal cual sería importar
   enlaces muertos al sitio nuevo. La migración es también una curaduría.

### Legislación

| Enlace original | Estado | Resolución |
|---|---|---|
| fadeeac.org.ar | 200 | se mantiene |
| Ley 24449 — PDF en vialidad.gba.gov.ar | 200 | **espejado** como documento propio |
| Decreto 03307-07 MGJEOSP — entrerios.gov.ar | 404 | sin reemplazo · **a confirmar** |
| Artículo «Ley» — fadeeac index.php?id=74 | redirige al home | sin reemplazo · **a confirmar** |
| Ley 26363 — PDF en gob.gba.gov.ar | 404 | texto consolidado de la 24449 en Infoleg, que ya incorpora sus reformas · **a confirmar** |

### Información útil

| Enlace original | Estado | Resolución |
|---|---|---|
| Guía del transportista — PDF FADEEAC | 200 | **espejado** como documento propio |
| Checklist — PDF FADEEAC | 404 | se elimina |
| Qué debe saber un transportista — FADEEAC | 404 | se elimina |
| Consultas sobre multas — FADEEAC | 200 | se mantiene |
| Estudios económicos y costos — FADEEAC | 200 | se mantiene |
| Restricciones a la circulación — FADEEAC | 404 | se elimina |
| D. General de Vialidad | sin DNS | `argentina.gob.ar/transporte/vialidad-nacional` |
| Gendarmería Nacional | sin DNS | `argentina.gob.ar/gendarmeria` |
| Secretaría de Transporte | sin DNS | `argentina.gob.ar/transporte` |
| Registro Automotor | meta-refresh | `dnrpa.gov.ar/portal_dnrpa/` |
| IRU | 200 | se mantiene |
| Occovi | sin DNS | organismo disuelto, se elimina |

Los dos PDF sobrevivientes ya están descargados en `media/documentos/`. Que
FADEEAC haya dado de baja uno de sus propios PDF es la mejor justificación del
campo `archivo`: los enlaces a terceros se pudren, los documentos propios no.

## Decisiones

- **Alcance:** sólo los tres enlaces rotos. «Productos» y «Otras cámaras» del
  sitio viejo quedan afuera; el modelo es genérico, así que sumarlas después es
  cargar una página desde el panel, sin tocar código.
- **Cursos:** se elimina `link_externo`. La ficha nueva ya muestra más que la
  página vieja; lo único que faltaba era cómo pagar, y eso es igual para todos
  los cursos, así que va a la configuración del sitio.
- **Estructura de las páginas:** lista plana de enlaces con un campo `grupo` de
  texto libre. Cubre la lista simple de Legislación y la agrupada de Información
  útil con un solo modelo y una sola pantalla de carga.
- **Ubicación:** app nueva `contenido`. Hoy `cursos` ya carga con
  `ConfiguracionSitio`, que de cursos no tiene nada; sumarle las páginas
  institucionales la volvería un cajón de sastre.

## Modelo de datos

App nueva `contenido`, dos modelos.

### `Pagina`

| Campo | Tipo | Notas |
|---|---|---|
| `titulo` | `CharField(120)` | |
| `slug` | `SlugField(unique)` | se autogenera del título, patrón de `Curso.save()` |
| `bajada` | `TextField(blank)` | |
| `orden` | `PositiveIntegerField(0)` | |
| `publicada` | `BooleanField(True)` | despublicada ⇒ 404 en la web |
| `actualizado` | `DateTimeField(auto_now)` | |

Manager con `publicadas()`. `get_absolute_url()` → `web:pagina`.

### `EnlacePagina`

| Campo | Tipo | Notas |
|---|---|---|
| `pagina` | `FK(Pagina, related_name="enlaces")` | |
| `titulo` | `CharField(200)` | |
| `descripcion` | `CharField(300, blank)` | |
| `grupo` | `CharField(120, blank)` | encabezado opcional |
| `url` | `URLField(blank)` | enlace externo |
| `archivo` | `FileField(upload_to="documentos/", blank)` | documento propio |
| `orden` | `PositiveIntegerField(0)` | |
| `activo` | `BooleanField(True)` | |

- `clean()` exige **exactamente uno** de `url` / `archivo`. Ni ninguno ni los dos.
- `destino` devuelve `archivo.url` o `url`, para que la plantilla no decida.
- `es_documento` devuelve `bool(archivo)`, para marcar los PDF en la lista.
- `Meta.ordering = ["orden", "id"]`.

El agrupado se resuelve en el modelo o en la vista, no en la plantilla: una
función devuelve `[(grupo, [enlaces…]), …]` respetando el orden de aparición y
dejando primero los que no tienen grupo.

## Web pública

- Ruta `/info/<slug>/` → `web:pagina`. `get_object_or_404` sobre `publicadas()`.
- Plantilla `templates/web/pagina.html`, reusando los estilos de ficha que ya existen.
- `web/context_processors.py` suma un dict `paginas` (`{slug: Pagina}` de las
  publicadas), con el mismo `try/except` que ya protege a `sitio` durante las
  migraciones iniciales.
- Las tarjetas de `inicio.html` muestran su enlace sólo si la página existe y
  está publicada. Si alguien despublica Legislación, la tarjeta queda sin enlace
  en lugar de romperse.

## Cursos y formas de pago

`ConfiguracionSitio` suma cuatro campos:

| Campo | Valor inicial |
|---|---|
| `pago_alias` | `FPT.LICENCIAPROF` |
| `pago_banco` | `Banco Nación` |
| `pago_titular` | vacío · **a confirmar** |
| `pago_aclaracion` | `TextField(blank)`, para el instructivo de comprobantes |

Se muestran en la ficha del curso bajo el precio, que es donde el visitante los
busca, y se editan desde la pantalla de configuración que ya existe.

`Curso.link_externo` se elimina en la misma migración. Toca `panel/forms.py:47`,
`templates/panel/curso_form.html:52`, `curso.html:107-111` y las seis entradas
`"link"` de `cursos/management/commands/cargar_datos.py`.

## Panel

- Rutas `paginas/`, `paginas/nueva/`, `paginas/<pk>/`, `paginas/<pk>/eliminar/`.
- Una sola pantalla: el form de `Pagina` con un `inlineformset_factory` de
  enlaces debajo, siguiendo el patrón de `curso_form.html`.
- Entrada «Páginas» en el menú lateral, junto a Configuración.
- `cuentas/permisos.py`: Dirección y Administración `TODOS`, Coordinación y
  Recepción `LECTURA`, Instructor sin acceso. Mismo criterio que
  `cursos.configuracionsitio`, porque es contenido institucional.

## Datos iniciales

`cargar_datos` crea las dos páginas con los enlaces ya curados de la tabla de
relevamiento. Los dos PDF espejados se cargan si están presentes en
`media/documentos/`; si no están, el comando sigue sin fallar y deja los enlaces
de archivo sin crear.

**`media/` está en `.gitignore`.** Los PDF descargados no viajan en el repo: en
producción se suben desde el panel, que es el flujo previsto.

## Pruebas

Sobre las 51 existentes:

- `clean()` rechaza un enlace sin destino y uno con los dos destinos.
- El agrupado respeta el orden y ubica primero los enlaces sin grupo.
- La vista web devuelve 200 con página publicada y 404 con despublicada.
- El context processor no rompe si la tabla todavía no existe.
- La matriz de permisos: cada rol contra alta, edición y baja de páginas.
- **Regresión:** un test recorre `templates/` y falla si reaparece un `href`
  hacia `cetacer.com`. Es exactamente el bug que estamos arreglando.

## Fuera de alcance

- Mudar `ConfiguracionSitio` a `contenido`. Es refactor no relacionado y agrega
  riesgo de migración a un cambio que no lo necesita.
- Migrar «Productos» y «Otras cámaras».
- Editor de texto enriquecido.
- Menú de navegación configurable: las páginas se enlazan desde las tarjetas de
  inicio, no desde la barra superior.

## Pendientes de confirmación con CETACER

1. Titular de la cuenta bancaria del alias `FPT.LICENCIAPROF`.
2. Qué hacer con el decreto provincial 03307-07, hoy sin URL viva.
3. Si se reemplaza la Ley 26363 por el texto consolidado de la 24449 en Infoleg.
4. Si quieren recuperar el Checklist y «Qué debe saber un transportista», dados
   de baja por FADEEAC: habría que pedirles el archivo.
