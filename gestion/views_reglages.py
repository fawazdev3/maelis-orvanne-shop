"""Back-office : réglages du site et maintenance."""
import io
import platform
from pathlib import Path

import django
from django.conf import settings
from django.contrib import messages
from django.core.management import call_command
from django.db import connection, transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from boutique.horaires import etat_boutique
from boutique.models import Arrivage, Categorie, Commande, Produit, ReglagesSite

from .decorators import acces_requis
from .forms import ReglagesForm, horaires_formset


def _taille_dossier(chemin):
    total = sum(f.stat().st_size for f in Path(chemin).rglob("*") if f.is_file()) if Path(chemin).exists() else 0
    for unite in ("o", "Ko", "Mo", "Go"):
        if total < 1024:
            return f"{total:.0f} {unite}"
        total /= 1024
    return f"{total:.1f} To"


def _donnees_exemple():
    produits = Produit.objects.filter(nom__endswith="(exemple)")
    return {
        "produits": produits.count(),
        "categories": Categorie.objects.filter(nom__endswith="(exemple)").count(),
        "commandes": Commande.objects.filter(nom_client__endswith="(exemple)").count(),
    }


@acces_requis("reglages")
def reglages(request):
    obj = ReglagesSite.charger()
    form = ReglagesForm(request.POST or None, instance=obj)
    horaires = horaires_formset(request.POST or None)
    if request.method == "POST":
        if form.is_valid() and horaires.is_valid():
            with transaction.atomic():
                form.save()
                horaires.save()
            messages.success(request, "Réglages enregistrés.")
            return redirect("gestion:reglages")
        messages.error(request, "Certains réglages sont à corriger : voir les messages en rouge.")
    exemple = _donnees_exemple()
    contexte = {
        "page": "reglages",
        "form": form,
        "horaires": horaires,
        "etat_boutique": etat_boutique(reglages=obj),
        "obj": obj,
        "whatsapp_env": "".join(c for c in (settings.BOUTIQUE_WHATSAPP or "") if c.isdigit()),
        "exemple": exemple,
        "a_des_exemples": any(exemple.values()),
        "infos": [
            ("Base de données", "PostgreSQL" if connection.vendor == "postgresql" else "SQLite (développement)"),
            ("Mode", "Développement (DEBUG activé)" if settings.DEBUG else "Production"),
            ("Produits / commandes", f"{Produit.objects.count()} / {Commande.objects.count()}"),
            ("Photos des produits", _taille_dossier(settings.MEDIA_ROOT)),
            ("Versions", f"Django {django.get_version()} · Python {platform.python_version()}"),
        ],
    }
    return render(request, "gestion/reglages.html", contexte)


@acces_requis("reglages")
def sauvegarde(request):
    """Télécharge toutes les données de la boutique (produits, commandes, stock, dépenses, réglages, rôles)
    dans un fichier JSON. Restauration : python manage.py loaddata fichier.json"""
    tampon = io.StringIO()
    call_command("dumpdata", "boutique", "gestion", "auth.group", indent=2, stdout=tampon)
    reponse = HttpResponse(tampon.getvalue(), content_type="application/json")
    nom = f"sauvegarde_maelis_{timezone.localtime():%Y-%m-%d_%Hh%M}.json"
    reponse["Content-Disposition"] = f'attachment; filename="{nom}"'
    return reponse


@acces_requis("reglages")
@require_POST
def retirer_exemples(request):
    """Supprime les données créées par `donnees_exemple` (noms qui finissent par « (exemple) »)."""
    with transaction.atomic():
        produits = Produit.objects.filter(nom__endswith="(exemple)")
        for a in Arrivage.objects.filter(produit__in=produits):
            if a.depense:
                a.depense.delete()
            a.delete()
        Commande.objects.filter(nom_client__endswith="(exemple)").delete()
        n = produits.count()
        produits.delete()
        Categorie.objects.filter(nom__endswith="(exemple)", produits__isnull=True).delete()
    messages.success(request, f"Données d'exemple retirées ({n} produit{'s' if n > 1 else ''}).")
    return redirect("gestion:reglages")
