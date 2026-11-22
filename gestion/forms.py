from django import forms
from django.contrib.auth.forms import AuthenticationForm

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
        fields = ["statut", "mode_paiement", "paiement_recu", "note_interne"]
        widgets = {
            "statut": forms.Select(attrs={"class": "form-select"}),
            "mode_paiement": forms.Select(attrs={"class": "form-select"}),
            "paiement_recu": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"}),
            "note_interne": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Ex. livreur prévu demain à 10 h"}
            ),
        }
