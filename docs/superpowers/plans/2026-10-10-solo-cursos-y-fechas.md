# Panel reducido a cursos y fechas — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sacar del sitio todo el registro de personas y dejar un panel con cursos y fechas, donde cada fecha se muestra «Disponible» o «Completo».

**Architecture:** `Comision` conserva su nombre de clase pero pierde cupo, instructor y estado: quedan dos booleanos, `visible` y `completa`. La app `inscripciones` queda como cáscara con sólo sus migraciones (hace falta la que borra las tablas). La web agrupa por categoría y filtra por curso. Los roles bajan a dos.

**Tech Stack:** Django 5.2, SQLite en desarrollo y PostgreSQL en producción, plantillas Django, CSS y JS propios sin dependencias.

**Spec:** `docs/superpowers/specs/2026-10-10-solo-cursos-y-fechas-design.md`

## Global Constraints

- Todo texto visible dice **fecha**, nunca «comisión». Direcciones del panel: `/panel/fechas/…`. La clase sigue llamándose `Comision`.
- Estados de una fecha: **Disponible** (verde), **Completo** (rojo), **Oculta** (gris, sólo en el panel).
- Una fecha nueva nace con `visible=True` y `completa=False`.
- La web publica una fecha si `visible` y `fecha_inicio >= hoy`.
- Roles: sólo **Dirección** y **Administración**.
- Código, comentarios y mensajes de commit en español, con el estilo del repo. Cada commit termina con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Pruebas: `.venv/bin/python manage.py test`. Cada tarea termina con toda la batería en verde.
- Las migraciones de esquema se generan con `makemigrations`; las de datos se escriben a mano y deben tolerar que falten filas (producción no tiene los mismos datos que desarrollo).
- No se hace push ni deploy hasta la Tarea 10.

## Review Focus

1. **Datos de producción distintos a los locales**: categorías o cursos que la migración busca y no existen → se saltean sin fallar. (Tarea 7)
2. **Usuario con un rol eliminado** que intenta entrar → queda sin rol y recibe el aviso de «sin rol asignado», no un error 500. (Tarea 5)
3. **`?curso=` desconocido o de un curso inactivo** → se ven todos los cursos. (Tarea 7)
4. **Curso sin «nombre corto»** → el botón usa el nombre completo. (Tarea 7)
5. **Enlaces viejos guardados** (`/panel/comisiones/…`, `/panel/inscripciones/`) → 404, no 500. (Tarea 4)

---

### Tarea 1: Las fechas no se pierden al editar

**Files:**
- Modify: `panel/forms.py` (`ComisionForm.Meta.widgets`)
- Test: `panel/tests.py`

- [ ] **Paso 1: Prueba que falla.** Agregar a `panel/tests.py`:

```python
class EditarFechaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.direccion = Usuario.objects.create_user(username="marta", password="clave-larga-123")
        cls.direccion.asignar_rol(Rol.DIRECCION)
        categoria = Categoria.objects.create(nombre="Cargas Generales")
        cls.curso = Curso.objects.create(categoria=categoria, nombre="Inicial", precio=1)
        cls.fecha = Comision.objects.create(
            curso=cls.curso, fecha_inicio=date(2030, 3, 5), fecha_fin=date(2030, 3, 7)
        )

    def test_el_formulario_trae_las_fechas_cargadas(self):
        self.client.force_login(self.direccion)
        respuesta = self.client.get(reverse("panel:comision_editar", args=[self.fecha.pk]))
        self.assertContains(respuesta, 'value="2030-03-05"')
        self.assertContains(respuesta, 'value="2030-03-07"')
```

Imports nuevos: `from datetime import date` y `from cursos.models import Categoria, Comision, Curso`.

- [ ] **Paso 2:** `manage.py test panel.tests.EditarFechaTests` → FALLA (el valor sale como `05/03/2030`).
- [ ] **Paso 3:** En `ComisionForm.Meta.widgets`, pasar `format="%Y-%m-%d"` a los dos `DateInput`:

```python
"fecha_inicio": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
"fecha_fin": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
```

Revisar `ParticipanteForm` no hace falta: se elimina en la Tarea 2.

- [ ] **Paso 4:** La prueba pasa; batería completa en verde.
- [ ] **Paso 5:** Commit: «Conservar las fechas al editar una comisión».

---

### Tarea 2: Sacar del panel el registro de personas

Sólo borra pantallas. Los modelos siguen existiendo hasta la Tarea 3.

**Files:**
- Delete: `panel/exportaciones.py`; `templates/panel/` → `asistencia.html`, `comision_detalle.html`, `inscripciones.html`, `inscripcion_form.html`, `participantes.html`, `participante_form.html`, `empresas.html`, `empresa_form.html`, `informes.html`, `_estado_inscripcion.html`, `_estado_pago.html`; `inscripciones/tests.py`, `inscripciones/admin.py`
- Modify: `panel/views.py`, `panel/urls.py`, `panel/forms.py`, `panel/accesos.py`, `templates/panel/base.html`, `templates/panel/inicio.html`, `templates/panel/comisiones.html`, `templates/panel/comision_form.html`, `templates/panel/agenda.html`, `requirements.txt`, `cursos/models.py` (`get_absolute_url`)
- Test: `panel/tests.py`

**Interfaces:**
- Produces: ya no existen las rutas `panel:comision_detalle`, `inscribir`, `asistencia`, `exportar_comision`, `planilla`, `inscripciones`, `inscripcion_editar`, `exportar_inscripciones`, `participantes`, `participante_nuevo`, `participante_editar`, `exportar_participantes`, `empresas`, `empresa_nueva`, `empresa_editar`, `informes`. Guardar una comisión redirige a `panel:comisiones`.

- [ ] **Paso 1: Pruebas que fallan.** En `panel/tests.py`:

```python
class PanelSinPersonasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.direccion = Usuario.objects.create_user(username="marta", password="clave-larga-123")
        cls.direccion.asignar_rol(Rol.DIRECCION)

    def setUp(self):
        self.client.force_login(self.direccion)

    def test_las_pantallas_de_personas_ya_no_existen(self):
        for ruta in ("inscripciones/", "participantes/", "empresas/", "informes/",
                     "inscripciones/exportar/", "participantes/nuevo/"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(f"/panel/{ruta}").status_code, 404)

    def test_el_menu_no_las_ofrece(self):
        respuesta = self.client.get(reverse("panel:inicio"))
        for texto in ("Inscripciones", "Participantes", "Informes", "PERSONAS"):
            self.assertNotContains(respuesta, texto)

    def test_el_tablero_no_habla_de_inscriptos_ni_pagos(self):
        respuesta = self.client.get(reverse("panel:inicio"))
        for texto in ("INSCRIPTOS", "PAGOS PENDIENTES", "SOLICITUDES WEB", "Últimas inscripciones"):
            self.assertNotContains(respuesta, texto)
```

- [ ] **Paso 2:** Correrlas → FALLAN.
- [ ] **Paso 3: Vistas.** En `panel/views.py` borrar: `comision_detalle`, `inscribir`, `tomar_asistencia`, `_filtrar_inscripciones`, `inscripciones_lista`, `inscripcion_editar`, `participantes_lista`, `participante_editar`, `empresas_lista`, `empresa_editar`, `exportar_comision`, `planilla_asistencia`, `exportar_inscripciones`, `exportar_participantes`, `informes`, y los imports que queden sin uso (`Sum`, `exp`, `Inscripcion`, `Participante`, `Empresa`, `EmpresaForm`, `InscribirForm`, `InscripcionForm`, `ParticipanteForm`, `GESTION_INSCRIPCIONES`, `url_has_allowed_host_and_scheme`, `_volver`). Además:
  - `comision_editar`: al guardar, `return redirect("panel:comisiones")`.
  - `comision_cambiar_estado`: redirigir a `panel:comisiones` (se reemplaza en la Tarea 4).
  - `comision_eliminar`: quitar el bloqueo por inscripciones.
  - `comisiones_lista`: quitar la anotación `inscriptos_total`.
  - `inicio`: dejar sólo `proximas` y un `indicadores` con `comisiones_abiertas`; quitar avisos, ocupación y últimas inscripciones (se rehace en la Tarea 4).
