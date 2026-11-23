import json

from django.test import override_settings

from config.tests_base import TestCase
from django.urls import reverse

from .models import Categorie, Commande, LigneCommande, Produit, TarifLivraison
from .pays import normaliser_telephone


class SitePublicTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cat = Categorie.objects.create(nom="Thés")
        cls.cachee = Categorie.objects.create(nom="Cachée", active=False)
        cls.the = Produit.objects.create(categorie=cls.cat, nom="Thé vert", prix=3000)
        cls.promo = Produit.objects.create(categorie=cls.cat, nom="Oolong", prix=4500, prix_promo=3900, mis_en_avant=True)
        cls.epuise = Produit.objects.create(categorie=cls.cat, nom="Pu-erh", prix=5000, en_stock=False)
        cls.inactif = Produit.objects.create(categorie=cls.cat, nom="Brouillon", prix=1000, actif=False)
        cls.hors_cat = Produit.objects.create(categorie=cls.cachee, nom="Secret", prix=1000)

    def donnees(self, panier, **extra):
        d = {
            "nom_client": "Ama Kossi", "telephone": "90 12 34 56", "ville_liste": "Lomé", "mode_paiement": "especes", "note": "",
            "panier": json.dumps(panier), "site_web": "", "pays": "TG",
        }
        d.update(extra)
        return d

    # ---- Pages
    def test_pages_publiques(self):
        for url in [reverse("boutique:accueil"), reverse("boutique:catalogue"),
                    reverse("boutique:categorie", args=[self.cat.slug]),
                    reverse("boutique:produit", args=[self.the.slug]), reverse("boutique:panier")]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_produits_caches_invisibles(self):
        r = self.client.get(reverse("boutique:catalogue"))
        self.assertContains(r, "Thé vert")
        self.assertNotContains(r, "Brouillon")
        self.assertNotContains(r, "Secret")
        self.assertEqual(self.client.get(reverse("boutique:produit", args=[self.inactif.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse("boutique:categorie", args=[self.cachee.slug])).status_code, 404)

    def test_recherche_et_tri(self):
        r = self.client.get(reverse("boutique:catalogue"), {"q": "oolong"})
        self.assertContains(r, "Oolong")
        self.assertNotContains(r, "Thé vert")
        r = self.client.get(reverse("boutique:catalogue"), {"tri": "prix_croissant"})
        noms = [p.nom for p in r.context["produits"]]
        self.assertEqual(noms, ["Thé vert", "Oolong", "Pu-erh"])  # en stock d'abord, puis prix

    # ---- API
    def test_api_produits(self):
        ids = f"{self.the.pk},{self.promo.pk},{self.inactif.pk},abc"
        data = self.client.get(reverse("boutique:api_produits"), {"ids": ids}).json()
        par_id = {p["id"]: p for p in data["produits"]}
        self.assertEqual(set(par_id), {self.the.pk, self.promo.pk})
        self.assertEqual(par_id[self.promo.pk]["prix_actuel"], 3900)
        self.assertTrue(par_id[self.promo.pk]["en_promo"])

    # ---- Commande
    def test_commande_prix_de_la_base(self):
        r = self.client.post(reverse("boutique:commander"), self.donnees([{"id": self.the.pk, "qte": 2}, {"id": self.promo.pk, "qte": 1, "prix": 1}]))
        commande = Commande.objects.get()
        self.assertRedirects(r, reverse("boutique:merci", args=[commande.jeton]))
        self.assertEqual(commande.total, 2 * 3000 + 3900 + 1000)  # + livraison Lomé
        self.assertEqual(commande.lignes.count(), 2)
        self.assertEqual(commande.statut, Commande.Statut.NOUVELLE)

    def test_articles_indisponibles_retires(self):
        self.client.post(reverse("boutique:commander"), self.donnees([{"id": self.the.pk, "qte": 1}, {"id": self.epuise.pk, "qte": 1}, {"id": self.inactif.pk, "qte": 3}]))
        commande = Commande.objects.get()
        self.assertEqual(list(commande.lignes.values_list("nom_produit", flat=True)), ["Thé vert"])
        self.assertEqual(commande.total, 3000 + 1000)

    def test_panier_vide_ou_illisible(self):
        for panier in ["[]", "pas du json"]:
            r = self.client.post(reverse("boutique:commander"), dict(self.donnees([]), panier=panier))
            self.assertEqual(r.status_code, 400)
        r = self.client.post(reverse("boutique:commander"), self.donnees([{"id": self.epuise.pk, "qte": 1}]))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Commande.objects.count(), 0)

    def test_quantite_plafonnee(self):
        self.client.post(reverse("boutique:commander"), self.donnees([{"id": self.the.pk, "qte": 5000}]))
        self.assertEqual(Commande.objects.get().lignes.get().quantite, 99)

    def test_telephone_invalide(self):
        r = self.client.post(reverse("boutique:commander"), self.donnees([{"id": self.the.pk, "qte": 1}], telephone="123"))
        self.assertEqual(r.status_code, 400)
        self.assertContains(r, "ne correspond pas au Togo", status_code=400)

    def test_champ_piege(self):
        r = self.client.post(reverse("boutique:commander"), self.donnees([{"id": self.the.pk, "qte": 1}], site_web="http://spam"))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Commande.objects.count(), 0)

    # ---- Confirmation et WhatsApp
    @override_settings(BOUTIQUE_WHATSAPP="22890000000")
    def test_merci_avec_whatsapp(self):
        self.client.post(reverse("boutique:commander"), self.donnees([{"id": self.promo.pk, "qte": 2}]))
        commande = Commande.objects.get()
        r = self.client.get(reverse("boutique:merci", args=[commande.jeton]))
        self.assertContains(r, commande.numero)
        self.assertContains(r, "https://wa.me/22890000000?text=")
        self.assertContains(r, "7\u202f800 FCFA")

    @override_settings(BOUTIQUE_WHATSAPP="")
    def test_merci_sans_whatsapp(self):
        self.client.post(reverse("boutique:commander"), self.donnees([{"id": self.the.pk, "qte": 1}]))
        r = self.client.get(reverse("boutique:merci", args=[Commande.objects.get().jeton]))
        self.assertContains(r, "bien enregistrée")
        self.assertNotContains(r, "wa.me")

    def test_jeton_inconnu(self):
        r = self.client.get("/commande/00000000-0000-0000-0000-000000000000/merci/")
        self.assertEqual(r.status_code, 404)


