from django.urls import path

from . import views

app_name = "web"

urlpatterns = [
    path("", views.inicio, name="inicio"),
    path("info/<slug:slug>/", views.pagina, name="pagina"),
    path("cursos/", views.catalogo, name="catalogo"),
    path("cursos/<slug:slug>/", views.curso_detalle, name="curso"),
    path("cursos/<slug:slug>/inscripcion/", views.preinscripcion, name="preinscripcion"),
    path("inscripcion/gracias/", views.preinscripcion_ok, name="preinscripcion_ok"),
]