- [ ] **Paso 4: Rutas, formularios y accesos.** Quitar de `panel/urls.py` las rutas listadas en *Interfaces*. De `panel/forms.py` borrar `EmpresaForm`, `ParticipanteForm`, `InscripcionForm`, `InscribirForm` y su import. De `panel/accesos.py` borrar `GESTION_INSCRIPCIONES`.
- [ ] **Paso 5: Plantillas.** Borrar las listadas. En `base.html` quitar el bloque «PERSONAS» (Inscripciones y Participantes) e «Informes». En `inicio.html` dejar el indicador de comisiones abiertas y la tabla de próximas sin la columna Ocupación; el enlace «Abrir» pasa a «Editar» → `panel:comision_editar`. En `comisiones.html` quitar las columnas Ocupación y Lista; el nombre del curso enlaza a `panel:comision_editar`. En `comision_form.html` quitar «Ver inscriptos». En `agenda.html` el evento enlaza a `panel:comision_editar` y no muestra `inscriptos/cupo`. En `cursos/models.py`, `Comision.get_absolute_url` → `reverse("panel:comision_editar", …)`.
- [ ] **Paso 6:** Quitar `openpyxl>=3.1` de `requirements.txt` y desinstalarlo del venv (`.venv/bin/pip uninstall -y openpyxl`). `grep -rn openpyxl --include=*.py .` no debe dar resultados fuera de `.venv`.
- [ ] **Paso 7:** Borrar `inscripciones/tests.py` e `inscripciones/admin.py`. Las pruebas de la web que vivían ahí (`WebPublicaTests`) se pasan a `web/tests.py` adaptando `BaseDatos` a un `setUpTestData` propio con una categoría, un curso y una comisión publicada futura; se conservan `test_el_inicio_muestra_los_cursos_activos`, `test_un_curso_desactivado_no_aparece`, `test_la_ficha_del_curso_lista_las_fechas_publicadas`, `test_la_web_no_ofrece_reservar_lugar`, `test_no_queda_ninguna_ruta_publica_de_reserva` y `test_la_ficha_no_enlaza_la_boleta_de_pago`.
- [ ] **Paso 8:** Batería en verde (las pruebas de `ManualTests` siguen pasando: el manual se reescribe en la Tarea 9). Commit: «Sacar del panel inscripciones, participantes, empresas e informes».

---

### Tarea 3: Fechas con «visible» y «completa»; adiós a cupo, instructor y estado

**Files:**
- Modify: `cursos/models.py`, `cursos/admin.py`, `cursos/management/commands/cargar_datos.py`, `panel/forms.py`, `panel/views.py`, `panel/accesos.py`, `templates/panel/comision_form.html`, `templates/panel/comisiones.html`, `templates/panel/inicio.html`, `templates/panel/agenda.html`, `templates/panel/curso_form.html`, `templates/panel/cursos.html`, `templates/web/_catalogo.html`, `templates/web/curso.html`
- Create: `cursos/migrations/0009_fechas_visible_y_completa.py`, `inscripciones/migrations/0002_borrar_registro_de_personas.py`, `cursos/migrations/0010_sacar_cupo_instructor_y_estado.py`, `cursos/tests_migraciones.py`
- Delete: `templates/panel/_estado_comision.html` (se reemplaza), contenido de `inscripciones/models.py`
- Test: `cursos/tests.py`, `cursos/tests_migraciones.py`

**Interfaces:**
- Produces, en `Comision`:
  - `visible: bool` (default `True`), `completa: bool` (default `False`)
  - `estado_clave -> str`: `"oculta"` si no es visible, `"completa"` si está completa, si no `"disponible"`
  - `estado_texto -> str`: `"Oculta"`, `"Completo"` o `"Disponible"`
  - desaparecen `Estado`, `estado`, `cupo`, `cerrada`, `instructor`, `observaciones`, `inscriptos`, `cantidad_inscriptos`, `lugares_disponibles`, `ocupacion_porcentaje`, `semaforo`, `visible_en_web`
- Produces, en `Curso`: desaparecen `cupo_sugerido` y `cupo_texto`. `comisiones_publicadas()` filtra `visible=True, fecha_inicio__gte=hoy`.
- Produces: plantilla `panel/_estado_fecha.html` (recibe `comision`).

- [ ] **Paso 0:** Guardar una copia de la base local tal como está antes de migrar, para el ensayo de la Tarea 10: `cp db.sqlite3 ../db-antes-de-solo-fechas.sqlite3` (fuera del repo).
- [ ] **Paso 1: Prueba de la migración de datos.** Crear `cursos/tests_migraciones.py`:

```python
"""Las migraciones que borran datos se prueban contra el estado anterior real."""
from datetime import date

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class MigracionTestCase(TransactionTestCase):
    """Lleva la base a `desde`, deja armar datos y migra a `hasta`."""

    desde = None
    hasta = None

    def setUp(self):
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(self.desde)
        self.armar(ejecutor.loader.project_state(self.desde).apps)
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(self.hasta)
        self.apps = ejecutor.loader.project_state(self.hasta).apps

    def tearDown(self):
        ejecutor = MigrationExecutor(connection)
        ejecutor.migrate(ejecutor.loader.graph.leaf_nodes())

    def armar(self, apps):
        raise NotImplementedError


class FechasVisibleYCompletaTests(MigracionTestCase):
    desde = [("cursos", "0008_comision_marcar_completa"), ("inscripciones", "0001_initial")]
    hasta = [("cursos", "0009_fechas_visible_y_completa")]

    def armar(self, apps):
        Categoria = apps.get_model("cursos", "Categoria")
        Curso = apps.get_model("cursos", "Curso")
        Comision = apps.get_model("cursos", "Comision")
        Participante = apps.get_model("inscripciones", "Participante")
        Inscripcion = apps.get_model("inscripciones", "Inscripcion")
        curso = Curso.objects.create(
            categoria=Categoria.objects.create(nombre="Cargas", slug="cargas"),
            nombre="Inicial", slug="inicial",
        )

        def comision(estado, cupo=25, cerrada=False, inscriptos=0, canceladas=0):
            c = Comision.objects.create(
                curso=curso, fecha_inicio=date(2030, 1, 1), estado=estado, cupo=cupo, cerrada=cerrada
            )
            for i in range(inscriptos + canceladas):
                persona = Participante.objects.create(
                    dni=f"{c.pk:03d}{i:05d}", apellido="A", nombre="B"
                )
                Inscripcion.objects.create(
                    comision=c, participante=persona,
                    estado="cancelada" if i >= inscriptos else "confirmada",
                )
            return c.pk

        self.publicada = comision("publicada")
        self.en_curso = comision("en_curso")
        self.borrador = comision("borrador")
        self.cancelada = comision("cancelada")
        self.finalizada = comision("finalizada")
        self.marcada = comision("publicada", cerrada=True)
        self.llena = comision("publicada", cupo=2, inscriptos=2)
        self.casi = comision("publicada", cupo=2, inscriptos=1, canceladas=3)

    def _fecha(self, pk):
        return self.apps.get_model("cursos", "Comision").objects.get(pk=pk)

    def test_publicada_y_en_curso_quedan_visibles(self):
        self.assertTrue(self._fecha(self.publicada).visible)
        self.assertTrue(self._fecha(self.en_curso).visible)

    def test_borrador_cancelada_y_finalizada_quedan_ocultas(self):
        for pk in (self.borrador, self.cancelada, self.finalizada):
            self.assertFalse(self._fecha(pk).visible)

    def test_la_marcada_como_completa_sigue_completa(self):
        self.assertTrue(self._fecha(self.marcada).completa)

    def test_la_que_llego_al_cupo_queda_completa(self):
        self.assertTrue(self._fecha(self.llena).completa)

    def test_las_canceladas_no_cuentan_para_el_cupo(self):
        self.assertFalse(self._fecha(self.casi).completa)

    def test_una_publicada_con_lugar_queda_disponible(self):
        self.assertFalse(self._fecha(self.publicada).completa)
```

- [ ] **Paso 2:** `manage.py test cursos.tests_migraciones` → FALLA (no existe la migración 0009).
- [ ] **Paso 3: Migración 0009**, escrita a mano en `cursos/migrations/0009_fechas_visible_y_completa.py`:

```python
"""Cada fecha pasa a tener sólo dos datos de estado: visible y completa.

Se calcula acá, mientras todavía existen el estado viejo, el cupo y las
inscripciones; las migraciones siguientes borran las tres cosas.
"""
from django.db import migrations, models
from django.db.models import Count, Q


def pasar_estado(apps, schema_editor):
    Comision = apps.get_model("cursos", "Comision")
    Comision.objects.filter(estado__in=["publicada", "en_curso"]).update(visible=True)
    Comision.objects.exclude(estado__in=["publicada", "en_curso"]).update(visible=False)
    llenas = Comision.objects.annotate(
        ocupados=Count("inscripciones", filter=~Q(inscripciones__estado="cancelada"))
    ).filter(ocupados__gte=models.F("cupo"), cupo__gt=0)
    Comision.objects.filter(pk__in=list(llenas.values_list("pk", flat=True))).update(completa=True)


class Migration(migrations.Migration):
    dependencies = [
        ("cursos", "0008_comision_marcar_completa"),
        ("inscripciones", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="comision", name="visible",
            field=models.BooleanField(
                default=True, verbose_name="visible en la web",
                help_text="Destildala para guardar la fecha sin publicarla.",
            ),
        ),
        migrations.RenameField(model_name="comision", old_name="cerrada", new_name="completa"),
        migrations.AlterField(
            model_name="comision", name="completa",
            field=models.BooleanField(
                default=False, verbose_name="completo",
                help_text="La web muestra la fecha como «Completo» en lugar de «Disponible».",
            ),
        ),
        migrations.RunPython(pasar_estado, migrations.RunPython.noop),
    ]
```

