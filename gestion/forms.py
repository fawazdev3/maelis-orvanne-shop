from django import forms
from django.contrib.auth.forms import AuthenticationForm

from boutique.models import TarifLivraison, normaliser_ville
from boutique.pays import PAYS
from boutique.models import Categorie, Commande, Produit


class ConnexionForm(AuthenticationForm):
    username = forms.CharField(
        label="Nom d'utilisateur",
        widget=forms.TextInput(attrs={"class": "form-control", "autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )

    def clean(self):
        """Bloque 15 minutes après 5 essais ratés (par adresse IP et par identifiant)."""
        from django.conf import settings

        from config.limites import adresse_ip, ajouter, compte, effacer

        maximum, duree = settings.LIMITE_CONNEXION
        nom = (self.data.get("username") or "").lower()[:150]
        cles = [f"connexion-ip:{adresse_ip(self.request)}", f"connexion-nom:{nom}"] if self.request else []
        if any(compte(c) >= maximum for c in cles):
            raise forms.ValidationError(
                "Trop d'essais ratés. Par sécurité, réessayez dans 15 minutes.", code="bloque"
            )
        try:
            donnees = super().clean()
        except forms.ValidationError:
            for c in cles:
                ajouter(c, duree)
            raise
        for c in cles:
            effacer(c)
        return donnees


FORMATS_PHOTO = {"jpeg", "png", "webp"}
TAILLE_MAX_PHOTO = 5 * 1024 * 1024


class ProduitForm(forms.ModelForm):
    supprimer_image = forms.BooleanField(
        label="Retirer la photo actuelle",
        required=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Produit
        fields = [
            "nom",
            "categorie",
            "description",
            "prix",
            "prix_promo",
            "prix_achat",
            "stock",
            "image",
            "en_stock",
            "actif",
            "mis_en_avant",
        ]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. Thé vert au jasmin"}),
            "categorie": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(
                attrs={"class": "form-control", "rows": 5, "placeholder": "Origine, goût, conseils de préparation…"}
            ),
            "prix": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 50}),
            "prix_promo": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 50}),
            "prix_achat": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 50}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": 0, "placeholder": "Non suivi"}),
            "image": forms.ClearableFileInput(
                attrs={"class": "form-control", "accept": "image/*", "data-apercu": "apercu-image"}
            ),
            "en_stock": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "actif": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "mis_en_avant": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categorie"].queryset = Categorie.objects.all()
        self.fields["categorie"].empty_label = "Choisir une catégorie"
        # Le champ d'image Django affiche déjà sa propre case « effacer » : on utilise la nôtre à la place.
        self.fields["image"].widget = forms.FileInput(
            attrs={"class": "form-control", "accept": "image/*", "data-apercu": "apercu-image"}
        )

    def clean_image(self):
        """Photo : JPG, PNG ou WebP, 5 Mo maximum (le contenu est vérifié, pas seulement le nom)."""
        from django.core.files.uploadedfile import UploadedFile

        image = self.cleaned_data.get("image")
        if isinstance(image, UploadedFile):  # seulement pour une nouvelle photo envoyée
            if image.size > TAILLE_MAX_PHOTO:
                raise forms.ValidationError("Photo trop lourde : 5 Mo maximum.")
            format_reel = (getattr(getattr(image, "image", None), "format", "") or "").lower()
            if format_reel and format_reel not in FORMATS_PHOTO:
                raise forms.ValidationError("Format non accepté : utilisez une photo JPG, PNG ou WebP.")
        return image

    def clean(self):
        donnees = super().clean()
        prix, promo = donnees.get("prix"), donnees.get("prix_promo")
        if prix is not None and promo is not None and promo >= prix:
            self.add_error("prix_promo", "Le prix promo doit être inférieur au prix normal.")
        return donnees

    def save(self, commit=True):
        produit = super().save(commit=False)
        if self.cleaned_data.get("supprimer_image") and not self.files.get("image"):
            if produit.image:
                produit.image.delete(save=False)
            produit.image = ""
        if commit:
            produit.save()
        return produit


