from django.contrib import admin

from .models import Empresa, Inscripcion, Participante


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "cuit", "localidad", "socia")
    search_fields = ("razon_social", "cuit")


@admin.register(Participante)
class ParticipanteAdmin(admin.ModelAdmin):
    list_display = ("apellido", "nombre", "dni", "empresa", "localidad")
    search_fields = ("apellido", "nombre", "dni")
    list_filter = ("empresa", "localidad")


@admin.register(Inscripcion)
class InscripcionAdmin(admin.ModelAdmin):
    list_display = ("participante", "comision", "estado", "pago", "creado")
    list_filter = ("estado", "pago", "comision__curso__categoria")
    search_fields = ("participante__apellido", "participante__dni")
