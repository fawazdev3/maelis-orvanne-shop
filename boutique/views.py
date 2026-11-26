from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, F, Q
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from .forms import CommandeClientForm
from .horaires import etat_boutique
from .models import Categorie, Commande, LigneCommande, Produit, ReglagesSite, TarifLivraison
from .pays import PAYS
from .whatsapp import lien_whatsapp


PRODUITS_PAR_PAGE = 12  # 3 rangées de 4 sur ordinateur, 6 rangées de 2 sur téléphone


def produits_en_ligne():
    """Produits visibles sur le site : actifs et dans une catégorie visible."""
    return Produit.objects.filter(actif=True, categorie__active=True).select_related("categorie")


def categories_menu():
    return Categorie.objects.filter(active=True).annotate(
        nb=Count("produits", filter=Q(produits__actif=True))
    ).filter(nb__gt=0)


# ---------------------------------------------------------------- Pages

def accueil(request):
    produits = produits_en_ligne()
    vedettes = list(produits.filter(mis_en_avant=True)[:8])
    if not vedettes:
        vedettes = list(produits[:8])
    contexte = {
        "vedettes": vedettes,
        # Les promotions déjà visibles dans la sélection ne sont pas répétées
        "promotions": produits.filter(prix_promo__isnull=False, en_stock=True).exclude(pk__in=[p.pk for p in vedettes])[:4],
        "a_des_promos": produits.filter(prix_promo__isnull=False, en_stock=True).exists(),
        "categories": categories_menu(),
        "page": "accueil",
    }
    return render(request, "boutique/accueil.html", contexte)


def catalogue(request, slug=None):
    produits = produits_en_ligne().annotate(prix_tri=Coalesce("prix_promo", "prix"))
    categorie = None
    if slug:
        categorie = get_object_or_404(Categorie, slug=slug, active=True)
        produits = produits.filter(categorie=categorie)

    q = request.GET.get("q", "").strip()
    if q:
        produits = produits.filter(Q(nom__icontains=q) | Q(description__icontains=q))

    tri = request.GET.get("tri", "")
    ordres = {
        "prix_croissant": ["prix_tri"],
        "prix_decroissant": ["-prix_tri"],
        "promo": ["-prix_promo"],
    }
    produits = produits.order_by(F("en_stock").desc(), *ordres.get(tri, ["-mis_en_avant", "-date_creation"]))

    page = Paginator(produits, PRODUITS_PAR_PAGE).get_page(request.GET.get("page"))
    contexte = {
        "produits": page,
        "numeros_pages": page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1),
        "categorie": categorie,
        "categories": categories_menu(),
        "q": q,
        "tri": tri,
        "page": "catalogue",
    }
    return render(request, "boutique/catalogue.html", contexte)


def produit_detail(request, slug):
    produit = get_object_or_404(produits_en_ligne(), slug=slug)
    similaires = produits_en_ligne().filter(categorie=produit.categorie).exclude(pk=produit.pk)[:4]
    return render(
        request,
        "boutique/produit.html",
        {"produit": produit, "similaires": similaires, "categories": categories_menu(), "page": "catalogue"},
    )


def contexte_panier(form):
    pays_choisi = form["pays"].value() or form.fields["pays"].initial
    infos = PAYS.get(pays_choisi, PAYS["TG"])
    return {
        "form": form,
        "villes": infos["villes"],
        "indicatif": infos["indicatif"],
        "ville_choisie": form["ville_liste"].value() or "",
        "pays_infos": {
            c: {"exemple": p["exemple"], "villes": p["villes"], "indicatif": p["indicatif"], "nom": p["nom"]}
            for c, p in PAYS.items()
        },
        "whatsapp_actif": bool(ReglagesSite.charger().whatsapp_effectif),
        "tarifs": [
            {"pays": t.pays, "ville": t.ville_normalisee, "frais": t.frais} for t in TarifLivraison.objects.all()
        ],
        "categories": categories_menu(),
        "page": "panier",
    }


