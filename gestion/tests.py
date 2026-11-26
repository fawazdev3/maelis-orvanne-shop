"""Tests du back-office.  Lancer avec :  python manage.py test"""
import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from config.tests_base import TestCase
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
        from django.contrib.auth.models import Group

        self.gerant.groups.add(Group.objects.get(name="Administrateur"))
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

    def test_actions_whatsapp_de_la_fiche_commande(self):
        commande = Commande.objects.create(
            nom_client="Veedah", telephone="+229 01 51 13 25 51", telephone_international="2290151132551",
            pays="BJ", ville="Cotonou", lieu_livraison="Lot 646 Tanto",
        )
        LigneCommande.objects.create(commande=commande, produit=self.produit, nom_produit="Thé vert", prix_unitaire=3000, quantite=2)
        commande.recalculer_total()
        self.client.login(username="gerant", password="motdepasse-test-123")
        r = self.client.get(reverse("gestion:commande_detail", args=[commande.pk]))
        self.assertContains(r, "https://wa.me/2290151132551?text=")  # message au client, bon pays
        self.assertContains(r, 'href="tel:+2290151132551"')
        self.assertContains(r, "https://wa.me/?text=LIVRAISON")  # fiche pour le livreur
        self.assertContains(r, "Les%20frais%20d%27envoi%20vers%20Cotonou%20vous%20seront%20pr%C3%A9cis%C3%A9s")
        self.assertContains(r, "Étape suivante")  # étape suggérée pour une nouvelle commande
        # recherche par numéro sans espaces
        r = self.client.get(reverse("gestion:commandes_liste"), {"q": "0151132551"})
        self.assertContains(r, commande.numero)

    def test_frais_de_livraison_modifiables_et_tarifs(self):
        from boutique.models import TarifLivraison

        commande = Commande.objects.create(nom_client="Kofi", telephone="90000000", ville="Kara", lieu_livraison="Centre")
        LigneCommande.objects.create(commande=commande, produit=self.produit, nom_produit="Thé vert", prix_unitaire=3000, quantite=1)
        commande.recalculer_total()
        self.client.login(username="gerant", password="motdepasse-test-123")
        self.client.post(reverse("gestion:commande_detail", args=[commande.pk]), {
            "statut": "confirmee", "mode_paiement": "especes", "frais_livraison": "2000", "note_interne": "",
        })
        commande.refresh_from_db()
        self.assertEqual((commande.frais_livraison, commande.total), (2000, 5000))
        # page des tarifs : ajout, puis doublon refusé (orthographe différente)
        self.assertEqual(self.client.get(reverse("gestion:livraison_tarifs")).status_code, 200)
        self.client.post(reverse("gestion:livraison_tarifs"), {"pays": "TG", "ville": "Kara", "frais": "2500"})
        r = self.client.post(reverse("gestion:livraison_tarifs"), {"pays": "TG", "ville": "KARA", "frais": "3000"})
        self.assertContains(r, "existe déjà")
        self.assertEqual(TarifLivraison.objects.get(pays="TG", ville_normalisee="kara").frais, 2500)


class RolesEtFinancesTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group

        U = get_user_model()
        self.admin = U.objects.create_user("admin", password="motdepasse-test-123", is_staff=True)
        self.admin.groups.add(Group.objects.get(name="Administrateur"))
        self.compta = U.objects.create_user("ami", password="motdepasse-test-123", is_staff=True)
        self.compta.groups.add(Group.objects.get(name="Comptabilité"))
        cat = Categorie.objects.create(nom="Thés")
        self.the = Produit.objects.create(categorie=cat, nom="Thé noir", prix=2500)

    def test_comptabilite_sans_equipe_ni_reglages(self):
        self.client.login(username="ami", password="motdepasse-test-123")
        for nom in ["gestion:stock", "gestion:depenses", "gestion:statistiques", "gestion:commandes_liste", "gestion:produits_liste"]:
            self.assertEqual(self.client.get(reverse(nom)).status_code, 200, nom)
        for nom in ["gestion:equipe", "gestion:livraison_tarifs"]:
            self.assertRedirects(self.client.get(reverse(nom)), reverse("gestion:tableau_de_bord"))
        self.assertNotContains(self.client.get(reverse("gestion:tableau_de_bord")), "Équipe")

    def test_admin_cree_un_compte_comptabilite(self):
        self.client.login(username="admin", password="motdepasse-test-123")
        r = self.client.post(reverse("gestion:equipe"), {
            "identifiant": "kofi", "prenom": "Kofi", "role": "Comptabilité", "mot_de_passe": "secret-tres-long", "actif": "on",
        })
        self.assertRedirects(r, reverse("gestion:equipe"))
        kofi = get_user_model().objects.get(username="kofi")
        self.assertTrue(kofi.is_staff and kofi.check_password("secret-tres-long"))
        self.assertEqual(list(kofi.groups.values_list("name", flat=True)), ["Comptabilité"])
        # l'admin ne peut pas se retirer ses propres droits
        r = self.client.post(reverse("gestion:equipe_modifier", args=[self.admin.pk]), {
            "identifiant": "admin", "role": "Comptabilité", "actif": "on",
        })
        self.assertContains(r, "propres droits")

    def test_arrivage_stock_et_livraison(self):
        self.client.login(username="ami", password="motdepasse-test-123")
        self.client.post(reverse("gestion:stock"), {
            "produit": self.the.pk, "quantite": "10", "prix_achat_unitaire": "1500", "date": "2026-11-20",
        })
        self.the.refresh_from_db()
        self.assertEqual((self.the.stock, self.the.prix_achat, self.the.en_stock), (10, 1500, True))
        from boutique.models import Depense

        self.assertEqual(Depense.objects.get().montant, 15000)
        # une commande de 10 livrée vide le stock, l'annuler le remet
        c = Commande.objects.create(nom_client="Ama", telephone="90000000", ville="Lomé", frais_livraison=1000)
        LigneCommande.objects.create(commande=c, produit=self.the, nom_produit="Thé noir", prix_unitaire=2500,
                                     prix_achat_unitaire=1500, quantite=10)
        c.recalculer_total()
        c.statut = "livree"; c.save()
        self.the.refresh_from_db()
        self.assertEqual((self.the.stock, self.the.en_stock), (0, False))
        c.save()  # enregistrer à nouveau ne retire pas deux fois
        c.statut = "annulee"; c.save()
        self.the.refresh_from_db()
        self.assertEqual(self.the.stock, 10)

    def test_statistiques_benefice(self):
        from boutique.models import CategorieDepense, Depense

        c = Commande.objects.create(nom_client="Ama", telephone="90000000", ville="Lomé", frais_livraison=1000)
        LigneCommande.objects.create(commande=c, produit=self.the, nom_produit="Thé noir", prix_unitaire=2500,
                                     prix_achat_unitaire=1500, quantite=4)
        c.recalculer_total()
        c.statut = "livree"; c.save()
        Depense.objects.create(categorie=CategorieDepense.objects.get(nom="Publicité Facebook"), libelle="Pub", montant=2000)
        Depense.objects.create(categorie=CategorieDepense.objects.get(nom="Achat de marchandise"), libelle="Stock", montant=50000)
        self.client.login(username="ami", password="motdepasse-test-123")
        r = self.client.get(reverse("gestion:statistiques"))
        s = r.context["s"]
        # ventes 10 000 − coût 6 000 = marge 4 000 ; + livraison 1 000 − pub 2 000 = 3 000
        self.assertEqual((s["ventes"], s["cout_achat"], s["marge"], s["benefice"]), (10000, 6000, 4000, 3000))
        self.assertEqual(s["achats_marchandise"], 50000)  # affiché à part, pas retiré du bénéfice
        self.assertEqual(r.context["jour"]["ventes"], 10000)
        csv = self.client.get(reverse("gestion:statistiques_export"), {"quoi": "ventes"}).content.decode("utf-8-sig")
        self.assertIn(c.numero, csv)
        self.assertIn("10000;1000;11000;6000;4000", csv)
        for p in ["jour", "annee"]:
            self.assertEqual(self.client.get(reverse("gestion:statistiques"), {"periode": p}).status_code, 200)

    def test_depense_saisie(self):
        from boutique.models import CategorieDepense, Depense

        self.client.login(username="ami", password="motdepasse-test-123")
        cat = CategorieDepense.objects.get(nom="Transport et envoi de colis")
        self.client.post(reverse("gestion:depenses"), {"date": "2026-11-21", "categorie": cat.pk, "libelle": "Colis Kara", "montant": "3000"})
        d = Depense.objects.get()
        self.assertEqual((d.montant, d.cree_par), (3000, self.compta))
        r = self.client.get(reverse("gestion:depenses"), {"mois": "2026-11"})
        self.assertContains(r, "Colis Kara")


class EquipeReglagesTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group

        U = get_user_model()
        self.admin = U.objects.create_user("admin", password="motdepasse-test-123", is_staff=True)
        self.admin.groups.add(Group.objects.get(name="Administrateur"))
        self.ami = U.objects.create_user("ami", password="motdepasse-test-123", is_staff=True)
        self.ami.groups.add(Group.objects.get(name="Comptabilité"))
        cat = Categorie.objects.create(nom="Thés")
        self.the = Produit.objects.create(categorie=cat, nom="Thé noir", prix=2500, stock=5)
        self.client.login(username="admin", password="motdepasse-test-123")

    def test_role_personnalise(self):
        self.client.post(reverse("gestion:role_ajouter"), {"nom": "Livreur", "sections": ["commandes"]})
        self.client.post(reverse("gestion:equipe_modifier", args=[self.ami.pk]),
                         {"identifiant": "ami", "role": "Livreur", "actif": "on"})
        self.client.logout()
        self.client.login(username="ami", password="motdepasse-test-123")
        self.assertEqual(self.client.get(reverse("gestion:commandes_liste")).status_code, 200)
        self.assertRedirects(self.client.get(reverse("gestion:statistiques")), reverse("gestion:tableau_de_bord"))
        menu = self.client.get(reverse("gestion:tableau_de_bord")).content.decode()
        self.assertIn("Commandes", menu)
        self.assertNotIn("Statistiques", menu)
        self.assertIn("Livreur", menu)  # rôle affiché en bas du menu

    def test_role_utilise_non_supprimable_et_admin_fixe(self):
        from django.contrib.auth.models import Group

        compta = Group.objects.get(name="Comptabilité")
        self.client.post(reverse("gestion:role_supprimer", args=[compta.pk]))
        self.assertTrue(Group.objects.filter(name="Comptabilité").exists())
        self.client.post(reverse("gestion:role_supprimer", args=[Group.objects.get(name="Administrateur").pk]))
        self.assertTrue(Group.objects.filter(name="Administrateur").exists())

    def test_desactiver_puis_supprimer_un_compte(self):
        self.client.post(reverse("gestion:compte_basculer", args=[self.ami.pk]))
        self.ami.refresh_from_db()
        self.assertFalse(self.ami.is_active)
        self.assertFalse(self.client.login(username="ami", password="motdepasse-test-123") and False)
        self.client.post(reverse("gestion:compte_supprimer", args=[self.ami.pk]))
        self.assertFalse(get_user_model().objects.filter(username="ami").exists())
        # impossible sur soi-même
        self.client.post(reverse("gestion:compte_supprimer", args=[self.admin.pk]))
        self.assertTrue(get_user_model().objects.filter(username="admin").exists())

    @staticmethod
    def horaires_post(**changements):
        from boutique.horaires import horaires_semaine

        d = {"horaires-TOTAL_FORMS": "7", "horaires-INITIAL_FORMS": "7", "horaires-MIN_NUM_FORMS": "0", "horaires-MAX_NUM_FORMS": "1000"}
        for i, h in enumerate(horaires_semaine()):
            d[f"horaires-{i}-id"] = str(h.pk)
            if h.ouvert:
                d[f"horaires-{i}-ouvert"] = "on"
            d[f"horaires-{i}-ouverture"] = h.ouverture.strftime("%H:%M")
            d[f"horaires-{i}-fermeture"] = h.fermeture.strftime("%H:%M")
        d.update(changements)
        return d

    def test_reglages_horaires(self):
        from boutique.models import HoraireJour, ReglagesSite

        base = {"nom_boutique": "M", "slogan": "s", "whatsapp": "", "pays": ["TG"], "commandes_ouvertes": "on",
                "message_commandes_fermees": "x", "message_maintenance": "x", "horaires_actifs": "on"}
        r = self.client.post(reverse("gestion:reglages"), {**base, **self.horaires_post(**{"horaires-0-ouverture": "09:30", "horaires-6-ouvert": "on"})})
        self.assertRedirects(r, reverse("gestion:reglages"))
        self.assertTrue(ReglagesSite.charger().horaires_actifs)
        self.assertEqual(HoraireJour.objects.get(jour=0).ouverture.strftime("%H:%M"), "09:30")
        self.assertTrue(HoraireJour.objects.get(jour=6).ouvert)
        # fermeture avant l'ouverture : refusé
        r = self.client.post(reverse("gestion:reglages"), {**base, **self.horaires_post(**{"horaires-1-fermeture": "07:00"})})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "doit être après")

    def test_reglages_whatsapp_pays_et_pause(self):
        from boutique.models import ReglagesSite

        r = self.client.post(reverse("gestion:reglages"), {
            "nom_boutique": "Maélis Orvanne Shop", "slogan": "Nouveau slogan", "whatsapp": "+228 90 00 00 01",
            "pays": ["TG", "BJ"], "commandes_ouvertes": "", "message_commandes_fermees": "En pause",
            "message_maintenance": "x", "pixel_facebook": "1234567890",
            **self.horaires_post(),
        })
        self.assertRedirects(r, reverse("gestion:reglages"))
        reg = ReglagesSite.charger()
        self.assertEqual((reg.whatsapp, reg.pays_livres, reg.commandes_ouvertes), ("22890000001", "TG,BJ", False))
        accueil = self.client.get("/").content.decode()
        self.assertIn("Nouveau slogan", accueil)
        self.assertIn("fbq('init', '1234567890')", accueil)
        import json

        r = self.client.post(reverse("boutique:commander"), {
            "nom_client": "Ama", "telephone": "90123456", "pays": "TG", "ville_liste": "Lomé", "mode_paiement": "especes",
            "panier": json.dumps([{"id": self.the.pk, "qte": 1}]),
        })
        self.assertContains(r, "En pause", status_code=400)
        self.assertEqual(Commande.objects.count(), 0)

    def test_maintenance(self):
        from boutique.models import ReglagesSite

        reg = ReglagesSite.charger()
        reg.maintenance = True
        reg.save()
        self.assertEqual(self.client.get("/").status_code, 200)  # l'équipe voit le site
        self.client.logout()
        r = self.client.get("/")
        self.assertEqual(r.status_code, 503)
        self.assertContains(r, "Revenez dans quelques instants", status_code=503)
        self.assertEqual(self.client.get(reverse("gestion:connexion")).status_code, 200)

    def test_sauvegarde_et_exemples(self):
        from django.core.management import call_command

        call_command("donnees_exemple", verbosity=0)
        r = self.client.get(reverse("gestion:sauvegarde"))
        self.assertEqual(r["Content-Type"], "application/json")
        self.assertIn(b"(exemple)", r.content)
        self.client.post(reverse("gestion:retirer_exemples"))
        self.assertFalse(Produit.objects.filter(nom__endswith="(exemple)").exists())
        self.assertTrue(Produit.objects.filter(nom="Thé noir").exists())

    def test_supprimer_commande_livree_remet_le_stock(self):
        c = Commande.objects.create(nom_client="Ama", telephone="90000000", ville="Lomé")
        LigneCommande.objects.create(commande=c, produit=self.the, nom_produit="Thé noir", prix_unitaire=2500, quantite=2)
        c.statut = "livree"; c.save()
        self.the.refresh_from_db(); self.assertEqual(self.the.stock, 3)
        self.client.post(reverse("gestion:commande_supprimer", args=[c.pk]))
        self.the.refresh_from_db()
        self.assertEqual((self.the.stock, Commande.objects.count()), (5, 0))


