"""Administration Django de secours (/admin-technique/).
Le back-office principal de la boutique est dans l'application « gestion » (/gestion/)."""
from django.contrib import admin

from .models import Categorie, Commande, LigneCommande, Produit


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("nom", "ordre", "active")
    prepopulated_fields = {"slug": ("nom",)}


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ("nom", "categorie", "prix", "prix_promo", "en_stock", "actif")
    list_filter = ("categorie", "actif", "en_stock")
    search_fields = ("nom",)


class LigneCommandeInline(admin.TabularInline):
    model = LigneCommande
    extra = 0


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ("numero", "nom_client", "telephone", "ville", "total", "statut", "date_creation")
    list_filter = ("statut",)
    search_fields = ("numero", "nom_client", "telephone")
    inlines = [LigneCommandeInline]


admin.site.site_header = "Maélis Orvanne Shop — administration technique"
