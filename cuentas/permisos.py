"""Mapa de permisos por grupo.

La jerarquía se implementa con los grupos nativos de Django: cada rol es un
grupo y recibe un conjunto de permisos del modelo. `sincronizar_grupos()` deja
los grupos exactamente como se describe acá, así que es seguro correrlo de nuevo
después de agregar modelos o cambiar la matriz.
"""
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from .models import Rol

TODOS = ("add", "change", "delete", "view")
LECTURA = ("view",)
ALTA_Y_EDICION = ("add", "change", "view")

#: rol -> {"app.modelo": (acciones,)}
MATRIZ = {
    Rol.DIRECCION: {
        "cursos.configuracionsitio": ("change", "view"),
        "cursos.categoria": TODOS,
        "cursos.curso": TODOS,
        "cursos.comision": TODOS,
        "inscripciones.empresa": TODOS,
        "inscripciones.participante": TODOS,
        "inscripciones.inscripcion": TODOS,
        "cuentas.usuario": TODOS,
        "auth.group": LECTURA,
    },
    Rol.ADMINISTRACION: {
        "cursos.configuracionsitio": ("change", "view"),
        "cursos.categoria": TODOS,
        "cursos.curso": TODOS,
        "cursos.comision": TODOS,
        "inscripciones.empresa": TODOS,
        "inscripciones.participante": TODOS,
        "inscripciones.inscripcion": TODOS,
        "cuentas.usuario": LECTURA,
    },
    Rol.COORDINACION: {
        "cursos.configuracionsitio": LECTURA,
        "cursos.categoria": LECTURA,
        "cursos.curso": ("change", "view"),
        "cursos.comision": TODOS,
        "inscripciones.empresa": ALTA_Y_EDICION,
        "inscripciones.participante": ALTA_Y_EDICION,
        "inscripciones.inscripcion": TODOS,
    },
    Rol.RECEPCION: {
        "cursos.configuracionsitio": LECTURA,
        "cursos.categoria": LECTURA,
        "cursos.curso": LECTURA,
        "cursos.comision": LECTURA,
        "inscripciones.empresa": ALTA_Y_EDICION,
        "inscripciones.participante": ALTA_Y_EDICION,
        "inscripciones.inscripcion": ALTA_Y_EDICION,
    },
    Rol.INSTRUCTOR: {
        "cursos.curso": LECTURA,
        "cursos.comision": LECTURA,
        "inscripciones.participante": LECTURA,
        "inscripciones.inscripcion": ("change", "view"),
    },
}


def sincronizar_grupos(verbose=False):
    """Crea (o actualiza) los cinco grupos con sus permisos. Idempotente."""
    resultado = []
    for rol, modelos in MATRIZ.items():
        grupo, creado = Group.objects.get_or_create(name=rol.value)
        permisos = []
        for etiqueta, acciones in modelos.items():
            app_label, modelo = etiqueta.split(".")
            try:
                tipo = ContentType.objects.get(app_label=app_label, model=modelo)
            except ContentType.DoesNotExist:
                continue
            for accion in acciones:
                codigo = f"{accion}_{modelo}"
                permiso = Permission.objects.filter(
                    content_type=tipo, codename=codigo
                ).first()
                if permiso:
                    permisos.append(permiso)
        grupo.permissions.set(permisos)
        resultado.append((rol.value, creado, len(permisos)))
        if verbose:
            estado = "creado" if creado else "actualizado"
            print(f"  {rol.value:<16} {estado:<12} {len(permisos)} permisos")
    return resultado