class CategorieForm(forms.ModelForm):
    class Meta:
        model = Categorie
        fields = ["nom", "description", "ordre", "active"]
        widgets = {
            "nom": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. Thés"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "ordre": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "active": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
        }


class CommandeStatutForm(forms.ModelForm):
    class Meta:
        model = Commande
        fields = ["statut", "mode_paiement", "frais_livraison", "paiement_recu", "note_interne"]
        widgets = {
            "statut": forms.Select(attrs={"class": "form-select"}),
            "mode_paiement": forms.Select(attrs={"class": "form-select"}),
            "frais_livraison": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 100, "placeholder": "À confirmer"}),
            "paiement_recu": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "note_interne": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Ex. livreur prévu demain à 10 h"}
            ),
        }


class TarifLivraisonForm(forms.ModelForm):
    pays = forms.ChoiceField(label="Pays", widget=forms.Select(attrs={"class": "form-select"}))

    class Meta:
        model = TarifLivraison
        fields = ["pays", "ville", "frais"]
        widgets = {
            "ville": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. Lomé — vide pour « autres villes »"}),
            "frais": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 100, "placeholder": "À confirmer"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pays"].choices = [(c, p["nom"]) for c, p in PAYS.items()]

    def clean(self):
        donnees = super().clean()
        cle = normaliser_ville(donnees.get("ville", ""))
        doublon = TarifLivraison.objects.filter(pays=donnees.get("pays"), ville_normalisee=cle).exclude(pk=self.instance.pk)
        if doublon.exists():
            self.add_error("ville", "Un tarif existe déjà pour cette ville." if cle else "Le tarif « autres villes » existe déjà pour ce pays.")
        return donnees


class CompteForm(forms.Form):
    """Création ou modification d'un compte de l'équipe."""

    identifiant = forms.CharField(label="Identifiant de connexion", max_length=150,
                                  widget=forms.TextInput(attrs={"class": "form-control", "autocomplete": "off"}))
    prenom = forms.CharField(label="Prénom", max_length=150, required=False,
                             widget=forms.TextInput(attrs={"class": "form-control"}))
    role = forms.ChoiceField(label="Rôle", widget=forms.Select(attrs={"class": "form-select"}))
    mot_de_passe = forms.CharField(
        label="Mot de passe", required=False, min_length=8,
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "new-password"}),
    )
    actif = forms.BooleanField(label="Compte actif", required=False, initial=True,
                               widget=forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}))

    def __init__(self, *args, compte=None, moi=None, **kwargs):
        from django.contrib.auth.models import Group

        from .roles import ADMINISTRATEUR, nom_role

        super().__init__(*args, **kwargs)
        self.compte, self.moi = compte, moi
        autres = Group.objects.exclude(name=ADMINISTRATEUR).order_by("name").values_list("name", flat=True)
        self.fields["role"].choices = [(ADMINISTRATEUR, "Administrateur — accès à tout")] + [(n, n) for n in autres]
        if compte:
            self.fields["identifiant"].initial = compte.username
            self.fields["prenom"].initial = compte.first_name
            self.fields["role"].initial = nom_role(compte)
            self.fields["actif"].initial = compte.is_active
            self.fields["mot_de_passe"].label = "Nouveau mot de passe"
            self.fields["mot_de_passe"].help_text = "Laissez vide pour garder le mot de passe actuel."
        else:
            self.fields["mot_de_passe"].required = True
            self.fields["role"].initial = "Comptabilité"
        self.fields["mot_de_passe"].error_messages["min_length"] = "Au moins 8 caractères."

    def clean_identifiant(self):
        from django.contrib.auth import get_user_model

        nom = self.cleaned_data["identifiant"].strip()
        autres = get_user_model().objects.filter(username__iexact=nom)
        if self.compte:
            autres = autres.exclude(pk=self.compte.pk)
        if autres.exists():
            raise forms.ValidationError("Cet identifiant est déjà utilisé.")
        return nom

    def clean_mot_de_passe(self):
        from django.contrib.auth.password_validation import validate_password

        mdp = self.cleaned_data.get("mot_de_passe")
        if mdp:
            validate_password(mdp, self.compte)
        return mdp

    def clean(self):
        donnees = super().clean()
        if self.compte and self.compte == self.moi:
            if donnees.get("role") != "Administrateur" or not donnees.get("actif"):
                raise forms.ValidationError("Vous ne pouvez pas retirer vos propres droits d'administrateur ni désactiver votre compte.")
        return donnees

    def enregistrer(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Group

        d = self.cleaned_data
        compte = self.compte or get_user_model()(is_staff=True)
        compte.username, compte.first_name, compte.is_active = d["identifiant"], d["prenom"], d["actif"]
        compte.is_staff = True
        if d.get("mot_de_passe"):
            compte.set_password(d["mot_de_passe"])
        compte.save()
        compte.groups.clear()  # un seul rôle par compte
        compte.groups.add(Group.objects.get_or_create(name=d["role"])[0])
        return compte


class ArrivageForm(forms.ModelForm):
    class Meta:
        from boutique.models import Arrivage

        model = Arrivage
        fields = ["produit", "quantite", "prix_achat_unitaire", "date", "fournisseur", "note"]
        widgets = {
            "produit": forms.Select(attrs={"class": "form-select"}),
            "quantite": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "prix_achat_unitaire": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 50}),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "fournisseur": forms.TextInput(attrs={"class": "form-control", "placeholder": "Facultatif"}),
            "note": forms.TextInput(attrs={"class": "form-control", "placeholder": "Facultatif"}),
        }
        labels = {"prix_achat_unitaire": "Prix d'achat par unité"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["produit"].queryset = Produit.objects.order_by("nom")
        self.fields["produit"].empty_label = "Choisir un produit"

    def clean_quantite(self):
        q = self.cleaned_data["quantite"]
        if q < 1:
            raise forms.ValidationError("Au moins 1.")
        return q


class DepenseForm(forms.ModelForm):
    class Meta:
        from boutique.models import Depense

        model = Depense
        fields = ["date", "categorie", "libelle", "montant", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "categorie": forms.Select(attrs={"class": "form-select"}),
            "libelle": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. Pub Facebook semaine 2"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": 50}),
            "note": forms.TextInput(attrs={"class": "form-control", "placeholder": "Facultatif"}),
        }

    def __init__(self, *args, **kwargs):
        from boutique.models import CATEGORIE_MARCHANDISE, CategorieDepense

        super().__init__(*args, **kwargs)
        # Les achats de marchandise passent par « Stock > Arrivage » (qui met aussi le stock à jour)
        self.fields["categorie"].queryset = CategorieDepense.objects.exclude(nom=CATEGORIE_MARCHANDISE)
        self.fields["categorie"].empty_label = "Choisir une catégorie"


