"""Crée quelques données d'exemple pour essayer le back-office.

Utilisation :  python manage.py donnees_exemple
Tout ce qui est créé porte la mention « (exemple) » : supprimez-le depuis le back-office quand vous voulez.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from boutique.models import Categorie, Commande, LigneCommande, Produit


class Command(BaseCommand):
    help = "Crée une catégorie, trois produits et une commande d'exemple."

    @transaction.atomic
    def handle(self, *args, **options):
        categorie, _ = Categorie.objects.get_or_create(nom="Thés (exemple)", defaults={"ordre": 1})
        exemples = [
            ("Thé vert au jasmin (exemple)", 3000, None),
            ("Thé oolong (exemple)", 4500, 3900),
            ("Thé noir (exemple)", 2500, None),
        ]
        produits = []
        for nom, prix, promo in exemples:
            produit, _ = Produit.objects.get_or_create(
                nom=nom, defaults={"categorie": categorie, "prix": prix, "prix_promo": promo}
            )
            produits.append(produit)

        if not Commande.objects.filter(nom_client="Client test (exemple)").exists():
            commande = Commande.objects.create(
                nom_client="Client test (exemple)",
                telephone="90000000",
                ville="Lomé",
                lieu_livraison="Quartier et repère (exemple)",
            )
            for produit, quantite in ((produits[0], 2), (produits[1], 1)):
                LigneCommande.objects.create(
                    commande=commande,
                    produit=produit,
                    nom_produit=produit.nom,
                    prix_unitaire=produit.prix_actuel,
                    quantite=quantite,
                )
            commande.recalculer_total()

        self.stdout.write(self.style.SUCCESS("Données d'exemple créées. Ouvrez /gestion/ pour les voir."))