Una comisión con cupo 0 no se marca completa por eso solo: en la reunión se vio una que quedó «completa» sin querer por tener cupo cero.

- [ ] **Paso 4: Modelo.** En `cursos/models.py`, `Comision`: borrar la clase `Estado` y los campos `cupo`, `instructor`, `estado`, `observaciones`; renombrar `cerrada` → `completa` y agregar `visible` (mismos `verbose_name` y `help_text` que en la migración); borrar las propiedades listadas en *Interfaces*; `Meta` con `verbose_name = "fecha"`, `verbose_name_plural = "fechas"`, `indexes = [models.Index(fields=["fecha_inicio", "visible"])]`; docstring «Una fecha de dictado del curso.». Agregar:

```python
    @property
    def estado_clave(self):
        """Para elegir color: oculta, completa o disponible."""
        if not self.visible:
            return "oculta"
        return "completa" if self.completa else "disponible"

    @property
    def estado_texto(self):
        return {"oculta": "Oculta", "completa": "Completo", "disponible": "Disponible"}[
            self.estado_clave
        ]
```

`Curso`: borrar `cupo_sugerido` y `cupo_texto`; `comisiones_publicadas()`:

```python
        return self.comisiones.filter(
            visible=True, fecha_inicio__gte=date.today()
        ).order_by("fecha_inicio", "hora_inicio")
```

Vaciar `inscripciones/models.py` dejando sólo el docstring: `"""Sin modelos: el registro de personas se eliminó. Quedan las migraciones."""`.

- [ ] **Paso 5: Migraciones de esquema.** `makemigrations inscripciones -n borrar_registro_de_personas` y agregarle a mano la dependencia `("cursos", "0009_fechas_visible_y_completa")`. Luego `makemigrations cursos -n sacar_cupo_instructor_y_estado` y agregarle la dependencia `("inscripciones", "0002_borrar_registro_de_personas")`. Verificar con `makemigrations --check --dry-run` que no queda nada pendiente y que `migrate` corre en limpio sobre una copia de `db.sqlite3`.
- [ ] **Paso 6: Pruebas del modelo.** En `cursos/tests.py`, `ComisionTests`: borrar `test_cupo_disponible`, `test_las_canceladas_no_ocupan_cupo`, `test_completa_al_llegar_al_cupo`, `test_marcada_como_completa_sin_llegar_al_cupo`; reescribir las dos de la web y agregar:

```python
    def test_una_fecha_nueva_nace_visible_y_disponible(self):
        fecha = Comision.objects.create(curso=self.curso, fecha_inicio=self.manana)
        self.assertTrue(fecha.visible)
        self.assertFalse(fecha.completa)
        self.assertEqual(fecha.estado_clave, "disponible")
        self.assertEqual(fecha.estado_texto, "Disponible")

    def test_completa_y_oculta(self):
        fecha = Comision(curso=self.curso, fecha_inicio=self.manana, completa=True)
        self.assertEqual(fecha.estado_texto, "Completo")
        fecha.visible = False
        self.assertEqual(fecha.estado_clave, "oculta")

    def test_solo_las_visibles_futuras_salen_en_la_web(self):
        visible = Comision.objects.create(curso=self.curso, fecha_inicio=self.manana)
        Comision.objects.create(curso=self.curso, fecha_inicio=self.manana, visible=False)
        self.assertEqual(list(self.curso.comisiones_publicadas()), [visible])

    def test_las_pasadas_no_salen_en_la_web(self):
        Comision.objects.create(curso=self.curso, fecha_inicio=self.ayer)
        self.assertEqual(list(self.curso.comisiones_publicadas()), [])

    def test_la_de_hoy_todavia_sale(self):
        hoy = Comision.objects.create(curso=self.curso, fecha_inicio=date.today())
        self.assertEqual(list(self.curso.comisiones_publicadas()), [hoy])

    def test_salen_ordenadas_por_fecha_aunque_se_carguen_desordenadas(self):
        tarde = Comision.objects.create(curso=self.curso, fecha_inicio=self.manana + timedelta(days=9))
        medio = Comision.objects.create(curso=self.curso, fecha_inicio=self.manana + timedelta(days=4))
        antes = Comision.objects.create(curso=self.curso, fecha_inicio=self.manana)
        self.assertEqual(list(self.curso.comisiones_publicadas()), [antes, medio, tarde])
```

(`self.manana` / `self.ayer` en `setUp`, si no existen ya, como `date.today() ± timedelta(days=1)`.)

- [ ] **Paso 7: Adaptar lo que usaba los campos viejos** (lo mínimo para quedar en verde; el panel se rediseña en la Tarea 4):
  - `cursos/admin.py`: `ComisionAdmin.list_display = ("curso", "fecha_inicio", "visible", "completa")`, `list_filter = ("visible", "completa", "curso__categoria")`.
  - `panel/forms.py`: `ComisionForm.Meta.fields = ["curso", "fecha_inicio", "fecha_fin", "hora_inicio", "hora_fin", "lugar", "visible", "completa"]`; quitar del `__init__` lo del instructor y del `clean` lo del cupo. `CursoForm`: quitar `cupo_sugerido` y `cupo_texto`.
  - `panel/views.py`: `comision_editar` sin `cupo` en `inicial`; `comisiones_lista` sin filtro por estado ni `comisiones_visibles`; `inicio` y `agenda` sin `estado` ni `comisiones_visibles`; borrar `comision_cambiar_estado`, `_puede_gestionar_comisiones` queda. En `panel/accesos.py` borrar `comisiones_visibles`.
  - Plantillas del panel: crear `panel/_estado_fecha.html`:

```django
{% if comision.estado_clave == "disponible" %}<span class="distintivo distintivo--verde">Disponible</span>
{% elif comision.estado_clave == "completa" %}<span class="distintivo distintivo--rojo">Completo</span>
{% else %}<span class="distintivo distintivo--gris">Oculta</span>{% endif %}
```

    y usarla donde se incluía `_estado_comision.html` (que se borra). `comision_form.html`: quitar cupo, instructor, estado y observaciones; mostrar `form.visible` y `form.completa`. `comisiones.html`: quitar columna Instructor y el filtro de estado. `curso_form.html` y `cursos.html`: quitar cupo sugerido y texto del cupo. `agenda.html`: clase `calendario__evento--{{ comision.estado_clave }}`.
  - Plantillas web: en `_catalogo.html` y `curso.html` reemplazar provisoriamente lugares/barra por `{{ comision.estado_texto }}` y quitar el dato «CUPO» (el diseño final va en la Tarea 6).
  - `cargar_datos.py`: quitar `cupo_sugerido` de los datos y de `defaults`; `_cargar_demo` crea sólo fechas (sin empresas, participantes ni inscripciones; `visible` al azar con peso 4 a 1 y `completa` con peso 1 a 4); quitar del resumen las líneas de participantes e inscripciones y el import de `inscripciones.models`.
- [ ] **Paso 8:** `manage.py test` completo en verde, incluida `cursos.tests_migraciones`. Probar `migrate` sobre una copia de la base local y abrir `/panel/` y `/` en el servidor de desarrollo.
- [ ] **Paso 9:** Commit: «Reducir cada fecha a visible y completa; borrar el registro de personas».

---

### Tarea 4: El panel de Fechas

**Files:**
- Modify: `panel/urls.py`, `panel/views.py`, `templates/panel/base.html`, `templates/panel/inicio.html`, `templates/panel/agenda.html`, `templates/panel/cursos.html`, `templates/panel/curso_form.html`, `static/css/panel.css`, `cursos/models.py` (`get_absolute_url`)
- Rename: `templates/panel/comisiones.html` → `fechas.html`, `comision_form.html` → `fecha_form.html`
- Create: `templates/panel/_acciones_fecha.html`
- Test: `panel/tests.py`

**Interfaces:**
- Produces rutas: `panel:fechas` (`fechas/`), `panel:fecha_nueva` (`fechas/nueva/`), `panel:fecha_editar` (`fechas/<pk>/`), `panel:fecha_eliminar` (`fechas/<pk>/eliminar/`), `panel:fecha_marcar` (`fechas/<pk>/marcar/`, sólo POST con `campo` ∈ {`visible`, `completa`} y `valor` ∈ {`0`, `1`}; vuelve a `next` si es una dirección propia, si no a `panel:fechas`).
- Las rutas `panel:comision*` dejan de existir.

- [ ] **Paso 1: Pruebas que fallan.** Reemplazar `EditarFechaTests` por `FechasTests` (misma base de datos de prueba, sumando un usuario de Administración):

