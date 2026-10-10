"""Prueba de la migración que reduce los roles a dos."""
from cursos.tests_migraciones import MigracionTestCase


class DosRolesTests(MigracionTestCase):
    desde = [("cuentas", "0001_initial")]
    hasta = [("cuentas", "0002_dos_roles")]

    def armar(self, apps):
        Usuario = apps.get_model("cuentas", "Usuario")
        Group = apps.get_model("auth", "Group")
        for nombre in ("Dirección", "Administración", "Coordinación", "Recepción", "Instructor"):
            grupo, _ = Group.objects.get_or_create(name=nombre)
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
        self.assertEqual(self._grupos("sin-grupo"), [])

    def test_los_grupos_viejos_se_borran(self):
        Group = self.apps.get_model("auth", "Group")
        self.assertEqual(
            sorted(Group.objects.values_list("name", flat=True)), ["Administración", "Dirección"]
        )
