from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "nombre_completo", "email", "rol_nombre", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Datos CETACER", {"fields": ("telefono", "dni", "cargo")}),
    )