```python
    def test_una_fecha_nueva_queda_publicada(self):
        self.client.post(reverse("panel:fecha_nueva"), {
            "curso": self.curso.pk, "fecha_inicio": "2030-05-10", "visible": "on",
        })
        nueva = Comision.objects.get(fecha_inicio=date(2030, 5, 10))
        self.assertTrue(nueva.visible)
        self.assertFalse(nueva.completa)

    def test_el_formulario_nuevo_trae_visible_tildado(self):
        respuesta = self.client.get(reverse("panel:fecha_nueva"))
        self.assertTrue(respuesta.context["form"]["visible"].value())
        self.assertFalse(respuesta.context["form"]["completa"].value())

    def test_el_formulario_trae_las_fechas_cargadas(self):
        respuesta = self.client.get(reverse("panel:fecha_editar", args=[self.fecha.pk]))
        self.assertContains(respuesta, 'value="2030-03-05"')
        self.assertContains(respuesta, 'value="2030-03-07"')

    def test_marcar_completa_y_volver_a_disponible(self):
        url = reverse("panel:fecha_marcar", args=[self.fecha.pk])
        self.client.post(url, {"campo": "completa", "valor": "1"})
        self.fecha.refresh_from_db()
        self.assertTrue(self.fecha.completa)
        self.client.post(url, {"campo": "completa", "valor": "0"})
        self.fecha.refresh_from_db()
        self.assertFalse(self.fecha.completa)

    def test_ocultar_y_publicar(self):
        url = reverse("panel:fecha_marcar", args=[self.fecha.pk])
        self.client.post(url, {"campo": "visible", "valor": "0"})
        self.fecha.refresh_from_db()
        self.assertFalse(self.fecha.visible)

    def test_marcar_no_acepta_otros_campos_ni_get(self):
        url = reverse("panel:fecha_marcar", args=[self.fecha.pk])
        self.client.post(url, {"campo": "curso", "valor": "1"})
        self.client.get(url)
        self.fecha.refresh_from_db()
        self.assertTrue(self.fecha.visible)
        self.assertFalse(self.fecha.completa)

    def test_marcar_vuelve_a_donde_estaba(self):
        respuesta = self.client.post(
            reverse("panel:fecha_marcar", args=[self.fecha.pk]),
            {"campo": "completa", "valor": "1", "next": reverse("panel:inicio")},
        )
        self.assertRedirects(respuesta, reverse("panel:inicio"))

    def test_marcar_no_redirige_afuera(self):
        respuesta = self.client.post(
            reverse("panel:fecha_marcar", args=[self.fecha.pk]),
            {"campo": "completa", "valor": "1", "next": "https://ejemplo.com/"},
        )
        self.assertRedirects(respuesta, reverse("panel:fechas"))

    def test_se_elimina_con_post_y_no_con_get(self):
        url = reverse("panel:fecha_eliminar", args=[self.fecha.pk])
        self.client.get(url)
        self.assertTrue(Comision.objects.filter(pk=self.fecha.pk).exists())
        self.client.post(url)
        self.assertFalse(Comision.objects.filter(pk=self.fecha.pk).exists())

    def test_el_listado_ordena_por_fecha_y_separa_las_pasadas(self):
        pasada = Comision.objects.create(curso=self.curso, fecha_inicio=date(2020, 1, 1))
        antes = Comision.objects.create(curso=self.curso, fecha_inicio=date(2030, 1, 1))
        proximas = list(self.client.get(reverse("panel:fechas")).context["fechas"])
        self.assertEqual(proximas, [antes, self.fecha])
        pasadas = list(self.client.get(reverse("panel:fechas") + "?cuando=pasadas").context["fechas"])
        self.assertEqual(pasadas, [pasada])

    def test_una_fecha_de_fin_anterior_al_inicio_no_se_guarda(self):
        respuesta = self.client.post(reverse("panel:fecha_nueva"), {
            "curso": self.curso.pk, "fecha_inicio": "2030-05-10", "fecha_fin": "2030-05-09",
        })
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "campo-fila--error")

    def test_los_enlaces_viejos_dan_404(self):
        for ruta in ("comisiones/", f"comisiones/{self.fecha.pk}/", "comisiones/nueva/"):
            with self.subTest(ruta=ruta):
                self.assertEqual(self.client.get(f"/panel/{ruta}").status_code, 404)

    def test_nada_dice_comision(self):
        for nombre in ("panel:inicio", "panel:fechas", "panel:fecha_nueva", "panel:agenda", "panel:cursos"):
            with self.subTest(pantalla=nombre):
                html = self.client.get(reverse(nombre)).content.decode().lower()
                self.assertNotIn("comisi", html)

    def test_el_tablero_cuenta_publicadas_completas_y_ocultas(self):
        Comision.objects.create(curso=self.curso, fecha_inicio=date(2030, 6, 1), completa=True)
        Comision.objects.create(curso=self.curso, fecha_inicio=date(2030, 6, 2), visible=False)
        Comision.objects.create(curso=self.curso, fecha_inicio=date(2020, 1, 1))
        indicadores = self.client.get(reverse("panel:inicio")).context["indicadores"]
        self.assertEqual(indicadores, {"publicadas": 2, "completas": 1, "ocultas": 1})
```

- [ ] **Paso 2:** Correr → FALLAN por `NoReverseMatch`.
- [ ] **Paso 3: Rutas y vistas.** En `panel/urls.py` reemplazar el bloque de comisiones por las cinco rutas de *Interfaces*. En `panel/views.py` renombrar `comisiones_lista` → `fechas_lista`, `comision_editar` → `fecha_editar`, `comision_eliminar` → `fecha_eliminar`, con mensajes «Fecha guardada.» / «Fecha «…» eliminada.», y agregar:

```python
def _volver(request, por_defecto):
    """Vuelve a `next` si es una dirección propia; si no, al destino por defecto."""
    destino = request.POST.get("next")
    if destino and url_has_allowed_host_and_scheme(
        destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(destino)
    return redirect(por_defecto)


@GESTION_COMISIONES
def fecha_marcar(request, pk):
    """Cambia «visible» o «completa» con un clic, desde el listado o el Tablero."""
    fecha = get_object_or_404(Comision, pk=pk)
    campo = request.POST.get("campo")
    if request.method == "POST" and campo in {"visible", "completa"}:
        setattr(fecha, campo, request.POST.get("valor") == "1")
        fecha.save(update_fields=[campo, "actualizado"])
        messages.success(request, f"{fecha.curso.nombre}, {fecha.fecha_texto}: {fecha.estado_texto.lower()}.")
    return _volver(request, "panel:fechas")
```

`fechas_lista`: `cuando` ∈ {`proximas` (por defecto, `fecha_inicio >= hoy`, orden ascendente), `pasadas` (`< hoy`, descendente)}; contexto `fechas`, `cuando`, `q`. `inicio`:

```python
    proximas = Comision.objects.select_related("curso", "curso__categoria").filter(fecha_inicio__gte=hoy)
    return render(request, "panel/inicio.html", {
        "seccion": "inicio",
        "indicadores": {
            "publicadas": proximas.filter(visible=True).count(),
            "completas": proximas.filter(visible=True, completa=True).count(),
            "ocultas": proximas.filter(visible=False).count(),
        },
        "proximas": proximas.order_by("fecha_inicio", "hora_inicio")[:10],
    })
```

`Comision.get_absolute_url` → `reverse("panel:fecha_editar", …)`. Renombrar el atajo `GESTION_COMISIONES` no hace falta hasta la Tarea 5.

- [ ] **Paso 4: Plantillas.** Crear `panel/_acciones_fecha.html` (recibe `comision`): un formulario chico por acción, cada uno con su `campo` y su `valor`.

```django
<div class="fila" style="gap:6px">
  <form method="post" action="{% url 'panel:fecha_marcar' comision.pk %}">
    {% csrf_token %}
    <input type="hidden" name="next" value="{{ request.get_full_path }}">
    <input type="hidden" name="campo" value="completa">
    <input type="hidden" name="valor" value="{% if comision.completa %}0{% else %}1{% endif %}">
    <button class="boton boton--secundario boton--chico" type="submit">
      {% if comision.completa %}Marcar disponible{% else %}Marcar completa{% endif %}
    </button>
  </form>
  <form method="post" action="{% url 'panel:fecha_marcar' comision.pk %}">
    {% csrf_token %}
    <input type="hidden" name="next" value="{{ request.get_full_path }}">
    <input type="hidden" name="campo" value="visible">
    <input type="hidden" name="valor" value="{% if comision.visible %}0{% else %}1{% endif %}">
    <button class="boton boton--secundario boton--chico" type="submit">
      {% if comision.visible %}Ocultar{% else %}Publicar{% endif %}
    </button>
  </form>
</div>
```

  `fechas.html`: título «Fechas», bajada «Cada fecha es un dictado de un curso. Tildá «Completo» cuando no queden lugares.», botón «+ Nueva fecha», pestañas Próximas / Pasadas, buscador por curso, columnas Curso · Fecha · Horario · Estado (`_estado_fecha.html`) · acciones (`_acciones_fecha.html`) · Editar. `fecha_form.html`: tres secciones —«1. Qué curso», «2. Cuándo y dónde», «3. Publicación» con las dos casillas—, botón «Guardar fecha» y el recuadro «Eliminar esta fecha» sin condiciones. `inicio.html`: tres indicadores (FECHAS PUBLICADAS, COMPLETAS, OCULTAS) y la tabla «Próximas fechas» con estado y acciones rápidas. `agenda.html`: bajada «N fechas en …», pie «Verde: disponible. Rojo: completo. Gris: oculta, no se ve en la web.». `base.html`: el menú dice «Fechas» y apunta a `panel:fechas`; `seccion == 'fechas'`. `cursos.html` y `curso_form.html`: «+ agregar fecha» → `panel:fecha_nueva`.

