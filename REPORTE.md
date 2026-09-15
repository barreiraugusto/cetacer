# Reporte — Sitio web y panel de administración de CETACER

**Proyecto:** reemplazo de cetacer.com con gestión de cursos e inscriptos
**Stack:** Django 5.2 · Python 3.11 · SQLite (PostgreSQL opcional) · openpyxl
**Estado:** funcional y probado — 51 pruebas automatizadas en verde

---

## 1. Qué se pidió y qué se entregó

| Pedido | Entregado |
|---|---|
| Proyecto Django para mostrar y administrar la web | Proyecto completo con 5 aplicaciones, web pública y panel |
| Panel estilo dashboard, lo más didáctico posible | Panel con tablero de indicadores, avisos accionables, textos de ayuda en cada pantalla y una sección «Cómo se usa» |
| Exportar listas de participantes | Cuatro exportaciones distintas, en Excel y CSV |
| Modificar la información de los cursos | ABM completo de categorías, cursos y comisiones, más la configuración del sitio |
| Sistema de usuarios con jerarquías usando grupos de Django | Cinco roles sobre `django.contrib.auth.Group`, con matriz de permisos declarativa |
| Respetar la estética del HTML entregado | Paleta, tipografía y medidas replicadas token por token |

---

## 2. La decisión de fondo: separar *curso* de *comisión*

El HTML original guardaba las fechas como texto libre dentro de cada curso
(`fechas: ["Consultar fechas del mes en curso"]`), en el `localStorage` del navegador.
Eso alcanza para mostrar, pero no para administrar: no permite saber quién se anotó,
ni controlar el cupo, ni exportar una lista.

El modelo de datos separa las dos cosas:

- **Curso** — lo que se dicta. Nombre, precio, requisitos, descripción. No tiene fecha.
- **Comisión** — un dictado concreto de ese curso. Fecha, horario, cupo, instructor
  y su propia lista de inscriptos.

Esto es lo que hace posible todo lo demás: repetir el mismo curso todos los meses sin
recargar precio ni requisitos, controlar el cupo por fecha, y conservar el historial de
quién cursó qué. Las fechas que la web muestra en cada tarjeta salen solas de las
comisiones publicadas.

A eso se suman:

- **Participante** — la persona, identificada por DNI, reutilizada entre cursos.
  Es el padrón: un camionero que hace el básico y tres años después la renovación es
  la misma ficha, con su historial.
- **Inscripción** — une un participante con una comisión. Lleva el estado
  (preinscripto, confirmado, asistió, ausente, cancelada), el estado del pago, el
  comprobante y si tiene el psicofísico y la documentación al día.
- **Empresa** — la empresa de transporte que manda gente, para los informes.
- **ConfiguracionSitio** — los textos y datos de contacto de la web, editables desde
  el panel sin tocar código.

Una restricción de base de datos impide inscribir dos veces a la misma persona en la
misma comisión, y las inscripciones canceladas liberan el lugar en el cupo.

---

## 3. Jerarquía de usuarios

Implementada con los grupos nativos de Django, como se pidió. La matriz de permisos
está declarada en un solo archivo (`cuentas/permisos.py`) y se aplica con
`python manage.py init_roles`, que es idempotente.

| # | Rol | Qué puede hacer |
|---|---|---|
| 1 | **Dirección** | Todo, incluidos usuarios y configuración del sitio |
| 2 | **Administración** | Catálogo completo, precios, comisiones, inscripciones y exportaciones |
| 3 | **Coordinación** | Arma comisiones y asigna instructores. No edita precios ni usuarios |
| 4 | **Recepción** | Carga participantes, toma inscripciones y descarga listas |
| 5 | **Instructor** | Sólo sus comisiones asignadas, para tomar asistencia |

Dos mecanismos sostienen esto:

- **Jerarquía por nivel.** `usuario.alcanza(Rol.RECEPCION)` es verdadero para
  Recepción y para todos los roles por encima. Las vistas se protegen con un
  decorador que expresa el nivel mínimo, no una lista de roles.
- **Filtrado por pertenencia.** Un instructor no ve las comisiones de otro: la
  consulta se filtra antes de llegar a la vista. Pedir la URL de una comisión ajena
  devuelve 404, no un error de permisos — no se filtra ni la existencia.

