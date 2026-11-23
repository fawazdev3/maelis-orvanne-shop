"""Back-office : stock (arrivages), dépenses et statistiques."""
import calendar
import csv
from datetime import date, datetime, time, timedelta

from django.contrib import messages
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from boutique.models import (
    CATEGORIE_MARCHANDISE,
    Arrivage,
    CategorieDepense,
    Commande,
    Depense,
    LigneCommande,
    Produit,
)

from .decorators import acces_requis, gestionnaire_requis
from .forms import ArrivageForm, DepenseForm

SEUIL_STOCK_BAS = 3
MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


# ---------------------------------------------------------------- Stock

@acces_requis("stock")
def stock(request):
    form = ArrivageForm(request.POST or None, initial={"produit": request.GET.get("produit")})
    if request.method == "POST" and form.is_valid():
        arrivage = form.save(commit=False)
        arrivage.cree_par = request.user
        arrivage.enregistrer()
        messages.success(
            request,
            f"Arrivage enregistré : {arrivage.produit.nom} × {arrivage.quantite}. "
            f"Stock : {arrivage.produit.stock}. Dépense de {arrivage.montant:,} FCFA ajoutée.".replace(",", " "),
        )
        return redirect("gestion:stock")

    produits = Produit.objects.select_related("categorie").order_by("nom")
    lignes, valeur_totale = [], 0
    for p in produits:
        valeur = (p.stock or 0) * (p.prix_achat or 0)
        valeur_totale += valeur
        etat = "non_suivi" if p.stock is None else ("epuise" if p.stock == 0 else ("bas" if p.stock <= SEUIL_STOCK_BAS else "ok"))
        lignes.append({"p": p, "valeur": valeur, "etat": etat})
    contexte = {
        "page": "stock",
        "form": form,
        "lignes": lignes,
        "valeur_totale": valeur_totale,
        "nb_bas": sum(1 for l in lignes if l["etat"] in ("bas", "epuise")),
        "arrivages": Arrivage.objects.select_related("produit")[:12],
        "prix_achat": {p.pk: p.prix_achat for p in produits if p.prix_achat is not None},
        "seuil": SEUIL_STOCK_BAS,
    }
    return render(request, "gestion/stock.html", contexte)


@acces_requis("stock")
@require_POST
def arrivage_supprimer(request, pk):
    arrivage = get_object_or_404(Arrivage, pk=pk)
    nom, q = arrivage.produit.nom, arrivage.quantite
    arrivage.annuler()
    messages.success(request, f"Arrivage supprimé : {q} retiré(s) du stock de {nom}, dépense annulée.")
    return redirect("gestion:stock")


# ---------------------------------------------------------------- Dépenses

def _mois_demande(request):
    aujourd_hui = timezone.localdate()
    try:
        a, m = (int(x) for x in request.GET.get("mois", "").split("-"))
        return date(a, m, 1)
    except (ValueError, TypeError):
        return aujourd_hui.replace(day=1)


@acces_requis("depenses")
def depenses(request, pk=None):
    depense = get_object_or_404(Depense, pk=pk) if pk else None
    if depense and hasattr(depense, "arrivage"):
        messages.info(request, "Cette dépense vient d'un arrivage : modifiez-la depuis la page Stock.")
        return redirect("gestion:stock")

    if request.method == "POST" and request.POST.get("action") == "categorie":
        nom = request.POST.get("nom", "").strip()
        if nom:
            CategorieDepense.objects.get_or_create(nom=nom)
            messages.success(request, f"Catégorie « {nom} » ajoutée.")
        return redirect(request.get_full_path())

    form = DepenseForm(request.POST or None, instance=depense)
    if request.method == "POST" and form.is_valid():
        d = form.save(commit=False)
        if not d.pk:
            d.cree_par = request.user
        d.save()
        messages.success(request, f"Dépense « {d.libelle} » enregistrée.")
        return redirect(f"{reverse('gestion:depenses')}?mois={d.date:%Y-%m}")

    debut = _mois_demande(request)
    fin = (debut + timedelta(days=32)).replace(day=1)
    du_mois = Depense.objects.filter(date__gte=debut, date__lt=fin).select_related("categorie", "cree_par", "arrivage")
    par_categorie = du_mois.values("categorie__nom").annotate(total=Sum("montant")).order_by("-total")
    contexte = {
        "page": "depenses",
        "form": form,
        "depense": depense,
        "depenses": du_mois,
        "total_mois": du_mois.aggregate(s=Sum("montant"))["s"] or 0,
        "par_categorie": par_categorie,
        "mois": debut,
        "mois_nom": f"{MOIS_FR[debut.month - 1]} {debut.year}",
        "mois_precedent": (debut - timedelta(days=1)).replace(day=1),
        "mois_suivant": fin if fin <= timezone.localdate() else None,
        "categories": CategorieDepense.objects.all(),
    }
    return render(request, "gestion/depenses.html", contexte)