- [ ] **Paso 5: Estilos.** En `static/css/panel.css` reemplazar los modificadores del calendario por:

```css
.calendario__evento--disponible { background: var(--verde-tinte); color: #05603a; }
.calendario__evento--completa { background: var(--rojo-tinte); color: #912018; }
.calendario__evento--oculta { background: #eef0f4; color: var(--texto-suave); }
```

- [ ] **Paso 6:** Batería en verde. Abrir el panel en el servidor de desarrollo: crear una fecha, marcarla completa desde el listado y desde el Tablero, ocultarla, editarla y borrarla.
- [ ] **Paso 7:** Commit: «Rehacer el panel alrededor de las fechas».

---

### Tarea 5: Dos roles

**Files:**
- Modify: `cuentas/models.py`, `cuentas/permisos.py`, `panel/accesos.py`, `panel/views.py`, `templates/panel/base.html`, `cursos/management/commands/cargar_datos.py`, `cuentas/tests.py`, `contenido/tests.py`, `panel/tests.py`
- Create: `cuentas/migrations/0002_dos_roles.py`, `cuentas/tests_migraciones.py`

**Interfaces:**
- Produces: `Rol` con sólo `DIRECCION` y `ADMINISTRACION`; `JERARQUIA = [Rol.DIRECCION, Rol.ADMINISTRACION]`; en `panel/accesos.py` quedan `requiere_panel`, `SOLO_DIRECCION` y `GESTION = requiere_nivel(Rol.ADMINISTRACION)` (reemplaza a `GESTION_CATALOGO`, `GESTION_COMISIONES` y `LECTURA_INSTITUCIONAL`).

- [ ] **Paso 1: Prueba de la migración.** `cuentas/tests_migraciones.py`, reutilizando `MigracionTestCase` de `cursos.tests_migraciones`:

```python
from cursos.tests_migraciones import MigracionTestCase


class DosRolesTests(MigracionTestCase):
    desde = [("cuentas", "0001_initial")]
    hasta = [("cuentas", "0002_dos_roles")]

    def armar(self, apps):
        Usuario = apps.get_model("cuentas", "Usuario")
        Group = apps.get_model("auth", "Group")
        for nombre in ("Dirección", "Administración", "Coordinación", "Recepción", "Instructor"):
            grupo = Group.objects.create(name=nombre)
            Usuario.objects.create(username=nombre).groups.add(grupo)
        Usuario.objects.create(username="sin-grupo")

    def _grupos(self, username):
        Usuario = self.apps.get_model("cuentas", "Usuario")
        return list(Usuario.objects.get(username=username).groups.values_list("name", flat=True))

    def test_direccion_y_administracion_no_cambian(self):
        self.assertEqual(self._grupos("Dirección"), ["Dirección"])
        self.assertEqual(self._grupos("Administración"), ["Administración"])

    def test_coordinacion_pasa_a_administracion(self):
        self.assertEqual(self._grupos("Coordinación"), ["Administración"])

    def test_recepcion_e_instructor_quedan_sin_rol(self):
        self.assertEqual(self._grupos("Recepción"), [])
        self.assertEqual(self._grupos("Instructor"), [])

    def test_los_grupos_viejos_se_borran(self):
        Group = self.apps.get_model("auth", "Group")
        self.assertEqual(
            sorted(Group.objects.values_list("name", flat=True)), ["Administración", "Dirección"]
        )
```

- [ ] **Paso 2:** Correr → FALLA.
- [ ] **Paso 3: Migración** `cuentas/migrations/0002_dos_roles.py`:

```python
"""Quedan dos roles. Coordinación pasa a Administración; el resto, sin rol."""
from django.db import migrations


def reducir(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Usuario = apps.get_model("cuentas", "Usuario")
    coordinacion = Group.objects.filter(name="Coordinación").first()
    if coordinacion:
        administracion, _ = Group.objects.get_or_create(name="Administración")
        for usuario in Usuario.objects.filter(groups=coordinacion):
            usuario.groups.set([administracion])
    Group.objects.filter(name__in=["Coordinación", "Recepción", "Instructor"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("cuentas", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]
    operations = [migrations.RunPython(reducir, migrations.RunPython.noop)]
```

- [ ] **Paso 4: Código.** `cuentas/models.py`: `Rol`, `JERARQUIA` y `DESCRIPCION_ROLES` con dos entradas («Acceso total: cursos, fechas, páginas, usuarios y configuración del sitio.» / «Gestiona cursos, categorías, fechas y páginas. No administra usuarios ni la configuración.»). `cuentas/permisos.py`: `MATRIZ` con los dos roles y sin las claves `inscripciones.*`. `panel/accesos.py`: los atajos de *Interfaces*. `panel/views.py`: usar `GESTION` en cursos, categorías, páginas (listado incluido) y fechas; `requiere_panel` en tablero, agenda, listados y ayuda. `base.html`: quitar la condición por «Instructor» del enlace Páginas. `cargar_datos.py`: sólo los usuarios `direccion` y `administracion`.
- [ ] **Paso 5: Pruebas.** `cuentas/tests.py`: `test_sincronizar_grupos_crea_los_dos_roles` (cuenta 2), usar `Rol.ADMINISTRACION` donde se usaba Recepción o Coordinación, y `test_alcanza_respeta_el_orden_de_la_jerarquia` con los dos roles. `contenido/tests.py`: borrar `test_recepcion_entra_al_listado` y `test_instructor_no_entra`. `panel/tests.py`: reemplazar `Rol.RECEPCION` por `Rol.ADMINISTRACION`, y agregar:

```python
class PermisosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        sincronizar_grupos()
        cls.administracion = Usuario.objects.create_user(username="luis", password="clave-larga-123")
        cls.administracion.asignar_rol(Rol.ADMINISTRACION)
        cls.sin_rol = Usuario.objects.create_user(username="viejo", password="clave-larga-123")

    def test_administracion_gestiona_fechas_cursos_y_paginas(self):
        self.client.force_login(self.administracion)
        for nombre in ("panel:fechas", "panel:fecha_nueva", "panel:cursos", "panel:curso_nuevo",
                       "panel:categorias", "panel:paginas", "panel:pagina_nueva", "panel:agenda"):
            with self.subTest(pantalla=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_administracion_no_toca_usuarios_ni_configuracion(self):
        self.client.force_login(self.administracion)
        for nombre in ("panel:usuarios", "panel:configuracion"):
            with self.subTest(pantalla=nombre):
                self.assertRedirects(self.client.get(reverse(nombre)), reverse("panel:inicio"))

    def test_un_usuario_sin_rol_no_entra_y_no_rompe(self):
        self.client.force_login(self.sin_rol)
        self.assertEqual(self.client.get(reverse("panel:inicio")).status_code, 403)
```

- [ ] **Paso 6:** Batería en verde. Commit: «Dejar sólo los roles Dirección y Administración».

---

### Tarea 6: La web muestra «Disponible» o «Completo»

**Files:**
- Modify: `templates/web/_catalogo.html`, `templates/web/curso.html`, `static/css/web.css`
- Test: `web/tests.py`

- [ ] **Paso 1: Pruebas que fallan.** En `web/tests.py`:

```python
class EstadoDeFechaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        categoria = Categoria.objects.create(nombre="Cargas Generales")
        cls.curso = Curso.objects.create(categoria=categoria, nombre="Inicial", precio=1)
        manana = date.today() + timedelta(days=1)
        Comision.objects.create(curso=cls.curso, fecha_inicio=manana)
        Comision.objects.create(curso=cls.curso, fecha_inicio=manana + timedelta(days=7), completa=True)
        Comision.objects.create(curso=cls.curso, fecha_inicio=manana + timedelta(days=14), visible=False)

    def _paginas(self):
        return [self.client.get("/"), self.client.get(self.curso.get_absolute_url())]

    def test_cada_fecha_lleva_su_estado(self):
        for respuesta in self._paginas():
            self.assertContains(respuesta, "estado-fecha--disponible", count=1)
            self.assertContains(respuesta, "estado-fecha--completa", count=1)
            self.assertContains(respuesta, ">Disponible<")
            self.assertContains(respuesta, ">Completo<")

    def test_ya_no_se_habla_de_lugares_ni_de_cupo(self):
        for respuesta in self._paginas():
            self.assertNotContains(respuesta, "lugar")
            self.assertNotContains(respuesta, "CUPO")
            self.assertNotContains(respuesta, "cupo-barra")
```

