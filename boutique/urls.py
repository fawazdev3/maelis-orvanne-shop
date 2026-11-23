from django.urls import path

from . import views

app_name = "boutique"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("boutique/", views.catalogue, name="catalogue"),
    path("boutique/<slug:slug>/", views.catalogue, name="categorie"),
    path("produit/<slug:slug>/", views.produit_detail, name="produit"),
    path("panier/", views.panier, name="panier"),
    path("commander/", views.commander, name="commander"),
    path("commande/<uuid:jeton>/merci/", views.merci, name="merci"),
    path("api/produits/", views.api_produits, name="api_produits"),
]
