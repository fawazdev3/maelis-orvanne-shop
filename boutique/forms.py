import json

from django import forms

from .models import Commande
from .pays import PAYS, codes_actifs, normaliser_telephone

QUANTITE_MAX = 99
LIGNES_MAX = 50


AUTRE_VILLE = "__autre__"


def toutes_les_villes():
    return [(v, v) for p in PAYS.values() for v in p["villes"]] + [(AUTRE_VILLE, "Autre ville")]


class CommandeClientForm(forms.ModelForm):
    """Formulaire de livraison rempli par le client sur la page Panier."""

    pays = forms.ChoiceField(label="Pays")
    # Ville choisie dans la liste du pays ; « Autre ville » ouvre le champ libre `ville`
    ville_liste = forms.ChoiceField(label="Ville", required=False, widget=forms.Select(attrs={"class": "form-select"}))
    panier = forms.CharField(widget=forms.HiddenInput)
    # Champ piège invisible : les robots le remplissent, les humains non.
    site_web = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    class Meta:
        model = Commande
        fields = ["nom_client", "telephone", "ville", "mode_paiement", "note"]
        labels = {
            "nom_client": "Nom et prénom",
            "telephone": "Numéro WhatsApp",
            "ville": "Nom de votre ville",
            "mode_paiement": "Mode de paiement",
            "note": "Message (facultatif)",
        }
        widgets = {
            "nom_client": forms.TextInput(attrs={"class": "form-control", "autocomplete": "name", "placeholder": "Ex. Ama Kossi"}),
            "telephone": forms.TextInput(attrs={"class": "form-control", "autocomplete": "tel-national", "inputmode": "tel"}),
            "ville": forms.TextInput(attrs={"class": "form-control", "autocomplete": "address-level2", "placeholder": "Ex. Badou"}),
            "mode_paiement": forms.RadioSelect,
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 2, "placeholder": "Heure de livraison préférée, précisions…"}),
        }
        error_messages = {
            "nom_client": {"required": "Indiquez votre nom."},
            "telephone": {"required": "Indiquez votre numéro."},
            "ville": {"required": "Indiquez votre ville."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        actifs = codes_actifs()
        defaut = actifs[0]
        self.fields["pays"].choices = [(c, PAYS[c]["nom"]) for c in actifs]
        self.fields["pays"].initial = defaut
        self.fields["pays"].widget.attrs["class"] = "form-select"
        if len(actifs) == 1:
            self.fields["pays"].widget = forms.HiddenInput()
        self.fields["ville_liste"].choices = [("", "Choisissez votre ville")] + toutes_les_villes()
        self.fields["ville"].required = False  # rempli seulement pour « Autre ville »
        self.fields["telephone"].widget.attrs["placeholder"] = PAYS[defaut]["exemple"]
        self.fields["mode_paiement"].initial = Commande.ModePaiement.ESPECES
        self.un_seul_pays = len(actifs) == 1

    def clean_panier(self):
        """Lit le panier envoyé par le navigateur : [{"id": 3, "qte": 2}, …].
        Seuls les identifiants et les quantités sont utilisés : les prix viennent toujours de la base."""
        try:
            donnees = json.loads(self.cleaned_data["panier"])
        except (TypeError, ValueError):
            raise forms.ValidationError("Votre panier n'a pas pu être lu. Rechargez la page et réessayez.")
        if not isinstance(donnees, list) or not donnees:
            raise forms.ValidationError("Votre panier est vide.")
        lignes = {}
        for item in donnees[:LIGNES_MAX]:
            try:
                pid, qte = int(item["id"]), int(item["qte"])
            except (KeyError, TypeError, ValueError):
                continue
            if pid > 0 and qte > 0:
                lignes[pid] = min(lignes.get(pid, 0) + qte, QUANTITE_MAX)
        if not lignes:
            raise forms.ValidationError("Votre panier est vide.")
        return lignes

    def clean(self):
        donnees = super().clean()
        if donnees.get("site_web"):
            raise forms.ValidationError("Envoi refusé.")
        choix = donnees.get("ville_liste")
        if choix and choix != AUTRE_VILLE:
            donnees["ville"] = choix
        elif not (donnees.get("ville") or "").strip():
            self.add_error("ville_liste" if not choix else "ville", "Indiquez votre ville.")
        tel, pays = donnees.get("telephone"), donnees.get("pays")
        if tel and pays:
            try:
                self.numero_international, donnees["telephone"] = normaliser_telephone(tel, pays)
            except ValueError as erreur:
                self.add_error("telephone", str(erreur))
        return donnees

    def save(self, commit=True):
        commande = super().save(commit=False)
        commande.pays = self.cleaned_data["pays"]
        commande.ville = self.cleaned_data["ville"].strip()
        commande.telephone_international = self.numero_international
        if commit:
            commande.save()
        return commande