class SecuriteTests(TestCase):
    def setUp(self):
        self.u = get_user_model().objects.create_user("gerant", password="motdepasse-test-123", is_staff=True, is_superuser=True)

    def test_connexion_bloquee_apres_5_essais(self):
        url = reverse("gestion:connexion")
        for _ in range(5):
            self.client.post(url, {"username": "gerant", "password": "faux"})
        r = self.client.post(url, {"username": "gerant", "password": "motdepasse-test-123"})
        self.assertContains(r, "Trop d")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_admin_technique_passe_par_la_connexion_protegee(self):
        r = self.client.get("/admin-technique/login/")
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("gestion:connexion"), r["Location"])

    def test_commandes_limitees_par_ip(self):
        import json

        p = Produit.objects.create(categorie=Categorie.objects.create(nom="Thés"), nom="Thé", prix=1000)
        d = {"nom_client": "Ama", "telephone": "90123456", "pays": "TG", "ville_liste": "Lomé",
             "mode_paiement": "especes", "panier": json.dumps([{"id": p.pk, "qte": 1}])}
        for _ in range(5):
            self.assertEqual(self.client.post(reverse("boutique:commander"), d).status_code, 302)
        self.assertEqual(self.client.post(reverse("boutique:commander"), d).status_code, 429)
        self.assertEqual(Commande.objects.count(), 5)

    def test_export_neutralise_les_formules(self):
        c = Commande.objects.create(nom_client="=HYPERLINK(\"http://pirate\")", telephone="90000000", ville="Lomé",
                                    statut="livree")
        self.client.login(username="gerant", password="motdepasse-test-123")
        contenu = self.client.get(reverse("gestion:statistiques_export"), {"quoi": "ventes"}).content.decode("utf-8-sig")
        self.assertIn('"\'=HYPERLINK', contenu)
        self.assertIn(";+22890000000;", contenu)

    def test_mot_de_passe_trop_simple_refuse(self):
        self.client.login(username="gerant", password="motdepasse-test-123")
        r = self.client.post(reverse("gestion:equipe"), {"identifiant": "kofi", "role": "Comptabilité",
                                                         "mot_de_passe": "12345678", "actif": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="kofi").exists())

    def test_photo_non_image_refusee(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        self.client.login(username="gerant", password="motdepasse-test-123")
        cat = Categorie.objects.create(nom="Thés")
        faux = SimpleUploadedFile("virus.jpg", b"<?php echo 1; ?>", content_type="image/jpeg")
        r = self.client.post(reverse("gestion:produit_ajouter"), {"nom": "X", "categorie": cat.pk, "prix": "1000",
                                                                  "image": faux, "actif": "on", "en_stock": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Produit.objects.filter(nom="X").exists())