(`test_ya_no_se_habla_de_lugares…`: si la sede u otro texto fijo contiene «lugar», afinar a `" lugares"` y `"1 lugar"`.)

- [ ] **Paso 2:** Correr → FALLAN.
- [ ] **Paso 3: Plantillas.** En `_catalogo.html`, cada fecha:

```django
<span class="fecha-chip">
  {{ comision.fecha_texto }}
  <span class="estado-fecha estado-fecha--{{ comision.estado_clave }}">{{ comision.estado_texto }}</span>
</span>
```

En `curso.html`, la columna «Cupo» pasa a «Estado» con el mismo `<span class="estado-fecha …">`, sin barra. Quitar el dato «CUPO» de la tarjeta y del lateral de la ficha.

- [ ] **Paso 4: Estilos** en `static/css/web.css`; borrar `.fecha-chip--completa`, `.cupo-barra*` y `.caja-fechas__cupo`:

```css
.estado-fecha {
  display: inline-block; margin-left: 6px; padding: 2px 9px; border-radius: 4px;
  font-size: 12.5px; font-weight: 700; letter-spacing: 0.02em; color: #ffffff;
}
.estado-fecha--disponible { background: #15803d; }
.estado-fecha--completa { background: #b42318; }
```

Verificar contraste de texto blanco sobre ambos fondos (≥ 4,5:1) y cómo se ve dentro de `.caja-fechas`, que tiene fondo oscuro.

- [ ] **Paso 5:** Batería en verde; mirar la portada y una ficha en el navegador, también a 380 px de ancho. Commit: «Mostrar cada fecha como disponible o completa».

---

### Tarea 7: Cursos agrupados en bloques, con un botón por curso

**Files:**
- Modify: `cursos/models.py`, `panel/forms.py`, `templates/panel/curso_form.html`, `web/views.py`, `templates/web/_catalogo.html`, `static/js/filtros.js`, `static/css/web.css`, `cursos/management/commands/cargar_datos.py`, `web/tests.py`
- Create: `cursos/migrations/0011_nombre_corto_y_bloques.py`
- Test: `web/tests.py`, `cursos/tests_migraciones.py`

**Interfaces:**
- Produces: `Curso.nombre_corto: str` (máx. 40, opcional) y `Curso.nombre_boton -> str` (el corto, o el nombre completo si está vacío). Contexto de la grilla: `catalogo` (como hoy) y `curso_actual: str` (slug o `""`). Desaparecen `filtros` y `filtro_actual`.

- [ ] **Paso 1: Pruebas que fallan.** En `web/tests.py`, reemplazar las pruebas de filtros por categoría de `CatalogoTests` (`test_sin_filtro_se_ven_todas_las_categorias`, `test_el_filtro_deja_una_sola_categoria`, `test_los_filtros_no_vuelven_al_principio_de_la_seccion`, `test_un_filtro_desconocido_muestra_todo`, `test_las_categorias_sin_cursos_no_tienen_filtro`) por:

```python
class BloquesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        generales = Categoria.objects.create(nombre="Cargas Generales", orden=1)
        peligrosas = Categoria.objects.create(nombre="Mercancías Peligrosas", orden=2)
        Categoria.objects.create(nombre="Transporte de Pasajeros", orden=3)
        cls.inicial = Curso.objects.create(
            categoria=generales, nombre="Curso primera vez — Cargas Generales", nombre_corto="Inicial", precio=1, orden=1)
        cls.renovacion = Curso.objects.create(
            categoria=generales, nombre="Renovación — Cargas Generales", nombre_corto="Renovación", precio=1, orden=2)
        cls.peligrosas = Curso.objects.create(
            categoria=peligrosas, nombre="Curso primera vez — Mercancías Peligrosas", precio=1)
        cls.oculto = Curso.objects.create(
            categoria=generales, nombre="Viejo", nombre_corto="Viejo", precio=1, activo=False)

    def _tarjetas_visibles(self, respuesta):
        html = respuesta.content.decode()
        return re.findall(r'<article class="tarjeta-curso" data-curso="([^"]+)"(?! hidden)', html)

    def test_sin_elegir_se_ven_todos_los_cursos(self):
        respuesta = self.client.get("/")
        self.assertEqual(
            self._tarjetas_visibles(respuesta),
            [self.inicial.slug, self.renovacion.slug, self.peligrosas.slug],
        )

    def test_cada_curso_tiene_su_boton_con_el_nombre_corto(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, 'data-curso="%s">Inicial</a>' % self.inicial.slug)
        self.assertContains(respuesta, 'data-curso="%s">Renovación</a>' % self.renovacion.slug)

    def test_sin_nombre_corto_el_boton_usa_el_nombre_completo(self):
        respuesta = self.client.get("/")
        self.assertContains(
            respuesta, 'data-curso="%s">Curso primera vez — Mercancías Peligrosas</a>' % self.peligrosas.slug)

    def test_elegir_un_curso_muestra_solo_ese(self):
        respuesta = self.client.get("/?curso=" + self.renovacion.slug)
        self.assertEqual(self._tarjetas_visibles(respuesta), [self.renovacion.slug])
        self.assertContains(respuesta, "boton-curso--activo", count=1)

    def test_los_bloques_y_sus_botones_siguen_a_la_vista(self):
        respuesta = self.client.get("/?curso=" + self.renovacion.slug)
        self.assertContains(respuesta, "Mercancías Peligrosas")
        self.assertContains(respuesta, 'data-curso="%s">Inicial</a>' % self.inicial.slug)

    def test_un_curso_desconocido_o_inactivo_muestra_todo(self):
        for slug in ("no-existe", self.oculto.slug):
            with self.subTest(slug=slug):
                self.assertEqual(len(self._tarjetas_visibles(self.client.get("/?curso=" + slug))), 3)

    def test_un_bloque_sin_cursos_visibles_no_aparece(self):
        self.assertNotContains(self.client.get("/"), "Transporte de Pasajeros")

    def test_el_boton_activo_vuelve_a_mostrar_todo(self):
        respuesta = self.client.get("/?curso=" + self.renovacion.slug)
        self.assertContains(respuesta, 'class="boton-curso boton-curso--activo" aria-current="true" href="/#cursos-lista"')

    def test_la_pagina_de_cursos_funciona_igual(self):
        respuesta = self.client.get("/cursos/?curso=" + self.inicial.slug)
        self.assertEqual(self._tarjetas_visibles(respuesta), [self.inicial.slug])
```

Y en `cursos/tests_migraciones.py`:

```python
class ReagruparCursosTests(MigracionTestCase):
    desde = [("cursos", "0010_sacar_cupo_instructor_y_estado")]
    hasta = [("cursos", "0011_nombre_corto_y_bloques")]

    def armar(self, apps):
        Categoria = apps.get_model("cursos", "Categoria")
        Curso = apps.get_model("cursos", "Curso")
        generales = Categoria.objects.create(nombre="Cargas Generales", slug="cargas-generales", orden=1)
        peligrosas = Categoria.objects.create(nombre="Mercancías Peligrosas", slug="mercancias-peligrosas", orden=2)
        renovacion = Categoria.objects.create(nombre="Renovación", slug="renovacion", orden=3)
        ampliacion = Categoria.objects.create(nombre="Ampliación", slug="ampliacion", orden=4)
        crear = lambda cat, nombre, slug: Curso.objects.create(categoria=cat, nombre=nombre, slug=slug)
        crear(generales, "Curso Primera vez — Cargas Generales y/o Pasajeros", "inicial")
        crear(peligrosas, "Curso primera vez — Mercancías Peligrosas", "mp-primera")
        crear(peligrosas, "Curso Renovación — Mercancías Peligrosas", "mp-renovacion")
        crear(peligrosas, "Curso actualización — Mercancías Peligrosas", "mp-actualizacion")
        crear(renovacion, "Renovación — Cargas Generales y/o Pasajeros", "renovacion")
        crear(ampliacion, "Ampliación — Cargas Generales y/o Pasajeros", "ampliacion")

    def _curso(self, slug):
        return self.apps.get_model("cursos", "Curso").objects.select_related("categoria").get(slug=slug)

    def test_renovacion_y_ampliacion_pasan_a_cargas_generales(self):
        for slug, corto in (("renovacion", "Renovación"), ("ampliacion", "Ampliación")):
            curso = self._curso(slug)
            self.assertEqual(curso.categoria.slug, "cargas-generales")
            self.assertEqual(curso.nombre_corto, corto)

    def test_los_botones_quedan_en_orden_inicial_renovacion_ampliacion(self):
        Curso = self.apps.get_model("cursos", "Curso")
        en_orden = Curso.objects.filter(categoria__slug="cargas-generales").order_by("orden", "nombre")
        self.assertEqual([c.nombre_corto for c in en_orden], ["Inicial", "Renovación", "Ampliación"])

    def test_peligrosas_recibe_sus_nombres_cortos(self):
        self.assertEqual(self._curso("mp-primera").nombre_corto, "Primera vez")
        self.assertEqual(self._curso("mp-renovacion").nombre_corto, "Renovación")
        self.assertEqual(self._curso("mp-actualizacion").nombre_corto, "Renovación")

    def test_las_categorias_vaciadas_se_ocultan(self):
        Categoria = self.apps.get_model("cursos", "Categoria")
        self.assertFalse(Categoria.objects.get(slug="renovacion").activa)
        self.assertFalse(Categoria.objects.get(slug="ampliacion").activa)
        self.assertTrue(Categoria.objects.get(slug="cargas-generales").activa)


class ReagruparSinDatosTests(MigracionTestCase):
    """En una base vacía, o con otras categorías, la migración no falla."""
    desde = [("cursos", "0010_sacar_cupo_instructor_y_estado")]
    hasta = [("cursos", "0011_nombre_corto_y_bloques")]

    def armar(self, apps):
        Categoria = apps.get_model("cursos", "Categoria")
        Curso = apps.get_model("cursos", "Curso")
        otra = Categoria.objects.create(nombre="Renovación", slug="renovacion")
        Curso.objects.create(categoria=otra, nombre="Renovación", slug="renovacion")

    def test_sin_cargas_generales_no_mueve_nada(self):
        curso = self.apps.get_model("cursos", "Curso").objects.select_related("categoria").get(slug="renovacion")
        self.assertEqual(curso.categoria.slug, "renovacion")
        self.assertTrue(curso.categoria.activa)
```