La pantalla «Usuarios y permisos» muestra los cinco roles con su descripción y quién
está en cada uno, así que la jerarquía se explica sola, sin manual.

---

## 4. El panel, pensado para el mostrador

La prioridad fue que alguien que atiende el teléfono pueda anotar a una persona en
menos de veinte segundos, sin capacitación previa.

**Tablero.** Cuatro indicadores (comisiones abiertas, inscriptos de los próximos 30
días, pagos pendientes, solicitudes web sin confirmar) y, debajo, avisos accionables:
«esta comisión sigue en borrador y arranca en 6 días», con el botón para resolverlo.
No informa: señala qué hacer.

**Ficha de comisión.** Es la pantalla que más se va a usar. Arriba, el estado del cupo
con su barra. Después, un formulario de una sola línea: se escribe el DNI y, si la
persona ya cursó, el sistema la reconoce; si es nueva, pide apellido y nombre. Abajo,
la lista de inscriptos con una columna «Falta» que dice de un vistazo qué le falta a
cada uno (pago, psicofísico, documentación).

**Agenda.** Calendario mensual con las comisiones y su ocupación. Las que están en
borrador se ven en gris, para distinguir de un vistazo lo publicado de lo que no.

**Vocabulario en español rioplatense.** Comisión, cupo, participante, turno. La
interfaz habla como habla la gente de la institución, no como habla un sistema.

**Ayuda incorporada.** Cada formulario explica en dos líneas para qué sirve lo que se
está cargando, y hay una sección «Cómo se usa» con las tres tareas de todos los días
paso a paso, el glosario y el significado de los colores.

---

## 5. Exportaciones

Cuatro salidas distintas, todas en Excel (.xlsx) y CSV, y todas respetando los
filtros que haya aplicados en pantalla:

1. **Lista de participantes de una comisión** — 18 columnas, con encabezado
   institucional, curso, fecha, lugar, cupo e instructor. Filtros automáticos y
   primera fila congelada.
2. **Planilla de firmas** — la misma lista reducida, con las columnas «Firma» y
   «Aclaración» en blanco para imprimir y hacer firmar el día del curso.
3. **Listado general de inscripciones** — para cruzar varios cursos y períodos.
4. **Padrón de participantes** — una fila por persona, con la cantidad de cursos
   realizados.

Dos detalles que suelen fallar y acá están resueltos: el CSV sale con punto y coma y
un único BOM, para que Excel en español lo abra bien al hacer doble clic; y las
inscripciones canceladas quedan fuera de la lista por defecto, sin que haya que
filtrarlas a mano.

---

## 6. La web pública

Reproduce la maqueta entregada respetando la paleta y las medidas: azul institucional
`#0f2744`, azul de acento `#1b55d4`, verde de WhatsApp `#16a34a`, tipografía
Source Sans 3, esquinas de 4 px y ancho de contenido de 1160 px. Los tokens están al
principio de `static/css/web.css`; cambiarlos ahí retiñe todo el sitio.

Lo que en el HTML original eran datos fijos ahora sale de la base:

- Las tarjetas de curso muestran el precio, los requisitos y las **fechas reales** de
  las comisiones publicadas, con los lugares que quedan. Una fecha completa se marca
  como tal.
- El botón «Pedir turno» arma el mensaje de WhatsApp con el nombre del curso ya escrito.
- Los filtros por categoría funcionan del lado del servidor.

Se agregaron dos cosas que el HTML no tenía:

- **Ficha individual de cada curso**, con la tabla de fechas, la ocupación de cada
  comisión y el detalle de requisitos.
- **Reserva de lugar online** (opcional, se apaga desde la configuración). Entra al
  panel como «preinscripta» con origen «web» y aparece en el tablero como pendiente de
  confirmar. No reemplaza al WhatsApp, que sigue siendo el canal principal: lo
  complementa para quien prefiere dejar los datos a cualquier hora.

El modo administración del HTML original —que editaba los cursos en el `localStorage`
del navegador— se reemplazó por el panel. Aquellos cambios sólo existían en la
computadora de quien los hacía y se perdían al limpiar el navegador.

---

## 7. Verificación