class RoleForm(forms.Form):
    nom = forms.CharField(label="Nom du rôle", max_length=80, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. Livreur"}))
    sections = forms.MultipleChoiceField(label="Pages autorisées", required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, role=None, **kwargs):
        from .roles import SECTIONS

        super().__init__(*args, **kwargs)
        self.role = role
        self.fields["sections"].choices = SECTIONS
        if role:
            self.fields["nom"].initial = role.name
            acces = getattr(role, "acces", None)
            self.fields["sections"].initial = acces.liste if acces else []

    def clean_nom(self):
        from django.contrib.auth.models import Group

        from .roles import ADMINISTRATEUR

        nom = self.cleaned_data["nom"].strip()
        if nom.lower() == ADMINISTRATEUR.lower():
            raise forms.ValidationError("Ce nom est réservé.")
        autres = Group.objects.filter(name__iexact=nom)
        if self.role:
            autres = autres.exclude(pk=self.role.pk)
        if autres.exists():
            raise forms.ValidationError("Un rôle porte déjà ce nom.")
        return nom

    def enregistrer(self):
        from django.contrib.auth.models import Group

        from .models import AccesRole

        role = self.role or Group()
        role.name = self.cleaned_data["nom"]
        role.save()
        AccesRole.objects.update_or_create(role=role, defaults={"sections": ",".join(self.cleaned_data["sections"])})
        return role


class ReglagesForm(forms.ModelForm):
    pays = forms.MultipleChoiceField(label="Pays où vous livrez", required=False, widget=forms.CheckboxSelectMultiple)

    class Meta:
        from boutique.models import ReglagesSite

        model = ReglagesSite
        fields = [
            "nom_boutique", "slogan", "whatsapp", "lien_facebook", "lien_instagram", "lien_tiktok", "pixel_facebook",
            "commandes_ouvertes", "message_commandes_fermees", "maintenance", "message_maintenance",
            "horaires_actifs", "commandes_hors_horaires",
        ]
        widgets = {
            "nom_boutique": forms.TextInput(attrs={"class": "form-control"}),
            "slogan": forms.TextInput(attrs={"class": "form-control"}),
            "whatsapp": forms.TextInput(attrs={"class": "form-control", "inputmode": "numeric", "placeholder": "22890123456"}),
            "lien_facebook": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://facebook.com/…"}),
            "lien_instagram": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://instagram.com/…"}),
            "lien_tiktok": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://tiktok.com/@…"}),
            "pixel_facebook": forms.TextInput(attrs={"class": "form-control", "inputmode": "numeric", "placeholder": "Ex. 123456789012345"}),
            "commandes_ouvertes": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "message_commandes_fermees": forms.TextInput(attrs={"class": "form-control"}),
            "maintenance": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "horaires_actifs": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "commandes_hors_horaires": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "message_maintenance": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pays"].choices = [(c, p["nom"]) for c, p in PAYS.items()]
        self.fields["pays"].initial = self.instance.pays_effectifs

    def clean_whatsapp(self):
        num = "".join(c for c in self.cleaned_data["whatsapp"] if c.isdigit())
        if num and not 10 <= len(num) <= 15:
            raise forms.ValidationError("Numéro complet avec l'indicatif, ex. 22890123456 (Togo) ou 2290197123456 (Bénin).")
        return num

    def clean_pays(self):
        pays = self.cleaned_data["pays"]
        if not pays:
            raise forms.ValidationError("Choisissez au moins un pays.")
        return pays

    def save(self, commit=True):
        obj = super().save(commit=False)
        ordre = [c for c in PAYS if c in self.cleaned_data["pays"]]
        obj.pays_livres = ",".join(ordre)
        if commit:
            obj.save()
        return obj


class HoraireJourForm(forms.ModelForm):
    class Meta:
        from boutique.models import HoraireJour

        model = HoraireJour
        fields = ["ouvert", "ouverture", "fermeture"]
        widgets = {
            "ouvert": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "ouverture": forms.TimeInput(attrs={"class": "form-control form-control-sm", "type": "time"}, format="%H:%M"),
            "fermeture": forms.TimeInput(attrs={"class": "form-control form-control-sm", "type": "time"}, format="%H:%M"),
        }

    def clean(self):
        donnees = super().clean()
        debut, fin = donnees.get("ouverture"), donnees.get("fermeture")
        if donnees.get("ouvert") and debut and fin and fin <= debut:
            raise forms.ValidationError("L'heure de fermeture doit être après l'heure d'ouverture.")
        return donnees


def horaires_formset(data=None):
    from django.forms import modelformset_factory

    from boutique.horaires import horaires_semaine
    from boutique.models import HoraireJour

    horaires_semaine()  # crée les 7 jours s'il en manque
    Formset = modelformset_factory(HoraireJour, form=HoraireJourForm, extra=0)
    return Formset(data, queryset=HoraireJour.objects.order_by("jour"), prefix="horaires")
