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
    list_display = ("curso", "fecha_inicio", "visible", "completa")
    list_filter = ("visible", "completa", "curso__categoria")
    date_hierarchy = "fecha_inicio"


admin.site.register(ConfiguracionSitio)
