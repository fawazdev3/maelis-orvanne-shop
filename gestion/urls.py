from django.urls import path

from . import views

app_name = "gestion"

urlpatterns = [
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", views.DeconnexionView.as_view(), name="deconnexion"),
    path("", views.tableau_de_bord, name="tableau_de_bord"),
    # Produits
    path("produits/", views.produits_liste, name="produits_liste"),
    path("produits/ajouter/", views.produit_ajouter, name="produit_ajouter"),
    path("produits/<int:pk>/modifier/", views.produit_modifier, name="produit_modifier"),
    path("produits/<int:pk>/supprimer/", views.produit_supprimer, name="produit_supprimer"),
    path("produits/<int:pk>/basculer/<str:champ>/", views.produit_basculer, name="produit_basculer"),
    # Catégories
    path("categories/", views.categories_liste, name="categories_liste"),
    path("categories/ajouter/", views.categorie_ajouter, name="categorie_ajouter"),
    path("categories/<int:pk>/modifier/", views.categorie_modifier, name="categorie_modifier"),
    path("categories/<int:pk>/supprimer/", views.categorie_supprimer, name="categorie_supprimer"),
    # Commandes
    path("commandes/", views.commandes_liste, name="commandes_liste"),
    path("commandes/<int:pk>/", views.commande_detail, name="commande_detail"),
    path("commandes/<int:pk>/paiement/", views.commande_paiement, name="commande_paiement"),
]
