from django.urls import path

from . import views

app_name = "boutique"

urlpatterns = [
    path("", views.accueil, name="accueil"),
]