- [ ] **Paso 2:** Correr → FALLAN.
- [ ] **Paso 3: Modelo y migración.** En `Curso`:

```python
    nombre_corto = models.CharField(
        "nombre corto", max_length=40, blank=True,
        help_text="Texto del botón del curso en la web. Ej: Inicial, Renovación.",
    )

    @property
    def nombre_boton(self):
        return self.nombre_corto or self.nombre
```

`makemigrations cursos -n nombre_corto_y_bloques` y agregar al final de `operations`:

```python
def reagrupar(apps, schema_editor):
    Categoria = apps.get_model("cursos", "Categoria")
    Curso = apps.get_model("cursos", "Curso")

    def corto(curso, texto, orden=None):
        if not curso.nombre_corto:
            curso.nombre_corto = texto
        if orden is not None:
            curso.orden = orden
        curso.save()

    generales = Categoria.objects.filter(slug="cargas-generales").first()
    if generales:
        for curso in Curso.objects.filter(categoria=generales):
            corto(curso, "Inicial", 1)
        for slug, texto, orden in (("renovacion", "Renovación", 2), ("ampliacion", "Ampliación", 3)):
            vieja = Categoria.objects.filter(slug=slug).first()
            if not vieja:
                continue
            for curso in Curso.objects.filter(categoria=vieja):
                curso.categoria = generales
                corto(curso, texto, orden)
            vieja.activa = False
            vieja.save()

    for curso in Curso.objects.filter(categoria__slug="mercancias-peligrosas"):
        nombre = curso.nombre.lower()
        corto(curso, "Primera vez" if "primera vez" in nombre else "Renovación")
```

con `migrations.RunPython(reagrupar, migrations.RunPython.noop)`. Si en Cargas Generales ya hay más de un curso, todos reciben «Inicial»: es aceptable porque el campo se corrige desde el panel; anotarlo en el resumen final.

- [ ] **Paso 4: Panel.** `CursoForm.Meta.fields` suma `nombre_corto` después de `nombre`; en `curso_form.html`, sección «1. Identificación», debajo del nombre.
- [ ] **Paso 5: Vista.** `web/views.py`, `_contexto_catalogo`:

```python
def _contexto_catalogo(request):
    """La grilla por bloques. Con `?curso=` se ve sólo ese curso; uno que no existe se ignora."""
    bloques = _catalogo()
    elegido = request.GET.get("curso", "")
    slugs = {curso.slug for bloque in bloques for curso in bloque["cursos"]}
    return {"catalogo": bloques, "curso_actual": elegido if elegido in slugs else ""}
```

- [ ] **Paso 6: Plantilla** `_catalogo.html` (el resto de la tarjeta no cambia):

```django
<script src="{% static 'js/filtros.js' %}" defer></script>
<div id="cursos-lista">
{% for bloque in catalogo %}
  <div class="categoria bloque bloque--{{ forloop.counter }}">
    <div class="categoria__titulo">
      {% if bloque.categoria.icono %}
        <img class="categoria__icono" src="{{ bloque.categoria.icono.url }}" alt="" height="36">
      {% endif %}
      <h3>{{ bloque.categoria.nombre }}</h3>
    </div>
    {% if bloque.categoria.resumen %}<p class="categoria__resumen">{{ bloque.categoria.resumen }}</p>{% endif %}
    <div class="botones-curso">
      {% for curso in bloque.cursos %}
        {% if curso_actual == curso.slug %}<a class="boton-curso boton-curso--activo" aria-current="true" href="{{ url_base }}#cursos-lista" data-curso="{{ curso.slug }}">{{ curso.nombre_boton }}</a>
        {% else %}<a class="boton-curso" href="{{ url_base }}?curso={{ curso.slug }}#cursos-lista" data-curso="{{ curso.slug }}">{{ curso.nombre_boton }}</a>{% endif %}
      {% endfor %}
    </div>
    <div class="grilla-cursos">
      {% for curso in bloque.cursos %}
        <article class="tarjeta-curso" data-curso="{{ curso.slug }}"{% if curso_actual and curso_actual != curso.slug %} hidden{% endif %}>
          …
        </article>
      {% endfor %}
    </div>
  </div>
{% empty %}
  <p class="categoria__resumen" style="margin-top:28px">No hay cursos publicados. Escribinos por WhatsApp y te informamos las próximas fechas.</p>
{% endfor %}
</div>
```

Ajustar el orden de los atributos del enlace activo al que espera `test_el_boton_activo_vuelve_a_mostrar_todo`. Se va el chip «N cursos» (`conteo_texto` queda sin uso: borrarlo del modelo y su prueba).

- [ ] **Paso 7: JavaScript.** Reescribir `static/js/filtros.js`:

```javascript
// Muestra un solo curso sin recargar la página. La dirección se actualiza
// igual, así se puede compartir. Sin JavaScript, los botones son enlaces.
(function () {
  var lista = document.getElementById("cursos-lista");
  if (!lista) return;
  var botones = lista.querySelectorAll(".boton-curso");
  var tarjetas = lista.querySelectorAll(".tarjeta-curso[data-curso]");

  function aplicar(slug) {
    botones.forEach(function (boton) {
      var activo = boton.dataset.curso === slug;
      boton.classList.toggle("boton-curso--activo", activo);
      if (activo) boton.setAttribute("aria-current", "true");
      else boton.removeAttribute("aria-current");
    });
    tarjetas.forEach(function (tarjeta) {
      tarjeta.hidden = Boolean(slug) && tarjeta.dataset.curso !== slug;
    });
  }

  lista.addEventListener("click", function (evento) {
    var boton = evento.target.closest(".boton-curso");
    if (!boton || evento.metaKey || evento.ctrlKey || evento.shiftKey) return;
    evento.preventDefault();
    // Tocar el botón activo lo apaga y vuelven a verse todos.
    var slug = boton.classList.contains("boton-curso--activo") ? "" : boton.dataset.curso;
    aplicar(slug);
    var url = new URL(window.location.href);
    if (slug) url.searchParams.set("curso", slug);
    else url.searchParams.delete("curso");
    url.searchParams.delete("categoria");
    url.hash = "cursos-lista";
    history.replaceState(null, "", url);
  });
})();
```

- [ ] **Paso 8: Estilos** en `web.css`; borrar `.filtros`, `.filtro*`, `.chip-conteo`. Cada bloque es una tarjeta con borde superior de su color; los botones son grandes (mínimo 44 px de alto) y pasan a una columna en el celular:

```css
.bloque {
  --acento: var(--azul-profundo);
  margin-top: 26px; padding: 22px clamp(16px, 3vw, 28px) 26px; background: #ffffff;
  border: 1px solid var(--borde); border-top: 5px solid var(--acento); border-radius: 8px;
}
.bloque--2 { --acento: #c2410c; }
.bloque--3 { --acento: #15803d; }
.bloque .categoria__titulo h3 { color: var(--acento); }
.botones-curso { display: flex; flex-wrap: wrap; gap: 10px; margin: 16px 0 4px; }
.boton-curso {
  flex: 1 1 180px; min-height: 48px; display: flex; align-items: center; justify-content: center;
  padding: 10px 16px; text-align: center; font-weight: 700; font-size: 16px; line-height: 1.25;
  color: var(--acento); background: #ffffff; border: 2px solid var(--acento); border-radius: 6px;
}
.boton-curso:hover { text-decoration: none; background: color-mix(in srgb, var(--acento) 8%, #ffffff); }
.boton-curso--activo, .boton-curso--activo:hover { color: #ffffff; background: var(--acento); }
.tarjeta-curso[hidden] { display: none; }
```

Verificar contraste del texto de los tres acentos sobre blanco y de blanco sobre cada acento (≥ 4,5:1).

