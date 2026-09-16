"""Control de acceso del panel, apoyado en la jerarquía de roles de `cuentas`."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from cuentas.models import Rol


def _sin_permiso(request):
    messages.error(
        request,
        "Tu rol no tiene acceso a esa sección. Si necesitás entrar, pedíselo a Dirección.",
    )
    return redirect("panel:inicio")


def requiere_rol(*roles):
    """Permite la vista sólo a los roles indicados (o a un superusuario)."""

    def decorador(vista):
        @wraps(vista)
        def envoltorio(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser or request.user.tiene_rol(*roles):
                return vista(request, *args, **kwargs)
            return _sin_permiso(request)

        return envoltorio

    return decorador


def requiere_nivel(rol_minimo):
    """Permite la vista a ese rol y a todos los que están por encima."""

    def decorador(vista):
        @wraps(vista)
        def envoltorio(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.is_superuser or request.user.alcanza(rol_minimo):
                return vista(request, *args, **kwargs)
            return _sin_permiso(request)

        return envoltorio

    return decorador


def requiere_panel(vista):
    """Acceso base: cualquier usuario con un rol asignado."""

    @wraps(vista)
    def envoltorio(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if request.user.is_superuser or request.user.rol is not None:
            return vista(request, *args, **kwargs)
        messages.error(
            request,
            "Tu usuario todavía no tiene un rol asignado. Contactá a Dirección.",
        )
        raise PermissionDenied("Usuario sin rol")

    return envoltorio


# Atajos de lectura para las vistas.
SOLO_DIRECCION = requiere_rol(Rol.DIRECCION)
GESTION_CATALOGO = requiere_nivel(Rol.ADMINISTRACION)
GESTION_COMISIONES = requiere_nivel(Rol.COORDINACION)
GESTION_INSCRIPCIONES = requiere_nivel(Rol.RECEPCION)
LECTURA_INSTITUCIONAL = requiere_nivel(Rol.RECEPCION)


def comisiones_visibles(usuario, queryset):
    """Un instructor sólo ve sus propias comisiones; el resto ve todas."""
    if usuario.is_superuser:
        return queryset
    if usuario.tiene_rol(Rol.INSTRUCTOR):
        return queryset.filter(instructor=usuario)
    return queryset