def panier(request):
    return render(request, "boutique/panier.html", contexte_panier(CommandeClientForm()))


@require_POST
def commander(request):
    from config.limites import adresse_ip, ajouter, compte

    form = CommandeClientForm(request.POST)
    maximum, duree = settings.LIMITE_COMMANDES
    cle_ip = f"commandes:{adresse_ip(request)}"
    if compte(cle_ip) >= maximum:
        form.is_valid()
        form.add_error(None, "Trop de commandes envoyées en peu de temps. Réessayez dans quelques minutes, ou écrivez-nous sur WhatsApp.")
        return render(request, "boutique/panier.html", contexte_panier(form), status=429)
    reglages = ReglagesSite.charger()
    if not reglages.commandes_ouvertes:
        form.is_valid()
        form.add_error(None, reglages.message_commandes_fermees)
        return render(request, "boutique/panier.html", contexte_panier(form), status=400)
    etat = etat_boutique(reglages=reglages)
    if etat and not etat["commandes_possibles"]:
        form.is_valid()
        form.add_error(None, etat["texte"] + " Vous pourrez valider votre commande à ce moment-là : votre panier reste enregistré.")
        return render(request, "boutique/panier.html", contexte_panier(form), status=400)
    if not form.is_valid():
        return render(request, "boutique/panier.html", contexte_panier(form), status=400)

    quantites = form.cleaned_data["panier"]
    produits = {p.pk: p for p in produits_en_ligne().filter(pk__in=quantites.keys(), en_stock=True)}
    indisponibles = [pid for pid in quantites if pid not in produits]
    if not produits:
        form.add_error(None, "Les produits de votre panier ne sont plus disponibles.")
        return render(request, "boutique/panier.html", contexte_panier(form), status=400)

    with transaction.atomic():
        commande = form.save(commit=False)
        commande.frais_livraison = TarifLivraison.frais_pour(commande.pays, commande.ville)
        commande.save()
        for pid, produit in produits.items():
            LigneCommande.objects.create(
                commande=commande,
                produit=produit,
                nom_produit=produit.nom,
                prix_unitaire=produit.prix_actuel,  # toujours le prix de la base, jamais celui du navigateur
                prix_achat_unitaire=produit.prix_achat,
                quantite=quantites[pid],
            )
        commande.recalculer_total()
    ajouter(cle_ip, duree)

    if indisponibles:
        messages.info(request, "Certains articles n'étaient plus disponibles et ont été retirés de votre commande.")
    return redirect("boutique:merci", jeton=commande.jeton)


def merci(request, jeton):
    commande = get_object_or_404(Commande.objects.prefetch_related("lignes"), jeton=jeton)
    return render(
        request,
        "boutique/merci.html",
        {
            "commande": commande,
            "lien_whatsapp": lien_whatsapp(commande),
            "categories": categories_menu(),
            "debug": settings.DEBUG,
        },
    )


# ---------------------------------------------------------------- API du panier

@require_GET
def api_produits(request):
    """Renvoie les informations à jour des produits du panier : /api/produits/?ids=1,2,3"""
    ids = [int(x) for x in request.GET.get("ids", "").split(",") if x.strip().isdigit()][:50]
    produits = produits_en_ligne().filter(pk__in=ids)
    donnees = [
        {
            "id": p.pk,
            "nom": p.nom,
            "url": reverse("boutique:produit", args=[p.slug]),
            "image": p.image.url if p.image else "",
            "prix": p.prix,
            "prix_actuel": p.prix_actuel,
            "en_promo": p.en_promo,
            "disponible": p.en_stock,
            "categorie": p.categorie.nom,
        }
        for p in produits
    ]
    return JsonResponse({"produits": donnees, "whatsapp_actif": bool(ReglagesSite.charger().whatsapp_effectif)})
