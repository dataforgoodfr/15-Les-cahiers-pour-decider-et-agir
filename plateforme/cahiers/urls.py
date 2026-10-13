from django.urls import path

from . import views

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("contributions/<int:pk>/extrait.pdf", views.extrait, name="extrait"),
]