@acces_requis("depenses")
@require_POST
def depense_supprimer(request, pk):
    d = get_object_or_404(Depense, pk=pk)
    if hasattr(d, "arrivage"):
        messages.error(request, "Cette dépense vient d'un arrivage : supprimez l'arrivage depuis la page Stock.")
    else:
        d.delete()
        messages.success(request, "Dépense supprimée.")
    return redirect(f"{reverse('gestion:depenses')}?mois={d.date:%Y-%m}")


# ---------------------------------------------------------------- Statistiques

def _cellule(v):
    """Empêche qu'un texte saisi par un client (ex. « =HYPERLINK(...) ») soit exécuté comme formule par Excel."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        if v[:1] == "+" and v[1:].replace(" ", "").isdigit():
            return v  # un numéro de téléphone (+228 90…) n'est pas une formule
        return "'" + v
    return v


class _Ecrivain:
    def __init__(self, w):
        self.w = w

    def writerow(self, ligne):
        self.w.writerow([_cellule(v) for v in ligne])


def periode_demandee(request):
    """Renvoie (type, début, fin exclue, libellé, précédente, suivante) à partir de ?periode=jour|mois|annee&ref=…"""
    aujourd_hui = timezone.localdate()
    type_ = request.GET.get("periode", "mois")
    ref = request.GET.get("ref", "")
    try:
        if type_ == "jour":
            jour = date.fromisoformat(ref) if ref else aujourd_hui
            return ("jour", jour, jour + timedelta(days=1), f"{jour.day} {MOIS_FR[jour.month - 1]} {jour.year}",
                    (jour - timedelta(days=1)).isoformat(), (jour + timedelta(days=1)).isoformat() if jour < aujourd_hui else None)
        if type_ == "annee":
            a = int(ref) if ref else aujourd_hui.year
            return ("annee", date(a, 1, 1), date(a + 1, 1, 1), str(a), str(a - 1), str(a + 1) if a < aujourd_hui.year else None)
        a, m = (int(x) for x in ref.split("-")) if ref else (aujourd_hui.year, aujourd_hui.month)
        debut = date(a, m, 1)
        fin = (debut + timedelta(days=32)).replace(day=1)
        prec = (debut - timedelta(days=1)).replace(day=1)
        return ("mois", debut, fin, f"{MOIS_FR[m - 1]} {a}", f"{prec:%Y-%m}", f"{fin:%Y-%m}" if fin <= aujourd_hui else None)
    except (ValueError, TypeError):
        debut = aujourd_hui.replace(day=1)
        fin = (debut + timedelta(days=32)).replace(day=1)
        return ("mois", debut, fin, f"{MOIS_FR[debut.month - 1]} {debut.year}", None, None)


def _bornes(debut, fin):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(debut, time.min), tz), timezone.make_aware(datetime.combine(fin, time.min), tz)


def calculer_statistiques(debut, fin):
    """Chiffres d'une période. Une vente compte le jour où la commande est livrée."""
    d1, d2 = _bornes(debut, fin)
    livrees = Commande.objects.filter(statut=Commande.Statut.LIVREE, date_livraison__gte=d1, date_livraison__lt=d2)
    agg = livrees.aggregate(ventes=Sum("montant_articles"), livraison=Sum("frais_livraison"), n=Count("pk"))
    ventes, frais, nb = agg["ventes"] or 0, agg["livraison"] or 0, agg["n"]

    lignes = LigneCommande.objects.filter(commande__in=livrees)
    cout = lignes.filter(prix_achat_unitaire__isnull=False).aggregate(
        s=Sum(F("prix_achat_unitaire") * F("quantite"))
    )["s"] or 0
    sans_cout = lignes.filter(prix_achat_unitaire__isnull=True).aggregate(s=Sum(F("prix_unitaire") * F("quantite")))["s"] or 0

    deps = Depense.objects.filter(date__gte=debut, date__lt=fin)
    achats_marchandise = deps.filter(categorie__nom=CATEGORIE_MARCHANDISE).aggregate(s=Sum("montant"))["s"] or 0
    autres_depenses = deps.exclude(categorie__nom=CATEGORIE_MARCHANDISE).aggregate(s=Sum("montant"))["s"] or 0
    depenses_par_cat = deps.exclude(categorie__nom=CATEGORIE_MARCHANDISE).values("categorie__nom").annotate(
        total=Sum("montant")
    ).order_by("-total")

    marge = ventes - cout
    top = (
        lignes.values("nom_produit")
        .annotate(qte=Sum("quantite"), ca=Sum(F("prix_unitaire") * F("quantite")),
                  cout=Sum(F("prix_achat_unitaire") * F("quantite")))
        .order_by("-ca")[:8]
    )
    en_cours = Commande.objects.filter(
        statut__in=[Commande.Statut.NOUVELLE, Commande.Statut.CONFIRMEE, Commande.Statut.EN_LIVRAISON],
        date_creation__gte=d1, date_creation__lt=d2,
    ).aggregate(n=Count("pk"), s=Sum("total"))
    return {
        "ventes": ventes,
        "frais_livraison": frais,
        "encaisse": ventes + frais,
        "nb_commandes": nb,
        "panier_moyen": round(ventes / nb) if nb else 0,
        "cout_achat": cout,
        "ventes_sans_cout": sans_cout,
        "marge": marge,
        "taux_marge": round(marge * 100 / ventes) if ventes else 0,
        "autres_depenses": autres_depenses,
        "depenses_par_cat": depenses_par_cat,
        "achats_marchandise": achats_marchandise,
        "benefice": marge + frais - autres_depenses,
        "top": [dict(t, marge=(t["ca"] - t["cout"]) if t["cout"] is not None else None) for t in top],
        "en_cours_n": en_cours["n"],
        "en_cours_montant": en_cours["s"] or 0,
        "livrees": livrees,
    }


