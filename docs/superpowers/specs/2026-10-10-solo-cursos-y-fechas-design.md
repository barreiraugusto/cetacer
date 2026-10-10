# Panel reducido a cursos y fechas — diseño

Fecha: 2026-10-10. Origen: reunión con CETACER del 10/10/2026 y aclaraciones de Augusto.

## Por qué

CETACER no va a llevar en el sitio el registro de quienes hacen los cursos: ya
lo cargan, de a uno, en el sistema nacional de la fundación, y repetirlo acá es
doble trabajo. El panel les resultó complejo («tiqui, tiqui, adivinando»).
Necesitan sólo tres cosas: mantener los cursos, subir fechas y marcar cada fecha
como disponible o completa.

Resultado buscado: quien atiende puede subir una fecha y marcarla completa sin
ayuda, y el conductor ve en la web, de un vistazo, qué fechas tienen lugar.

## Qué se elimina

- **La app `inscripciones` completa**: modelos `Empresa`, `Participante` e
  `Inscripcion`, su admin, sus pruebas y sus tablas (también en producción).
- **Del panel**: Inscripciones, Participantes, Empresas e Informes; «Inscribir a
  alguien», la lista de participantes, la asistencia, la planilla de firmas y
  todas las exportaciones (`panel/exportaciones.py`, y `openpyxl` si no le queda
  otro uso).
- **De cada fecha** (`Comision`): `cupo`, `instructor`, `estado` y
  `observaciones`, con todo lo que se calculaba a partir de inscriptos
  (lugares disponibles, porcentaje de ocupación, semáforo).
- **De cada curso**: `cupo_sugerido` y `cupo_texto`. La web deja de mostrar el
  dato «CUPO».
- **Roles** Coordinación, Recepción e Instructor.

## Fechas (antes «Comisiones»)

En todo lo que ve el usuario, «comisión» pasa a llamarse **fecha**: menú
«Fechas», botón «+ Nueva fecha», direcciones `/panel/fechas/…`. La clase del
modelo sigue llamándose `Comision` para no renombrar tabla y relaciones; cambian
sus `verbose_name`.

Campos que quedan: curso, fecha de inicio, fecha de finalización (opcional),
hora de inicio y de fin (opcionales), lugar (opcional; vacío usa la sede) y dos
casillas:

- **Visible en la web** (`visible`, tildada por defecto). Destildada, la fecha
  queda guardada pero no se publica. Reemplaza a Borrador y a Cancelada.
- **Completo** (`completa`, destildada por defecto; es el actual `cerrada`).
  Una fecha visible se muestra «Disponible» hasta que se tilda.

Una fecha nueva queda publicada al guardar. Se puede eliminar siempre, con
confirmación. Las fechas dejan de verse en la web solas cuando pasa su día de
inicio (igual que hoy); en el panel siguen en la pestaña «Pasadas».

Migración de datos, antes de borrar los campos viejos:

- `visible` = el estado era Publicada o En curso.
- `completa` = estaba marcada como completa, o los inscriptos alcanzaban el cupo.

**Listado del panel.** Pestañas «Próximas» y «Pasadas», siempre ordenadas por
fecha. Cada fila: curso, fecha, horario, un distintivo verde «Disponible» o rojo
«Completo» (gris «Oculta» si no es visible) y tres acciones: **Marcar completa /
Marcar disponible** y **Ocultar / Publicar**, que cambian el estado con un clic
sin abrir el formulario, y **Editar**. Desaparece la pantalla de detalle.

**Arreglo incluido.** Al editar una fecha, los campos de fecha aparecen vacíos:
el formulario los entrega en formato local y el selector del navegador exige
año-mes-día. Se corrige el formato y se cubre con una prueba.

## Agenda y Tablero

- **Agenda**: queda. Cada recuadro muestra el curso con el color de su estado
  (verde disponible, rojo completo, gris oculta) y lleva a editar la fecha.
- **Tablero**: tres indicadores (fechas publicadas próximas, completas y
  ocultas) y la lista de las próximas fechas con las mismas acciones rápidas del
  listado. Se van los indicadores de inscriptos, pagos y solicitudes web, la
  demanda por categoría y las últimas inscripciones.

## Roles

Quedan dos:

- **Dirección**: todo, incluidos usuarios y configuración del sitio.
- **Administración**: cursos, categorías, fechas y páginas.

Migración: los usuarios de Coordinación pasan a Administración. Los de Recepción
e Instructor quedan sin rol —no pueden entrar— y figuran en «Sin rol asignado»
para que Dirección decida. Se borran los tres grupos.

## Web pública

**Estado de cada fecha.** En la tarjeta del curso y en su ficha, cada fecha
lleva un recuadro de fondo **verde «Disponible»** o **rojo «Completo»**, en
lugar de «25 lugares» o «quedan 11 lugares». Se va la barra de ocupación.

**Cursos agrupados en bloques.** Cada categoría es un bloque con su título, su
ícono y un color de acento propio, y dentro una fila de botones, uno por curso:

- Cargas Generales: Inicial · Renovación · Ampliación
- Mercancías Peligrosas: Primera vez · Renovación
- Transporte de Pasajeros: sus cursos, cuando tenga alguno visible

Sin tocar nada se ven todos los cursos. Al tocar un botón se ve sólo ese curso,
con sus fechas, «Pedir turno» y «Ver requisitos completos»; al volver a tocarlo
se ven todos otra vez. Funciona sin recargar y la dirección queda compartible
(`?curso=…`). Reemplaza a los filtros por categoría de hoy.

Para el texto del botón, cada curso suma un campo **«nombre corto»**; vacío, se
usa el nombre completo.

Migración de datos: los cursos de las categorías «Renovación» y «Ampliación»
pasan a «Cargas Generales» con nombre corto «Renovación» y «Ampliación», el
curso inicial de Cargas Generales recibe «Inicial», los de Mercancías Peligrosas
«Primera vez» y «Renovación», y las dos categorías que quedan vacías se ocultan.
Se busca por identificador y, si algo no está, se saltea sin fallar.

**Logo.** En el encabezado, el logo con el 60 va más grande y acompañado de
«Cámara Empresaria del Transporte Automotor de Cargas de Entre Ríos», legible
también en el celular.

## Manual y datos de ejemplo

- «Cómo se usa» se reescribe para lo que queda: ingresar, agenda, cursos y
  categorías, fechas, páginas, usuarios y configuración, referencia. Se retoman
  las capturas.
- `cargar_datos` deja de crear participantes, empresas e inscripciones, y crea
  sólo los dos roles. El README se actualiza.

## Publicación

Las migraciones borran tablas y columnas y no tienen vuelta atrás. Antes del
deploy se corre `deploy/backup.sh` en el VPS y se confirma que el respaldo quedó.

## Pruebas

- Modelo: `visible`/`completa`, fechas pasadas fuera de la web, orden por fecha.
- Migraciones de datos: estado → visible, cupo lleno → completa, reagrupado de
  categorías, roles.
- Panel: alta de fecha publicada por defecto, edición que conserva las fechas,
  acciones rápidas, permisos de los dos roles, direcciones eliminadas dan 404.
- Web: distintivo Disponible/Completo, bloques y botones por curso, `?curso=`.
- Manual: capítulos y capturas existentes.

## Fuera de alcance

El asistente de WhatsApp con IA del que se habló en la reunión.