class NumerosTests(TestCase):
    def test_togo(self):
        self.assertEqual(normaliser_telephone("90 12 34 56", "TG"), ("22890123456", "+228 90 12 34 56"))
        self.assertEqual(normaliser_telephone("22890123456", "TG")[0], "22890123456")
        self.assertEqual(normaliser_telephone("00228 90123456", "TG")[0], "22890123456")
        with self.assertRaises(ValueError):
            normaliser_telephone("9012345", "TG")

    def test_benin_nouveau_et_ancien_format(self):
        self.assertEqual(normaliser_telephone("01 51 13 25 51", "BJ"), ("2290151132551", "+229 01 51 13 25 51"))
        self.assertEqual(normaliser_telephone("51 13 25 51", "BJ")[0], "2290151132551")  # 01 ajouté
        self.assertEqual(normaliser_telephone("+229 0151132551", "TG")[0], "2290151132551")  # pays reconnu par +229

    def test_ghana(self):
        self.assertEqual(normaliser_telephone("024 123 4567", "GH"), ("233241234567", "+233 24 123 4567"))
        self.assertEqual(normaliser_telephone("+233 24 123 4567", "TG")[0], "233241234567")

    def test_numero_etranger(self):
        self.assertEqual(normaliser_telephone("+33 6 12 34 56 78", "TG")[0], "33612345678")


@override_settings(BOUTIQUE_PAYS=["TG", "BJ"], BOUTIQUE_WHATSAPP="22890000000")
class CommandeMultiPaysTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Categorie.objects.create(nom="Thés")
        cls.the = Produit.objects.create(categorie=cat, nom="Thé noir", prix=2500)

    def commander(self, **extra):
        d = {
            "nom_client": "Veedah", "telephone": "0151132551", "ville_liste": "Cotonou",
            "mode_paiement": "especes", "note": "", "pays": "BJ", "site_web": "",
            "panier": json.dumps([{"id": self.the.pk, "qte": 2}]),
        }
        d.update(extra)
        return self.client.post(reverse("boutique:commander"), d)

    def test_commande_benin(self):
        self.commander()
        c = Commande.objects.get()
        self.assertEqual((c.pays, c.telephone_international, c.telephone), ("BJ", "2290151132551", "+229 01 51 13 25 51"))
        r = self.client.get(reverse("boutique:merci", args=[c.jeton]))
        self.assertContains(r, "Cotonou (Bénin)")
        self.assertContains(r, "%2B229%2001%2051%2013%2025%2051")  # numéro complet dans le message WhatsApp

    def test_numero_ghaneen_livre_au_benin(self):
        self.commander(telephone="+233 24 123 4567")
        c = Commande.objects.get()
        self.assertEqual((c.pays, c.telephone_international), ("BJ", "233241234567"))

    def test_pays_non_livre_refuse(self):
        r = self.commander(pays="GH")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Commande.objects.count(), 0)

    def test_panier_affiche_choix_pays(self):
        r = self.client.get(reverse("boutique:panier"))
        self.assertContains(r, "<option value=\"BJ\">Bénin</option>", html=False)
        self.assertContains(r, "Bénin")


class LivraisonTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Categorie.objects.create(nom="Thés")
        cls.the = Produit.objects.create(categorie=cat, nom="Thé noir", prix=2500, prix_achat=1400)

    def commander(self, ville):
        d = {
            "nom_client": "Ama", "telephone": "90123456", "ville_liste": "__autre__", "ville": ville,
            "mode_paiement": "especes", "note": "", "pays": "TG", "site_web": "",
            "panier": json.dumps([{"id": self.the.pk, "qte": 2}]),
        }
        self.client.post(reverse("boutique:commander"), d)
        return Commande.objects.latest("pk")

    def test_tarif_lome_quelle_que_soit_l_ecriture(self):
        for ville in ["Lomé", "LOME", " lome "]:
            c = self.commander(ville)
            self.assertEqual((c.montant_articles, c.frais_livraison, c.total), (5000, 1000, 6000))

    def test_autre_ville_a_confirmer(self):
        c = self.commander("Kara")
        self.assertIsNone(c.frais_livraison)
        self.assertEqual(c.total, 5000)
        r = self.client.get(reverse("boutique:merci", args=[c.jeton]))
        self.assertContains(r, "à confirmer")

    def test_tarif_ajoute_pour_une_ville(self):
        TarifLivraison.objects.create(pays="TG", ville="Kara", frais=2500)
        self.assertEqual(self.commander("kara").total, 7500)

    def test_prix_achat_copie_sur_la_ligne(self):
        c = self.commander("Lomé")
        self.assertEqual(c.lignes.get().prix_achat_unitaire, 1400)

    def test_prix_achat_jamais_public(self):
        r = self.client.get(reverse("boutique:produit", args=[self.the.slug]))
        self.assertNotContains(r, "1 400")
        self.assertNotContains(r, "1400")
        data = self.client.get(reverse("boutique:api_produits"), {"ids": self.the.pk}).json()
        self.assertNotIn("prix_achat", data["produits"][0])


class FormulaireVilleTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Categorie.objects.create(nom="Thés")
        cls.the = Produit.objects.create(categorie=cat, nom="Thé noir", prix=2500)

    def donnees(self, **extra):
        d = {"nom_client": "Ama", "telephone": "90123456", "pays": "TG", "mode_paiement": "especes",
             "note": "", "site_web": "", "panier": json.dumps([{"id": self.the.pk, "qte": 1}])}
        d.update(extra)
        return d

    def test_ville_choisie_dans_la_liste(self):
        self.client.post(reverse("boutique:commander"), self.donnees(ville_liste="Sokodé"))
        c = Commande.objects.get()
        self.assertEqual((c.ville, c.lieu_livraison), ("Sokodé", ""))

    def test_autre_ville_ecrite(self):
        self.client.post(reverse("boutique:commander"), self.donnees(ville_liste="__autre__", ville="Badou"))
        self.assertEqual(Commande.objects.get().ville, "Badou")

    def test_ville_obligatoire(self):
        r = self.client.post(reverse("boutique:commander"), self.donnees())
        self.assertEqual(r.status_code, 400)
        r = self.client.post(reverse("boutique:commander"), self.donnees(ville_liste="__autre__", ville=" "))
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Commande.objects.count(), 0)

    @override_settings(BOUTIQUE_WHATSAPP="22890000000")
    def test_message_demande_la_position(self):
        self.client.post(reverse("boutique:commander"), self.donnees(ville_liste="Kara"))
        r = self.client.get(reverse("boutique:merci", args=[Commande.objects.get().jeton]))
        self.assertContains(r, "ma%20position")