- [ ] **Paso 9:** `cargar_datos.py`: los cursos de ejemplo llevan `nombre_corto` y quedan repartidos en tres categorías (Cargas Generales con Inicial, Renovación y Ampliación; Mercancías Peligrosas con Primera vez y Renovación; Transporte de Pasajeros con uno). Borrar de ahí las categorías «Renovación», «Ampliación» y «Renovaciones y ampliaciones».
- [ ] **Paso 10:** Batería en verde. En el navegador: tocar cada botón, volver a tocarlo, recargar con `?curso=`, probar con JavaScript desactivado y a 380 px. Commit: «Agrupar los cursos en bloques con un botón por curso».

---

### Tarea 8: Logo más grande, con la razón social

**Files:**
- Modify: `templates/web/base.html`, `static/css/web.css`, `web/tests.py`

- [ ] **Paso 1: Prueba que falla.** En `web/tests.py`, reemplazar `test_la_web_usa_el_logo_sin_la_razon_social` por:

```python
    def test_el_encabezado_muestra_la_razon_social(self):
        respuesta = self.client.get("/")
        self.assertContains(respuesta, '<span class="marca__razon">')
        self.assertContains(
            respuesta, "Cámara Empresaria del Transporte Automotor de Cargas de Entre Ríos"
        )
```

- [ ] **Paso 2:** Correr → FALLA.
- [ ] **Paso 3: Encabezado.** La razón social va como texto, no dentro de la imagen, para que se lea en cualquier tamaño y la encuentren los buscadores. En `base.html`, dentro de `.marca__enlace`, después del `<img>`:

```django
<span class="marca__razon">Cámara Empresaria del Transporte Automotor de Cargas de Entre Ríos</span>
```

El texto es fijo: `sitio.descripcion_larga` está en mayúsculas y lo edita el personal para la pantalla de ingreso.

- [ ] **Paso 4: Estilos.**

```css
.marca__enlace { display: flex; align-items: center; gap: 14px; }
.marca__enlace:hover { text-decoration: none; }
.marca__logo { display: block; width: auto; height: 96px; }
.marca__razon {
  max-width: 250px; font-size: 14px; font-weight: 600; line-height: 1.3; color: var(--azul-profundo);
}
@media (max-width: 560px) {
  .marca__logo { height: 72px; }
  .marca__razon { max-width: 170px; font-size: 12.5px; }
}
```

Mirar el encabezado a 1280, 768 y 380 px: el menú no debe montarse sobre la marca. Si a 380 px no entra, la razón social baja a una línea propia debajo del logo (`flex-wrap: wrap` en `.marca__enlace`).

- [ ] **Paso 5:** Batería en verde. Commit: «Agrandar el logo y sumar la razón social al encabezado».

---

### Tarea 9: Manual, datos de ejemplo y README

**Files:**
- Modify: `templates/panel/ayuda.html`, `templates/panel/ayuda/01_ingresar.html`, `02_agenda.html`, `03_cursos.html`, `09_paginas.html` → `05_paginas.html`, `11_administracion.html` → `06_administracion.html`, `12_referencia.html` → `07_referencia.html`, `panel/tests.py`, `README.md`
- Create: `templates/panel/ayuda/04_fechas.html`
- Delete: `templates/panel/ayuda/04_comisiones.html`, `05_inscribir.html`, `06_asistencia.html`, `07_inscripciones.html`, `08_personas.html`, `10_informes.html`; capturas `asistencia`, `comision-detalle`, `comision-estado`, `comision-nueva`, `comision-participantes`, `comisiones`, `empresa-nueva`, `empresas`, `informes`, `inscribir`, `inscripcion-editar`, `inscripciones`, `participante-ficha`, `participantes`

- [ ] **Paso 1: Prueba.** En `panel/tests.py`: `CAPITULOS = ["ingresar", "agenda", "cursos", "fechas", "paginas", "administracion", "referencia"]`; `test_todas_las_capturas_existen` baja el mínimo a `assertGreater(len(capturas), 10)`; agregar:

```python
    def test_el_manual_no_menciona_lo_que_se_saco(self):
        html = self._manual(JERARQUIA[0]).content.decode().lower()
        for palabra in ("comisi", "inscrip", "participante", "empresa", "asistencia", "cupo", "instructor", "informes"):
            with self.subTest(palabra=palabra):
                self.assertNotIn(palabra, html)
```

(«Empresaria» de la razón social no aparece en el panel; si el pie o el logo la incluyeran, afinar la palabra a `"empresas"`.)

- [ ] **Paso 2:** Correr → FALLA.
- [ ] **Paso 3: Contenido.**
  - `ayuda.html`: las tarjetas rápidas pasan a dos —«1. Subir una fecha» (Fechas → + Nueva fecha → elegir curso y día → Guardar; queda publicada) y «2. Marcar una fecha como completa» (Fechas o Tablero → «Marcar completa»; para deshacer, «Marcar disponible»)—; índice con los siete capítulos.
  - `01_ingresar.html`: tabla del menú sin Inscripciones, Participantes ni Informes y con «Fechas»; Tablero con los tres indicadores y las acciones rápidas; quitar la nota del rol Instructor.
  - `02_agenda.html`: colores verde/rojo/gris; el recuadro abre la edición de la fecha.
  - `03_cursos.html`: quitar cupo sugerido y texto del cupo; sumar «nombre corto» (el texto del botón en la web) y explicar que cada categoría es un bloque de la web; «comisión» → «fecha».
  - `04_fechas.html` (nuevo, `id="fechas"`): qué es una fecha; el listado y sus pestañas; subir una fecha paso a paso; **Disponible, Completo y Oculta** en una tabla con qué ve el público en cada caso; las acciones rápidas; que las fechas pasadas salen solas de la web; editar y eliminar.
  - `05_paginas.html`, `06_administracion.html`: renumerar títulos e `id`; en administración, sólo dos roles.
  - `07_referencia.html`: tabla de roles; «Quién puede hacer cada tarea» con dos filas (Administración: cursos, categorías, fechas y páginas; Dirección: además usuarios y configuración); glosario con Curso, Categoría, Fecha, Disponible, Completo, Oculta; quitar «Los colores de las barras».
- [ ] **Paso 4: Capturas.** Con el servidor de desarrollo sobre una copia de la base recién cargada con `cargar_datos --demo` (así no hay personas reales), retomar con Chrome sin interfaz: `ingresar`, `menu`, `tablero`, `agenda`, `cursos`, `curso-editar`, `categorias`, `fechas`, `fecha-nueva`, `fecha-acciones` (recorte de una fila con sus botones), `paginas`, `pagina-editar`, `enlace-error`, `usuarios`, `usuario-nuevo`, `usuario-eliminar`, `configuracion`. Borrar las capturas listadas en *Files*. Actualizar `ancho`/`alto` de cada `include`.
- [ ] **Paso 5: README.** Actualizar la tabla de comandos, la estructura de apps (`inscripciones/` «sólo migraciones históricas»), el glosario (Fecha), la tabla de roles (dos) y la lista de funciones; quitar la mención a `comisiones_visibles`.
- [ ] **Paso 6:** Batería en verde. Commit: «Reescribir el manual para el panel de cursos y fechas».

---

### Tarea 10: Verificación final y publicación

- [ ] **Paso 1:** `manage.py test` completo, `manage.py makemigrations --check --dry-run` y `manage.py check --deploy` sin novedades.
- [ ] **Paso 2: Ensayo de la migración** sobre la copia guardada en el Paso 0 de la Tarea 3 (apuntando `DATABASES` a una copia de esa copia): `migrate` termina sin errores; comparar a mano cinco fechas (visible/completa) contra su estado, cupo e inscriptos anteriores.
- [ ] **Paso 3:** Recorrer en el navegador: portada, `/cursos/`, una ficha, y en el panel Tablero, Agenda, Fechas (alta, completa, ocultar, editar, eliminar), Cursos, Páginas, Usuarios, Configuración y Cómo se usa, con Dirección y con Administración.
- [ ] **Paso 4:** Revisión de código de toda la rama (`superpowers:requesting-code-review`).
- [ ] **Paso 5: Publicar**, con el visto bueno de Augusto:
  1. Correr en el VPS el respaldo como lo hace `deploy/cetacer-backup.service` (leer ese archivo para el comando y el usuario exactos) y confirmar que el volcado nuevo quedó en `/var/backups/cetacer/` con tamaño razonable.
  2. `git pull --rebase && git push`.
  3. `ssh cetacer-vps 'bash /srv/cetacer/app/deploy/actualizar.sh'`.
  4. Verificar `https://cetacer.com/salud/`, la portada (bloques, botones, estados, logo) y que `/panel/inscripciones/` responde 404 o redirige al ingreso.
- [ ] **Paso 6:** Avisar a Augusto qué revisar a mano en producción: nombres cortos de los cursos, que las fechas vigentes hayan quedado visibles y con el estado correcto, y qué usuarios quedaron sin rol.
