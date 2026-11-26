import uuid

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def slug_unique(instance, valeur, champ="slug"):
    """Génère un slug unique à partir d'un texte (ex. « Thé vert jasmin » -> « the-vert-jasmin »)."""
    base = slugify(valeur)[:60] or "element"
    slug = base
    modele = instance.__class__
    i = 2
    while modele.objects.filter(**{champ: slug}).exclude(pk=instance.pk).exists():
        slug = f"{base}-{i}"
        i += 1
    return slug


class Categorie(models.Model):
    nom = models.CharField("nom", max_length=100, unique=True)
    slug = models.SlugField("adresse (slug)", max_length=80, unique=True, blank=True)
    description = models.TextField("description", blank=True)
    ordre = models.PositiveIntegerField(
        "ordre d'affichage", default=0, help_text="Les plus petits numéros s'affichent en premier."
    )
    active = models.BooleanField("visible sur le site", default=True)
    date_creation = models.DateTimeField("créée le", auto_now_add=True)

    class Meta:
        verbose_name = "catégorie"
        verbose_name_plural = "catégories"
        ordering = ["ordre", "nom"]

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slug_unique(self, self.nom)
        super().save(*args, **kwargs)


class Produit(models.Model):
    categorie = models.ForeignKey(
        Categorie,
        verbose_name="catégorie",
        on_delete=models.PROTECT,
        related_name="produits",
    )
    nom = models.CharField("nom", max_length=150)
    slug = models.SlugField("adresse (slug)", max_length=80, unique=True, blank=True)
    description = models.TextField("description", blank=True)
    prix = models.PositiveIntegerField("prix (FCFA)")
    # Visible seulement dans le back-office : sert au calcul du bénéfice
    prix_achat = models.PositiveIntegerField(
        "prix d'achat (FCFA)", null=True, blank=True, help_text="Ce que le produit vous coûte. Jamais affiché aux clients."
    )
    # Quantité disponible. Vide = stock non suivi (l'interrupteur « en stock » se règle alors à la main)
    stock = models.PositiveIntegerField("stock", null=True, blank=True, help_text="Laissez vide pour ne pas suivre les quantités.")
    prix_promo = models.PositiveIntegerField(
        "prix promo (FCFA)",
        null=True,
        blank=True,
        help_text="Laisser vide s'il n'y a pas de promotion. Doit être inférieur au prix normal.",
    )
    image = models.ImageField("photo", upload_to="produits/%Y/%m/", blank=True)
    en_stock = models.BooleanField("en stock", default=True)
    actif = models.BooleanField(
        "visible sur le site", default=True, help_text="Décocher pour cacher le produit sans le supprimer."
    )
    mis_en_avant = models.BooleanField("mis en avant sur l'accueil", default=False)
    date_creation = models.DateTimeField("créé le", auto_now_add=True)
    date_modification = models.DateTimeField("modifié le", auto_now=True)

    class Meta:
        verbose_name = "produit"
        verbose_name_plural = "produits"
        ordering = ["-date_creation"]

    def __str__(self):
        return self.nom

    def clean(self):
        if self.prix_promo is not None and self.prix is not None and self.prix_promo >= self.prix:
            raise ValidationError({"prix_promo": "Le prix promo doit être inférieur au prix normal."})

    def save(self, *args, **kwargs):
        if self.stock is not None:
            self.en_stock = self.stock > 0
        if not self.slug:
            self.slug = slug_unique(self, self.nom)
        super().save(*args, **kwargs)

    @property
    def en_promo(self):
        return self.prix_promo is not None and self.prix_promo < self.prix

    @property
    def prix_actuel(self):
        return self.prix_promo if self.en_promo else self.prix

    @property
    def pourcentage_remise(self):
        if not self.en_promo or not self.prix:
            return 0
        return round((self.prix - self.prix_promo) * 100 / self.prix)


