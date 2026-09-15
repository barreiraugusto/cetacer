from django.contrib.auth.models import AbstractUser, Group
from django.db import models


class Rol(models.TextChoices):
    """Jerarquía de acceso al panel. Cada valor es el nombre de un grupo de Django."""

    DIRECCION = "Dirección", "Dirección"
    ADMINISTRACION = "Administración", "Administración"
    COORDINACION = "Coordinación", "Coordinación"
    RECEPCION = "Recepción", "Recepción"
    INSTRUCTOR = "Instructor", "Instructor"


#: Orden jerárquico, de mayor a menor alcance. Un rol "alcanza" a todos los
#: que están por debajo suyo en esta lista.
JERARQUIA = [
    Rol.DIRECCION,
    Rol.ADMINISTRACION,
    Rol.COORDINACION,
    Rol.RECEPCION,
    Rol.INSTRUCTOR,
]

DESCRIPCION_ROLES = {
    Rol.DIRECCION: "Acceso total: cursos, comisiones, inscripciones, usuarios y configuración del sitio.",
    Rol.ADMINISTRACION: "Gestiona el catálogo completo, precios, comisiones, inscripciones y exportaciones.",
    Rol.COORDINACION: "Arma comisiones, asigna instructores y administra inscripciones. No edita precios ni usuarios.",
    Rol.RECEPCION: "Carga participantes, toma inscripciones y descarga listas. No modifica el catálogo.",
    Rol.INSTRUCTOR: "Ve únicamente sus comisiones asignadas y registra la asistencia.",
}


class Usuario(AbstractUser):
    """Usuario del panel. Los permisos concretos se otorgan por grupo."""

    telefono = models.CharField("teléfono", max_length=40, blank=True)
    dni = models.CharField("DNI", max_length=20, blank=True)
    cargo = models.CharField(
        "cargo", max_length=120, blank=True, help_text="Cómo figura la persona en la institución."
    )
    activo_desde = models.DateField("activo desde", auto_now_add=True)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["first_name", "last_name", "username"]

    def __str__(self):
        return self.nombre_completo

    @property
    def nombre_completo(self):
        completo = f"{self.first_name} {self.last_name}".strip()
        return completo or self.username

    @property
    def iniciales(self):
        partes = [p for p in (self.first_name, self.last_name) if p]
        if partes:
            return "".join(p[0] for p in partes[:2]).upper()
        return self.username[:2].upper()

    @property
    def rol(self):
        """Rol de mayor jerarquía del usuario, o None si no tiene ninguno."""
        if self.is_superuser:
            return Rol.DIRECCION
        nombres = {g.name for g in self.groups.all()}
        for rol in JERARQUIA:
            if rol.value in nombres:
                return rol
        return None

    @property
    def rol_nombre(self):
        rol = self.rol
        return rol.label if rol else "Sin rol asignado"

    def tiene_rol(self, *roles):
        """True si el rol del usuario es alguno de los indicados."""
        actual = self.rol
        return actual is not None and actual in roles

    def alcanza(self, rol_minimo):
        """True si el rol del usuario está al mismo nivel o por encima de `rol_minimo`."""
        actual = self.rol
        if actual is None:
            return False
        return JERARQUIA.index(actual) <= JERARQUIA.index(rol_minimo)

    def asignar_rol(self, rol):
        """Deja al usuario con un único grupo: el del rol indicado."""
        grupo, _ = Group.objects.get_or_create(name=rol.value if hasattr(rol, "value") else rol)
        self.groups.set([grupo])
        return grupo