**51 pruebas automatizadas, todas en verde.** Cubren:

- La jerarquía de roles: que `alcanza()` respete el orden, que asignar un rol reemplace
  el anterior, que un superusuario sea siempre Dirección.
- El cupo: que las canceladas no lo ocupen, que no se pueda pasarse del límite, que el
  semáforo cambie de color.
- Los permisos, rol por rol: que Coordinación no edite precios, que Recepción no cree
  comisiones, que sólo Dirección administre usuarios, que un instructor reciba 404 en
  una comisión ajena.
- Las exportaciones: que el Excel traiga el encabezado y una fila por persona, que el
  CSV tenga un solo BOM, que las canceladas queden fuera, que los filtros se respeten.
- La web pública: que un curso desactivado no aparezca, que la preinscripción cree la
  persona y la inscripción, que no deje reservar en una comisión completa.

**Recorrido completo de rutas.** Las 33 rutas del panel se probaron con los cinco
roles: sin errores 4xx ni 5xx, y con el corte de permisos donde corresponde
(Dirección accede a 33, Instructor a 19).

**Revisión visual.** Se renderizaron las pantallas en Chromium y se compararon contra
la maqueta.

**`check --deploy`** pasa limpio salvo dos avisos esperables: la clave secreta de
prueba (se define por variable de entorno en producción) y el *preload* de HSTS, que
es una decisión del titular del dominio.

### Dos errores encontrados y corregidos durante la revisión

- **BOM repetido en los CSV.** Declarar `charset=utf-8-sig` hacía que Django
  antepusiera el BOM en *cada* escritura, no sólo al principio: Excel mostraba basura
  al inicio de cada línea. Se declara `utf-8` y el BOM se escribe una sola vez.
- **Plurales rotos en español.** El filtro `pluralize` de Django agrega letras al
  final, y en palabras con tilde en la última sílaba producía «comisiónes» e
  «inscripciónes». Se agregó un filtro propio que usa la forma correcta.

---

## 8. Tamaño y estructura

| | |
|---|---|
| Código Python | ~3.500 líneas (sin migraciones) |
| Plantillas HTML | ~2.200 líneas |
| CSS | 735 líneas, con tokens al principio de cada archivo |
| Pruebas | 51 |
| Dependencias | 3 (Django, openpyxl, whitenoise) |

Sin JavaScript de terceros, sin build, sin `node_modules`. El panel es HTML renderizado
en el servidor: una interfaz así se mantiene con Django solo, y quien la herede no
necesita saber un framework de frontend para tocarla.

---

## 9. Para poner en marcha

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py cargar_datos --demo
python manage.py runserver
```

Usuarios de prueba, uno por rol, con contraseña `cetacer2024`: `direccion`,
`administracion`, `coordinacion`, `recepcion`, `instructor`.
**Hay que cambiarlas antes de publicar el sitio.**

El catálogo cargado es el real (los seis cursos con sus precios y requisitos, tomados
del HTML entregado). Con `--demo` se agregan comisiones e inscriptos falsos para poder
ver el panel con datos; sin ese modificador, el catálogo queda limpio para empezar a
cargar las fechas verdaderas.

---

## 10. Qué conviene definir antes de salir a producción

Cosas que quedaron resueltas con un criterio razonable, pero que la institución
debería confirmar:

1. **La reserva online.** Está activada. Si prefieren que los turnos sigan siendo
   sólo por WhatsApp, se apaga con una casilla en Configuración; la web vuelve a
   ofrecer únicamente el botón verde.
2. **Los precios.** Se cargaron los del HTML entregado. Conviene verificarlos antes
   de publicar, porque ahora se muestran desde la base y no a mano.
3. **Aviso automático al inscripto.** Hoy la confirmación se hace por WhatsApp a
   mano. Si quieren un correo automático al confirmar la inscripción, es un agregado
   acotado sobre lo que ya está.
4. **Certificados.** El sistema ya sabe quién asistió a qué; emitir el certificado en
   PDF desde la ficha de la comisión sería el siguiente paso natural.
5. **Base de datos.** SQLite alcanza para el volumen actual (un puñado de cursos por
   mes). Si en algún momento hace falta, el cambio a PostgreSQL es definir una
   variable de entorno.
