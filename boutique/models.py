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
    nom_client = models.CharField("nom du client", max_length=120)
    telephone = models.CharField("téléphone", max_length=30)
    ville = models.CharField("ville", max_length=80)
    lieu_livraison = models.CharField("lieu de livraison (quartier, repère)", max_length=200)
    note = models.TextField("note du client", blank=True)
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
        super().save(*args, **kwargs)

    def recalculer_total(self):
        self.total = sum(ligne.sous_total for ligne in self.lignes.all())
        self.save(update_fields=["total", "date_modification"])

    @property
    def a_encaisser(self):
        return not self.paiement_recu and self.statut != self.Statut.ANNULEE

    @property
    def nombre_articles(self):
        return sum(ligne.quantite for ligne in self.lignes.all())

    @property
    def telephone_whatsapp(self):
        """Numéro au format wa.me (chiffres seulement, indicatif 228 ajouté si absent)."""
        chiffres = "".join(c for c in self.telephone if c.isdigit())
        if chiffres.startswith("00"):
            chiffres = chiffres[2:]
        if len(chiffres) == 8:  # numéro togolais sans indicatif
            chiffres = "228" + chiffres
        return chiffres

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
    quantite = models.PositiveIntegerField("quantité", default=1)

    class Meta:
        verbose_name = "ligne de commande"
        verbose_name_plural = "lignes de commande"

    def __str__(self):
        return f"{self.nom_produit} × {self.quantite}"

    @property
    def sous_total(self):
        return self.prix_unitaire * self.quantite
