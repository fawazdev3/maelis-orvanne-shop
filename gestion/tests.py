"""Tests du back-office.  Lancer avec :  python manage.py test"""
import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from boutique.models import Categorie, Commande, LigneCommande, Produit

MEDIA_TEMP = tempfile.mkdtemp()


def image_test():
    tampon = io.BytesIO()
    Image.new("RGB", (60, 60), (90, 23, 38)).save(tampon, "JPEG")
    return SimpleUploadedFile("the.jpg", tampon.getvalue(), content_type="image/jpeg")


@override_settings(MEDIA_ROOT=MEDIA_TEMP)
class BackOfficeTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TEMP, ignore_errors=True)

    def setUp(self):
        Utilisateur = get_user_model()
        self.gerant = Utilisateur.objects.create_user("gerant", password="motdepasse-test-123", is_staff=True)
        self.client_simple = Utilisateur.objects.create_user("visiteur", password="motdepasse-test-123")
        self.categorie = Categorie.objects.create(nom="Thés")
        self.produit = Produit.objects.create(categorie=self.categorie, nom="Thé vert", prix=3000)

    def connecter(self):
        self.client.login(username="gerant", password="motdepasse-test-123")

    def test_pages_protegees(self):
        reponse = self.client.get(reverse("gestion:tableau_de_bord"))
        self.assertEqual(reponse.status_code, 302)
        self.assertIn(reverse("gestion:connexion"), reponse["Location"])

    def test_visiteur_sans_droits_refuse(self):
        self.client.login(username="visiteur", password="motdepasse-test-123")
        self.assertEqual(self.client.get(reverse("gestion:tableau_de_bord")).status_code, 403)

    def test_connexion(self):
        reponse = self.client.post(
            reverse("gestion:connexion"), {"username": "gerant", "password": "motdepasse-test-123"}
        )
        self.assertRedirects(reponse, reverse("gestion:tableau_de_bord"))

    def test_toutes_les_pages_s_affichent(self):
        self.connecter()
        commande = Commande.objects.create(nom_client="Ama", telephone="90 00 00 00", ville="Lomé", lieu_livraison="Bè")
        LigneCommande.objects.create(commande=commande, produit=self.produit, nom_produit="Thé vert", prix_unitaire=3000, quantite=2)
        commande.recalculer_total()
        pages = [
            reverse("gestion:tableau_de_bord"),
            reverse("gestion:produits_liste"),
            reverse("gestion:produits_liste") + "?q=vert&filtre=visibles",
            reverse("gestion:produit_ajouter"),
            reverse("gestion:produit_modifier", args=[self.produit.pk]),
            reverse("gestion:produit_supprimer", args=[self.produit.pk]),
            reverse("gestion:categories_liste"),
            reverse("gestion:categorie_ajouter"),
            reverse("gestion:categorie_modifier", args=[self.categorie.pk]),
            reverse("gestion:categorie_supprimer", args=[self.categorie.pk]),
            reverse("gestion:commandes_liste"),
            reverse("gestion:commandes_liste") + "?statut=nouvelle&q=Ama",
            reverse("gestion:commande_detail", args=[commande.pk]),
            reverse("boutique:accueil"),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_ajout_produit_avec_photo_et_promo(self):
        self.connecter()
        reponse = self.client.post(
            reverse("gestion:produit_ajouter"),
            {"nom": "Thé oolong", "categorie": self.categorie.pk, "prix": 4500, "prix_promo": 3900,
             "actif": "on", "en_stock": "on", "image": image_test()},
        )
        self.assertRedirects(reponse, reverse("gestion:produits_liste"))
        produit = Produit.objects.get(nom="Thé oolong")
        self.assertTrue(produit.image)
        self.assertTrue(produit.en_promo)
        self.assertEqual(produit.prix_actuel, 3900)
        self.assertEqual(produit.pourcentage_remise, 13)

    def test_prix_promo_superieur_refuse(self):
        self.connecter()
        reponse = self.client.post(
            reverse("gestion:produit_modifier", args=[self.produit.pk]),
            {"nom": "Thé vert", "categorie": self.categorie.pk, "prix": 3000, "prix_promo": 3500},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "inférieur au prix normal")

    def test_basculer_visibilite(self):
        self.connecter()
        self.client.post(reverse("gestion:produit_basculer", args=[self.produit.pk, "actif"]))
        self.produit.refresh_from_db()
        self.assertFalse(self.produit.actif)

    def test_categorie_avec_produits_non_supprimable(self):
        self.connecter()
        self.client.post(reverse("gestion:categorie_supprimer", args=[self.categorie.pk]))
        self.assertTrue(Categorie.objects.filter(pk=self.categorie.pk).exists())

    def test_paiement_a_la_livraison(self):
        self.connecter()
        commande = Commande.objects.create(nom_client="Ama", telephone="90000000", ville="Lomé", lieu_livraison="Bè")
        self.assertEqual(commande.mode_paiement, Commande.ModePaiement.ESPECES)
        self.assertTrue(commande.a_encaisser)
        self.client.post(reverse("gestion:commande_paiement", args=[commande.pk]))
        commande.refresh_from_db()
        self.assertTrue(commande.paiement_recu)
        self.assertIsNotNone(commande.date_paiement)
        self.assertEqual(self.client.get(reverse("gestion:commandes_liste") + "?statut=a_encaisser").status_code, 200)
        self.client.post(reverse("gestion:commande_paiement", args=[commande.pk]))
        commande.refresh_from_db()
        self.assertFalse(commande.paiement_recu)
        self.assertIsNone(commande.date_paiement)

    def test_numero_commande_et_statut(self):
        self.connecter()
        commande = Commande.objects.create(nom_client="Kofi", telephone="+228 91 11 11 11", ville="Kara", lieu_livraison="Centre")
        self.assertTrue(commande.numero.startswith("MO-"))
        self.assertEqual(commande.telephone_whatsapp, "22891111111")
        self.client.post(reverse("gestion:commande_detail", args=[commande.pk]), {"statut": "confirmee", "mode_paiement": "mobile_money", "note_interne": ""})
        commande.refresh_from_db()
        self.assertEqual(commande.statut, "confirmee")
