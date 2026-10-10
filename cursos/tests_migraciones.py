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
        self.sin_cupo = comision("publicada", cupo=0)

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

    def test_un_cupo_en_cero_sigue_completa_como_la_mostraba_la_web(self):
        # Con cupo 0 la web ya decía «Completo»: la migración no cambia lo que
        # ve el público. Si era un error de carga, se arregla con un clic.
        self.assertTrue(self._fecha(self.sin_cupo).completa)


class ReagruparCursosTests(MigracionTestCase):
    desde = [("cursos", "0010_sacar_cupo_instructor_y_estado")]
    hasta = [("cursos", "0011_nombre_corto_y_bloques")]

    def armar(self, apps):
        Categoria = apps.get_model("cursos", "Categoria")
        Curso = apps.get_model("cursos", "Curso")

        def categoria(nombre, slug, orden):
            return Categoria.objects.create(nombre=nombre, slug=slug, orden=orden)

        def curso(cat, nombre, slug):
            return Curso.objects.create(categoria=cat, nombre=nombre, slug=slug)

        generales = categoria("Cargas Generales", "cargas-generales", 1)
        peligrosas = categoria("Mercancías Peligrosas", "mercancias-peligrosas", 2)
        curso(generales, "Curso Primera vez — Cargas Generales y/o Pasajeros", "inicial")
        curso(peligrosas, "Curso primera vez — Mercancías Peligrosas", "mp-primera")
        curso(peligrosas, "Curso Renovación — Mercancías Peligrosas", "mp-renovacion")
        curso(categoria("Renovación", "renovacion", 3), "Renovación — Cargas Generales y/o Pasajeros", "renovacion")
        curso(categoria("Ampliación", "ampliacion", 4), "Ampliación — Cargas Generales y/o Pasajeros", "ampliacion")
        otra = categoria("Transporte de Pasajeros", "transporte-de-pasajeros", 5)
        curso(otra, "Curso primera vez — Pasajeros", "pasajeros")

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

    def test_las_categorias_vaciadas_se_ocultan(self):
        Categoria = self.apps.get_model("cursos", "Categoria")
        self.assertFalse(Categoria.objects.get(slug="renovacion").activa)
        self.assertFalse(Categoria.objects.get(slug="ampliacion").activa)
        self.assertTrue(Categoria.objects.get(slug="cargas-generales").activa)

    def test_las_demas_categorias_no_se_tocan(self):
        curso = self._curso("pasajeros")
        self.assertEqual(curso.categoria.slug, "transporte-de-pasajeros")
        self.assertEqual(curso.nombre_corto, "")
        self.assertTrue(curso.categoria.activa)


class ReagruparSinCargasGeneralesTests(MigracionTestCase):
    """Con otras categorías, o con la base vacía, la migración no falla ni mueve nada."""

    desde = [("cursos", "0010_sacar_cupo_instructor_y_estado")]
    hasta = [("cursos", "0011_nombre_corto_y_bloques")]

    def armar(self, apps):
        Categoria = apps.get_model("cursos", "Categoria")
        Curso = apps.get_model("cursos", "Curso")
        otra = Categoria.objects.create(nombre="Renovación", slug="renovacion")
        Curso.objects.create(categoria=otra, nombre="Renovación", slug="renovacion")

    def test_sin_cargas_generales_no_mueve_nada(self):
        Curso = self.apps.get_model("cursos", "Curso")
        curso = Curso.objects.select_related("categoria").get(slug="renovacion")
        self.assertEqual(curso.categoria.slug, "renovacion")
        self.assertTrue(curso.categoria.activa)


class ReagruparConVariosCursosTests(MigracionTestCase):
    """Si no se puede saber qué curso es cuál, el nombre corto queda vacío."""

    desde = [("cursos", "0010_sacar_cupo_instructor_y_estado")]
    hasta = [("cursos", "0011_nombre_corto_y_bloques")]

    def armar(self, apps):
        Categoria = apps.get_model("cursos", "Categoria")
        Curso = apps.get_model("cursos", "Curso")
        generales = Categoria.objects.create(nombre="Cargas Generales", slug="cargas-generales")
        peligrosas = Categoria.objects.create(nombre="Mercancías Peligrosas", slug="mercancias-peligrosas")
        renovacion = Categoria.objects.create(nombre="Renovación", slug="renovacion")
        Curso.objects.create(categoria=generales, nombre="Curso primera vez", slug="g1")
        Curso.objects.create(categoria=generales, nombre="Otro curso", slug="g2")
        Curso.objects.create(categoria=renovacion, nombre="Renovación A", slug="r1")
        Curso.objects.create(categoria=renovacion, nombre="Renovación B", slug="r2")
        Curso.objects.create(categoria=peligrosas, nombre="Curso básico nuevo", slug="p1")
        Curso.objects.create(categoria=peligrosas, nombre="Curso Renovación", slug="p3")
        Curso.objects.create(categoria=peligrosas, nombre="Curso actualización", slug="p4")

    def _curso(self, slug):
        return self.apps.get_model("cursos", "Curso").objects.select_related("categoria").get(slug=slug)

    def test_dos_cursos_en_cargas_generales_no_reciben_inicial(self):
        self.assertEqual(self._curso("g1").nombre_corto, "")
        self.assertEqual(self._curso("g2").nombre_corto, "")

    def test_dos_cursos_de_renovacion_se_mudan_sin_nombre_corto(self):
        for slug in ("r1", "r2"):
            self.assertEqual(self._curso(slug).categoria.slug, "cargas-generales")
            self.assertEqual(self._curso(slug).nombre_corto, "")

    def test_un_curso_de_peligrosas_que_no_se_reconoce_queda_sin_nombre_corto(self):
        self.assertEqual(self._curso("p1").nombre_corto, "")

    def test_dos_renovaciones_de_peligrosas_quedan_sin_nombre_corto(self):
        self.assertEqual(self._curso("p3").nombre_corto, "")
        self.assertEqual(self._curso("p4").nombre_corto, "")


class ReagruparConCargasGeneralesOcultaTests(MigracionTestCase):
    """Mudar cursos a una categoría oculta los sacaría de la web: no se mudan."""

    desde = [("cursos", "0010_sacar_cupo_instructor_y_estado")]
    hasta = [("cursos", "0011_nombre_corto_y_bloques")]

    def armar(self, apps):
        Categoria = apps.get_model("cursos", "Categoria")
        Curso = apps.get_model("cursos", "Curso")
        Categoria.objects.create(nombre="Cargas Generales", slug="cargas-generales", activa=False)
        renovacion = Categoria.objects.create(nombre="Renovación", slug="renovacion")
        Curso.objects.create(categoria=renovacion, nombre="Renovación", slug="renovacion")

    def test_los_cursos_se_quedan_donde_estan(self):
        Curso = self.apps.get_model("cursos", "Curso")
        curso = Curso.objects.select_related("categoria").get(slug="renovacion")
        self.assertEqual(curso.categoria.slug, "renovacion")
        self.assertTrue(curso.categoria.activa)