class Commande(models.Model):
    class Statut(models.TextChoices):
        NOUVELLE = "nouvelle", "Nouvelle"
        CONFIRMEE = "confirmee", "Confirmée"
        EN_LIVRAISON = "en_livraison", "En livraison"
        LIVREE = "livree", "Livrée"
        ANNULEE = "annulee", "Annulée"

    class ModePaiement(models.TextChoices):
        ESPECES = "especes", "Espèces à la livraison"
        MOBILE_MONEY = "mobile_money", "Mobile Money à la livraison"

    numero = models.CharField("numéro", max_length=30, unique=True, blank=True)
    # Code secret de la page de confirmation (évite qu'on devine l'adresse d'une autre commande)
    jeton = models.UUIDField("jeton", default=uuid.uuid4, editable=False, unique=True)
    nom_client = models.CharField("nom du client", max_length=120)
    telephone = models.CharField("téléphone", max_length=30)
    # Numéro complet, chiffres seulement avec l'indicatif (ex. 22890123456) : sert pour WhatsApp et les appels
    telephone_international = models.CharField("téléphone international", max_length=20, blank=True)
    pays = models.CharField("pays de livraison", max_length=2, default="TG")
    ville = models.CharField("ville", max_length=80)
    # Facultatif : le client envoie plutôt sa position sur WhatsApp
    lieu_livraison = models.CharField("lieu de livraison (quartier, repère)", max_length=200, blank=True)
    note = models.TextField("note du client", blank=True)
    montant_articles = models.PositiveIntegerField("montant des articles (FCFA)", default=0)
    # Vide = frais d'envoi encore à confirmer (ville hors tarif)
    frais_livraison = models.PositiveIntegerField("frais de livraison (FCFA)", null=True, blank=True)
    total = models.PositiveIntegerField("total (FCFA)", default=0)
    statut = models.CharField("statut", max_length=20, choices=Statut.choices, default=Statut.NOUVELLE)
    # Paiement à la livraison : le client paie au livreur, en espèces ou par Mobile Money
    mode_paiement = models.CharField(
        "mode de paiement", max_length=20, choices=ModePaiement.choices, default=ModePaiement.ESPECES
    )
    paiement_recu = models.BooleanField("paiement reçu", default=False)
    date_paiement = models.DateTimeField("payée le", null=True, blank=True)
    note_interne = models.TextField(
        "note interne", blank=True, help_text="Visible seulement dans le back-office."
    )
    date_creation = models.DateTimeField("passée le", default=timezone.now)
    date_livraison = models.DateTimeField("livrée le", null=True, blank=True)
    # Le stock a-t-il déjà été retiré pour cette commande ? (évite de le retirer deux fois)
    stock_deduit = models.BooleanField(default=False, editable=False)
    date_modification = models.DateTimeField("modifiée le", auto_now=True)

    class Meta:
        verbose_name = "commande"
        verbose_name_plural = "commandes"
        ordering = ["-date_creation"]

    def __str__(self):
        return self.numero or f"Commande {self.pk}"

    def save(self, *args, **kwargs):
        # Date d'encaissement remplie ou effacée automatiquement
        if self.paiement_recu and not self.date_paiement:
            self.date_paiement = timezone.now()
        elif not self.paiement_recu:
            self.date_paiement = None
        if not self.numero:
            with transaction.atomic():
                jour = timezone.localdate(self.date_creation).strftime("%Y%m%d")
                prefixe = f"MO-{jour}-"
                n = Commande.objects.filter(numero__startswith=prefixe).count() + 1
                numero = f"{prefixe}{n:03d}"
                while Commande.objects.filter(numero=numero).exists():
                    n += 1
                    numero = f"{prefixe}{n:03d}"
                self.numero = numero
        if self.statut == self.Statut.LIVREE and not self.date_livraison:
            self.date_livraison = timezone.now()
        elif self.statut != self.Statut.LIVREE:
            self.date_livraison = None
        super().save(*args, **kwargs)
        if self.pk and not kwargs.get("update_fields"):
            self.synchroniser_stock()

    def synchroniser_stock(self):
        """Retire le stock quand la commande passe « livrée », le remet si elle ne l'est plus."""
        livree = self.statut == self.Statut.LIVREE
        if livree == self.stock_deduit:
            return
        with transaction.atomic():
            for ligne in self.lignes.select_related("produit"):
                p = ligne.produit
                if p is None or p.stock is None:
                    continue
                p.stock = max(0, p.stock - ligne.quantite) if livree else p.stock + ligne.quantite
                p.save(update_fields=["stock", "en_stock", "date_modification"])
            self.stock_deduit = livree
            Commande.objects.filter(pk=self.pk).update(stock_deduit=livree)

    def recalculer_total(self):
        self.montant_articles = sum(ligne.sous_total for ligne in self.lignes.all())
        self.total = self.montant_articles + (self.frais_livraison or 0)
        self.save(update_fields=["montant_articles", "total", "date_modification"])

    @property
    def livraison_a_confirmer(self):
        return self.frais_livraison is None

    @property
    def a_encaisser(self):
        return not self.paiement_recu and self.statut != self.Statut.ANNULEE

    @property
    def nombre_articles(self):
        return sum(ligne.quantite for ligne in self.lignes.all())

    @property
    def telephone_whatsapp(self):
        """Numéro au format wa.me : chiffres seulement, avec l'indicatif du pays."""
        if self.telephone_international:
            return self.telephone_international
        from .pays import normaliser_telephone

        try:
            return normaliser_telephone(self.telephone, self.pays)[0]
        except (ValueError, KeyError):
            return "".join(c for c in self.telephone if c.isdigit())

    @property
    def telephone_affiche(self):
        """Numéro lisible avec l'indicatif : +229 01 51 13 25 51."""
        if self.telephone.strip().startswith("+"):
            return self.telephone
        return f"+{self.telephone_whatsapp}"

    @property
    def nom_pays(self):
        from .pays import nom_pays

        return nom_pays(self.pays)

    @property
    def drapeau(self):
        from .pays import PAYS

        return PAYS.get(self.pays, {}).get("drapeau", "")

    def get_absolute_url(self):
        return reverse("gestion:commande_detail", args=[self.pk])


