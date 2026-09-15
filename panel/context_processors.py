def rol_usuario(request):
    """Expone el rol del usuario a todas las plantillas del panel."""
    usuario = getattr(request, "user", None)
    if not usuario or not usuario.is_authenticated:
        return {"rol_actual": None, "rol_nombre": ""}
    return {"rol_actual": usuario.rol, "rol_nombre": usuario.rol_nombre}
