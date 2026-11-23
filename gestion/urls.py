from django.urls import path

from . import views, views_finances as finances, views_reglages as reglages

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
    # Livraison
    path("livraison/", views.livraison_tarifs, name="livraison_tarifs"),
    path("livraison/<int:pk>/modifier/", views.livraison_tarifs, name="livraison_tarif_modifier"),
    path("livraison/<int:pk>/supprimer/", views.livraison_tarif_supprimer, name="livraison_tarif_supprimer"),
    # Stock, dépenses, statistiques
    path("stock/", finances.stock, name="stock"),
    path("stock/arrivages/<int:pk>/supprimer/", finances.arrivage_supprimer, name="arrivage_supprimer"),
    path("depenses/", finances.depenses, name="depenses"),
    path("depenses/<int:pk>/", finances.depenses, name="depense_modifier"),
    path("depenses/<int:pk>/supprimer/", finances.depense_supprimer, name="depense_supprimer"),
    path("statistiques/", finances.statistiques, name="statistiques"),
    path("statistiques/export/", finances.statistiques_export, name="statistiques_export"),
    # Réglages et maintenance
    path("reglages/", reglages.reglages, name="reglages"),
    path("reglages/sauvegarde/", reglages.sauvegarde, name="sauvegarde"),
    path("reglages/retirer-exemples/", reglages.retirer_exemples, name="retirer_exemples"),
    # Équipe
    path("equipe/", views.equipe, name="equipe"),
    path("equipe/<int:pk>/", views.equipe, name="equipe_modifier"),
    path("equipe/<int:pk>/activer/", views.compte_basculer, name="compte_basculer"),
    path("equipe/<int:pk>/supprimer/", views.compte_supprimer, name="compte_supprimer"),
    path("equipe/roles/nouveau/", views.role_form, name="role_ajouter"),
    path("equipe/roles/<int:pk>/", views.role_form, name="role_modifier"),
    path("equipe/roles/<int:pk>/supprimer/", views.role_supprimer, name="role_supprimer"),
    # Commandes
    path("commandes/", views.commandes_liste, name="commandes_liste"),
    path("commandes/<int:pk>/", views.commande_detail, name="commande_detail"),
    path("commandes/<int:pk>/paiement/", views.commande_paiement, name="commande_paiement"),
    path("commandes/<int:pk>/supprimer/", views.commande_supprimer, name="commande_supprimer"),
]