def _graphique(type_, debut, fin, livrees):
    """Barres : par jour pour un mois, par mois pour une année."""
    if type_ == "jour":
        return []
    totaux = {}
    for c in livrees.only("date_livraison", "montant_articles"):
        d = timezone.localtime(c.date_livraison).date()
        cle = d if type_ == "mois" else d.month
        totaux[cle] = totaux.get(cle, 0) + c.montant_articles
    if type_ == "mois":
        cles = [debut + timedelta(days=i) for i in range((fin - debut).days)]
        libelles = [str(c.day) for c in cles]
    else:
        cles = list(range(1, 13))
        libelles = [MOIS_FR[m - 1][:3] for m in cles]
    maximum = max([totaux.get(c, 0) for c in cles] + [1])
    return [
        {"libelle": l, "montant": totaux.get(c, 0), "hauteur": round(totaux.get(c, 0) * 100 / maximum)}
        for c, l in zip(cles, libelles)
    ]


@acces_requis("statistiques")
def statistiques(request):
    type_, debut, fin, libelle, prec, suiv = periode_demandee(request)
    stats = calculer_statistiques(debut, fin)
    aujourd_hui = timezone.localdate()
    mois_debut = aujourd_hui.replace(day=1)
    contexte = {
        "page": "statistiques",
        "type": type_,
        "libelle": libelle,
        "prec": prec,
        "suiv": suiv,
        "ref": request.GET.get("ref", ""),
        "s": stats,
        "graphique": _graphique(type_, debut, fin, stats["livrees"]),
        # Rappel permanent en haut de page : aujourd'hui et ce mois-ci
        "jour": calculer_statistiques(aujourd_hui, aujourd_hui + timedelta(days=1)),
        "ce_mois": calculer_statistiques(mois_debut, (mois_debut + timedelta(days=32)).replace(day=1)),
        "nom_ce_mois": f"{MOIS_FR[aujourd_hui.month - 1]} {aujourd_hui.year}",
    }
    return render(request, "gestion/statistiques.html", contexte)


@acces_requis("statistiques")
def statistiques_export(request):
    """Export CSV (s'ouvre dans Excel) des ventes ou des dépenses de la période choisie."""
    type_, debut, fin, libelle, _, _ = periode_demandee(request)
    quoi = request.GET.get("quoi", "ventes")
    reponse = HttpResponse(content_type="text/csv; charset=utf-8")
    nom = f"{quoi}_{libelle.replace(' ', '_')}.csv"
    reponse["Content-Disposition"] = f'attachment; filename="{nom}"'
    reponse.write("﻿")  # pour qu'Excel lise bien les accents
    w = _Ecrivain(csv.writer(reponse, delimiter=";"))
    if quoi == "depenses":
        w.writerow(["Date", "Catégorie", "Libellé", "Montant (FCFA)", "Note", "Saisi par"])
        for d in Depense.objects.filter(date__gte=debut, date__lt=fin).select_related("categorie", "cree_par").order_by("date"):
            w.writerow([d.date.strftime("%d/%m/%Y"), d.categorie.nom, d.libelle, d.montant, d.note,
                        d.cree_par.get_username() if d.cree_par else ""])
        return reponse
    w.writerow(["Livrée le", "Commande", "Client", "Téléphone", "Ville", "Pays", "Articles (FCFA)", "Livraison (FCFA)",
                "Total (FCFA)", "Coût d'achat (FCFA)", "Marge sur articles (FCFA)", "Paiement", "Payée"])
    livrees = calculer_statistiques(debut, fin)["livrees"].prefetch_related("lignes").order_by("date_livraison")
    for c in livrees:
        cout = sum((l.prix_achat_unitaire or 0) * l.quantite for l in c.lignes.all())
        complet = all(l.prix_achat_unitaire is not None for l in c.lignes.all())
        w.writerow([
            timezone.localtime(c.date_livraison).strftime("%d/%m/%Y"), c.numero, c.nom_client, c.telephone_affiche,
            c.ville, c.nom_pays, c.montant_articles, c.frais_livraison or 0, c.total,
            cout if complet else "", c.montant_articles - cout if complet else "",
            c.get_mode_paiement_display(), "oui" if c.paiement_recu else "non",
        ])
    return reponse