class LigneCommande(models.Model):
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name="lignes")
    produit = models.ForeignKey(
        Produit, on_delete=models.SET_NULL, null=True, blank=True, related_name="lignes_commande"
    )
    # Copie du nom et du prix au moment de la commande (si le produit change ou est supprimé plus tard)
    nom_produit = models.CharField("produit", max_length=150)
    prix_unitaire = models.PositiveIntegerField("prix unitaire (FCFA)")
    # Copie du prix d'achat au moment de la commande (pour calculer le bénéfice plus tard)
    prix_achat_unitaire = models.PositiveIntegerField("prix d'achat unitaire", null=True, blank=True)
    quantite = models.PositiveIntegerField("quantité", default=1)

    class Meta:
        verbose_name = "ligne de commande"
        verbose_name_plural = "lignes de commande"

    def __str__(self):
        return f"{self.nom_produit} × {self.quantite}"

    @property
    def sous_total(self):
        return self.prix_unitaire * self.quantite


def normaliser_ville(texte):
    """« Lomé », « LOME », « lome  » → « lome » : pour comparer les villes tapées par les clients."""
    import unicodedata

    texte = unicodedata.normalize("NFKD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    return " ".join(texte.lower().replace("-", " ").split())


class TarifLivraison(models.Model):
    """Frais de livraison facturés au client, par ville. Une ligne sans ville = tarif des autres villes du pays."""

    pays = models.CharField("pays", max_length=2, default="TG")
    ville = models.CharField(
        "ville", max_length=80, blank=True, help_text="Laissez vide pour le tarif de toutes les autres villes du pays."
    )
    ville_normalisee = models.CharField(max_length=80, editable=False, default="")
    frais = models.PositiveIntegerField(
        "frais (FCFA)", null=True, blank=True, help_text="Laissez vide si le prix est à confirmer au cas par cas."
    )

    class Meta:
        verbose_name = "tarif de livraison"
        verbose_name_plural = "tarifs de livraison"
        ordering = ["pays", "-ville_normalisee"]
        constraints = [models.UniqueConstraint(fields=["pays", "ville_normalisee"], name="tarif_unique_par_ville")]

    def __str__(self):
        return f"{self.ville or 'Autres villes'} ({self.pays})"

    def save(self, *args, **kwargs):
        self.ville = self.ville.strip()
        self.ville_normalisee = normaliser_ville(self.ville)
        super().save(*args, **kwargs)

    @classmethod
    def frais_pour(cls, pays, ville):
        """Frais pour cette ville ; à défaut, tarif « autres villes » du pays ; à défaut, None (à confirmer)."""
        tarifs = {t.ville_normalisee: t.frais for t in cls.objects.filter(pays=pays)}
        cle = normaliser_ville(ville)
        if cle in tarifs:
            return tarifs[cle]
        return tarifs.get("")


class CategorieDepense(models.Model):
    nom = models.CharField("nom", max_length=80, unique=True)
    ordre = models.PositiveIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "catégorie de dépense"
        verbose_name_plural = "catégories de dépenses"
        ordering = ["ordre", "nom"]

    def __str__(self):
        return self.nom


CATEGORIE_MARCHANDISE = "Achat de marchandise"


class Depense(models.Model):
    date = models.DateField("date", default=timezone.localdate)
    categorie = models.ForeignKey(CategorieDepense, on_delete=models.PROTECT, related_name="depenses", verbose_name="catégorie")
    libelle = models.CharField("libellé", max_length=160)
    montant = models.PositiveIntegerField("montant (FCFA)")
    note = models.CharField("note", max_length=255, blank=True)
    cree_par = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "dépense"
        verbose_name_plural = "dépenses"
        ordering = ["-date", "-pk"]

    def __str__(self):
        return f"{self.libelle} ({self.montant} FCFA)"


class Arrivage(models.Model):
    """Entrée de marchandise : augmente le stock, met à jour le prix d'achat et crée la dépense correspondante."""

    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name="arrivages")
    quantite = models.PositiveIntegerField("quantité")
    prix_achat_unitaire = models.PositiveIntegerField("prix d'achat unitaire (FCFA)")
    date = models.DateField("date", default=timezone.localdate)
    fournisseur = models.CharField("fournisseur", max_length=120, blank=True)
    note = models.CharField("note", max_length=255, blank=True)
    depense = models.OneToOneField(Depense, null=True, blank=True, on_delete=models.SET_NULL, related_name="arrivage")
    cree_par = models.ForeignKey("auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        verbose_name = "arrivage"
        verbose_name_plural = "arrivages"
        ordering = ["-date", "-pk"]

    @property
    def montant(self):
        return self.quantite * self.prix_achat_unitaire

    def enregistrer(self):
        with transaction.atomic():
            categorie, _ = CategorieDepense.objects.get_or_create(nom=CATEGORIE_MARCHANDISE)
            self.depense = Depense.objects.create(
                date=self.date, categorie=categorie, montant=self.montant, cree_par=self.cree_par,
                libelle=f"Arrivage : {self.produit.nom} × {self.quantite}", note=self.fournisseur,
            )
            self.save()
            p = self.produit
            p.stock = (p.stock or 0) + self.quantite
            p.prix_achat = self.prix_achat_unitaire
            p.save()

    def annuler(self):
        """Supprime l'arrivage : retire la quantité du stock et la dépense liée."""
        with transaction.atomic():
            p = self.produit
            if p.stock is not None:
                p.stock = max(0, p.stock - self.quantite)
                p.save()
            if self.depense:
                self.depense.delete()
            self.delete()


class ReglagesSite(models.Model):
    """Réglages du site modifiables depuis le back-office (une seule ligne).
    Un champ vide reprend la valeur du fichier .env (BOUTIQUE_WHATSAPP, BOUTIQUE_PAYS)."""

    nom_boutique = models.CharField("nom de la boutique", max_length=80, default="Maélis Orvanne Shop")
    slogan = models.CharField("phrase d'accroche", max_length=120, default="L'élégance à portée de clic")
    whatsapp = models.CharField(
        "numéro WhatsApp de la boutique", max_length=20, blank=True,
        help_text="Format international, sans + ni espaces : 22890123456.",
    )
    pays_livres = models.CharField("pays livrés", max_length=40, blank=True)
    lien_facebook = models.URLField("page Facebook", blank=True)
    lien_instagram = models.URLField("compte Instagram", blank=True)
    lien_tiktok = models.URLField("compte TikTok", blank=True)
    pixel_facebook = models.CharField(
        "identifiant du Pixel Facebook", max_length=30, blank=True,
        help_text="Pour mesurer les commandes venues de vos publicités. Laissez vide pour désactiver.",
    )
    commandes_ouvertes = models.BooleanField("commandes ouvertes", default=True)
    message_commandes_fermees = models.CharField(
        "message quand les commandes sont en pause", max_length=200,
        default="Les commandes sont en pause pour quelques jours. Revenez bientôt !",
    )
    horaires_actifs = models.BooleanField("appliquer les horaires d'ouverture", default=False)
    commandes_hors_horaires = models.BooleanField(
        "accepter les commandes quand la boutique est fermée", default=False,
        help_text="Si coché, le client voit que la boutique est fermée mais peut quand même commander.",
    )
    maintenance = models.BooleanField("site en maintenance", default=False)
    message_maintenance = models.CharField(
        "message de maintenance", max_length=200, default="Le site est en cours d'amélioration. Revenez dans quelques instants.",
    )
    fin_maintenance = models.DateTimeField(
        "fin de la maintenance", null=True, blank=True,
        help_text="Affichée aux visiteurs. À cette heure-là, le site se rouvre tout seul. Laissez vide si vous ne savez pas.",
    )
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "réglages du site"
        verbose_name_plural = "réglages du site"

    def __str__(self):
        return "Réglages du site"

    @classmethod
    def charger(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        self.whatsapp = "".join(c for c in self.whatsapp if c.isdigit())
        self.pixel_facebook = "".join(c for c in self.pixel_facebook if c.isdigit())
        super().save(*args, **kwargs)

    def maintenance_active(self, maintenant=None):
        """Vrai si le site est en maintenance. Une fois l'heure de fin passée, la maintenance s'arrête d'elle-même."""
        from django.utils import timezone

        if not self.maintenance:
            return False
        if self.fin_maintenance and (maintenant or timezone.now()) >= self.fin_maintenance:
            ReglagesSite.objects.filter(pk=self.pk).update(maintenance=False, fin_maintenance=None)
            self.maintenance, self.fin_maintenance = False, None
            return False
        return True

    def fin_maintenance_texte(self, maintenant=None):
        """« aujourd'hui à 14h », « demain à 9h30 », « samedi 28 novembre à 10h »."""
        from django.utils import timezone

        if not self.fin_maintenance:
            return ""
        fin = timezone.localtime(self.fin_maintenance)
        jour = timezone.localtime(maintenant or timezone.now()).date()
        h = heure_fr(fin.time())
        ecart = (fin.date() - jour).days
        if ecart <= 0:
            return f"aujourd'hui à {h}"
        if ecart == 1:
            return f"demain à {h}"
        jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
                "septembre", "octobre", "novembre", "décembre"]
        return f"{jours[fin.weekday()]} {fin.day} {mois[fin.month - 1]} à {h}"

    @property
    def whatsapp_effectif(self):
        from django.conf import settings

        return self.whatsapp or "".join(c for c in (settings.BOUTIQUE_WHATSAPP or "") if c.isdigit())

    @property
    def pays_effectifs(self):
        from django.conf import settings

        codes = [c for c in self.pays_livres.split(",") if c] or list(getattr(settings, "BOUTIQUE_PAYS", ["TG"]))
        return [c.strip().upper() for c in codes]


class HoraireJour(models.Model):
    """Horaires d'ouverture de la boutique, un par jour de la semaine (0 = lundi)."""

    JOURS = [(0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"), (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche")]

    jour = models.PositiveSmallIntegerField("jour", choices=JOURS, unique=True)
    ouvert = models.BooleanField("ouvert", default=True)
    ouverture = models.TimeField("ouverture", default="08:00")
    fermeture = models.TimeField("fermeture", default="19:00")

    class Meta:
        verbose_name = "horaire d'ouverture"
        verbose_name_plural = "horaires d'ouverture"
        ordering = ["jour"]

    def __str__(self):
        return f"{self.get_jour_display()} : {self.plage}"

    @property
    def plage(self):
        if not self.ouvert:
            return "Fermé"
        return f"{heure_fr(self.ouverture)} – {heure_fr(self.fermeture)}"


def heure_fr(t):
    """08:00 -> 8h, 18:30 -> 18h30"""
    return f"{t.hour}h{t.minute:02d}" if t.minute else f"{t.hour}h"
