from django.contrib import admin

from .models import Categoria, Comision, ConfiguracionSitio, Curso


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "orden", "activa")
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "categoria", "precio_texto", "activo")
    list_filter = ("categoria", "activo")
    search_fields = ("nombre",)
    prepopulated_fields = {"slug": ("nombre",)}


@admin.register(Comision)
class ComisionAdmin(admin.ModelAdmin):
    list_display = ("curso", "fecha_inicio", "cupo", "cantidad_inscriptos", "estado")
    list_filter = ("estado", "curso__categoria")
    date_hierarchy = "fecha_inicio"


admin.site.register(ConfiguracionSitio)
