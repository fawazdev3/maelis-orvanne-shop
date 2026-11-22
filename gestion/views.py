from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from boutique.models import Categorie, Commande, Produit

from .decorators import gestionnaire_requis
from .forms import CategorieForm, CommandeStatutForm, ConnexionForm, ProduitForm


# ---------------------------------------------------------------- Connexion

class ConnexionView(auth_views.LoginView):
    template_name = "gestion/connexion.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


class DeconnexionView(auth_views.LogoutView):
    pass


# ---------------------------------------------------------------- Tableau de bord

@gestionnaire_requis
def tableau_de_bord(request):
    maintenant = timezone.localtime()
    debut_jour = maintenant.replace(hour=0, minute=0, second=0, microsecond=0)
    debut_mois = debut_jour.replace(day=1)
    il_y_a_30_jours = debut_jour - timedelta(days=29)

    commandes_valides = Commande.objects.exclude(statut=Commande.Statut.ANNULEE)

    # Ventes des 30 derniers jours, jour par jour (pour le petit graphique)
    ventes_par_jour = {}
    for c in commandes_valides.filter(date_creation__gte=il_y_a_30_jours).only("date_creation", "total"):
        jour = timezone.localdate(c.date_creation)
        ventes_par_jour[jour] = ventes_par_jour.get(jour, 0) + c.total
    jours = [(il_y_a_30_jours + timedelta(days=i)).date() for i in range(30)]
    serie = [ventes_par_jour.get(j, 0) for j in jours]
    maximum = max(serie) or 1
    graphique = [
        {"jour": j, "montant": m, "hauteur": round(m * 100 / maximum) if m else 0}
        for j, m in zip(jours, serie)
    ]

    a_encaisser = commandes_valides.filter(paiement_recu=False)

    contexte = {
        "page": "tableau_de_bord",
        "nb_commandes_nouvelles": Commande.objects.filter(statut=Commande.Statut.NOUVELLE).count(),
        "nb_commandes_jour": commandes_valides.filter(date_creation__gte=debut_jour).count(),
        "encaisse_mois": commandes_valides.filter(paiement_recu=True, date_paiement__gte=debut_mois).aggregate(
            s=Sum("total")
        )["s"]
        or 0,
        "montant_a_encaisser": a_encaisser.aggregate(s=Sum("total"))["s"] or 0,
        "nb_a_encaisser": a_encaisser.count(),
        "ca_30_jours": sum(serie),
        "nb_produits_actifs": Produit.objects.filter(actif=True).count(),
        "nb_produits_promo": Produit.objects.filter(actif=True, prix_promo__isnull=False).count(),
        "produits_rupture": Produit.objects.filter(actif=True, en_stock=False)[:5],
        "dernieres_commandes": Commande.objects.prefetch_related("lignes")[:6],
        "graphique": graphique,
        "mois_nom": maintenant.strftime("%m/%Y"),
    }
    return render(request, "gestion/tableau_de_bord.html", contexte)


# ---------------------------------------------------------------- Produits

@gestionnaire_requis
def produits_liste(request):
    produits = Produit.objects.select_related("categorie")
    q = request.GET.get("q", "").strip()
    categorie_id = request.GET.get("categorie", "")
    filtre = request.GET.get("filtre", "")

    if q:
        produits = produits.filter(Q(nom__icontains=q) | Q(description__icontains=q))
    if categorie_id.isdigit():
        produits = produits.filter(categorie_id=int(categorie_id))
    if filtre == "visibles":
        produits = produits.filter(actif=True)
    elif filtre == "caches":
        produits = produits.filter(actif=False)
    elif filtre == "promo":
        produits = produits.filter(prix_promo__isnull=False)
    elif filtre == "rupture":
        produits = produits.filter(en_stock=False)

    page = Paginator(produits, 20).get_page(request.GET.get("page"))
    contexte = {
        "page": "produits",
        "produits": page,
        "categories": Categorie.objects.all(),
        "q": q,
        "categorie_id": categorie_id,
        "filtre": filtre,
        "total_produits": Produit.objects.count(),
    }
    return render(request, "gestion/produits_liste.html", contexte)


@gestionnaire_requis
def produit_ajouter(request):
    if not Categorie.objects.exists():
        messages.info(request, "Créez d'abord une catégorie (par exemple « Thés ») avant d'ajouter un produit.")
        return redirect("gestion:categorie_ajouter")
    form = ProduitForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        produit = form.save()
        messages.success(request, f"Le produit « {produit.nom} » a été ajouté.")
        if "ajouter_autre" in request.POST:
            return redirect("gestion:produit_ajouter")
        return redirect("gestion:produits_liste")
    return render(request, "gestion/produit_form.html", {"page": "produits", "form": form, "produit": None})


@gestionnaire_requis
def produit_modifier(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    form = ProduitForm(request.POST or None, request.FILES or None, instance=produit)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Le produit « {produit.nom} » a été mis à jour.")
        return redirect("gestion:produits_liste")
    return render(request, "gestion/produit_form.html", {"page": "produits", "form": form, "produit": produit})


@gestionnaire_requis
def produit_supprimer(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    if request.method == "POST":
        nom = produit.nom
        if produit.image:
            produit.image.delete(save=False)
        produit.delete()
        messages.success(request, f"Le produit « {nom} » a été supprimé.")
        return redirect("gestion:produits_liste")
    return render(
        request,
        "gestion/confirmer_suppression.html",
        {
            "page": "produits",
            "objet": produit,
            "type_objet": "le produit",
            "retour": "gestion:produits_liste",
            "avertissement": "Les anciennes commandes qui contiennent ce produit sont conservées.",
        },
    )


@gestionnaire_requis
@require_POST
def produit_basculer(request, pk, champ):
    """Active ou désactive rapidement « visible » ou « en stock » depuis la liste."""
    produit = get_object_or_404(Produit, pk=pk)
    if champ in ("actif", "en_stock"):
        setattr(produit, champ, not getattr(produit, champ))
        produit.save(update_fields=[champ, "date_modification"])
        libelle = "visible" if champ == "actif" else "en stock"
        etat = "oui" if getattr(produit, champ) else "non"
        messages.success(request, f"« {produit.nom} » — {libelle} : {etat}.")
    return redirect(request.POST.get("suivant") or "gestion:produits_liste")


# ---------------------------------------------------------------- Catégories

@gestionnaire_requis
def categories_liste(request):
    categories = Categorie.objects.annotate(nb_produits=Count("produits"))
    return render(request, "gestion/categories_liste.html", {"page": "categories", "categories": categories})


@gestionnaire_requis
def categorie_ajouter(request):
    form = CategorieForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        categorie = form.save()
        messages.success(request, f"La catégorie « {categorie.nom} » a été créée.")
        return redirect("gestion:categories_liste")
    return render(request, "gestion/categorie_form.html", {"page": "categories", "form": form, "categorie": None})


@gestionnaire_requis
def categorie_modifier(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    form = CategorieForm(request.POST or None, instance=categorie)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"La catégorie « {categorie.nom} » a été mise à jour.")
        return redirect("gestion:categories_liste")
    return render(
        request, "gestion/categorie_form.html", {"page": "categories", "form": form, "categorie": categorie}
    )


@gestionnaire_requis
def categorie_supprimer(request, pk):
    categorie = get_object_or_404(Categorie, pk=pk)
    if request.method == "POST":
        try:
            nom = categorie.nom
            categorie.delete()
            messages.success(request, f"La catégorie « {nom} » a été supprimée.")
        except ProtectedError:
            messages.error(
                request,
                f"Impossible de supprimer « {categorie.nom} » : elle contient encore des produits. "
                "Déplacez ou supprimez d'abord ces produits.",
            )
        return redirect("gestion:categories_liste")
    return render(
        request,
        "gestion/confirmer_suppression.html",
        {
            "page": "categories",
            "objet": categorie,
            "type_objet": "la catégorie",
            "retour": "gestion:categories_liste",
            "avertissement": "Une catégorie qui contient encore des produits ne peut pas être supprimée.",
        },
    )


# ---------------------------------------------------------------- Commandes

@gestionnaire_requis
def commandes_liste(request):
    commandes = Commande.objects.prefetch_related("lignes")
    statut = request.GET.get("statut", "")
    q = request.GET.get("q", "").strip()
    if statut in Commande.Statut.values:
        commandes = commandes.filter(statut=statut)
    elif statut == "a_encaisser":
        commandes = commandes.filter(paiement_recu=False).exclude(statut=Commande.Statut.ANNULEE)
    if q:
        commandes = commandes.filter(
            Q(numero__icontains=q) | Q(nom_client__icontains=q) | Q(telephone__icontains=q) | Q(ville__icontains=q)
        )
    compteurs = dict(Commande.objects.values_list("statut").annotate(n=Count("id")))
    nb_a_encaisser = Commande.objects.filter(paiement_recu=False).exclude(statut=Commande.Statut.ANNULEE).count()
    onglets = (
        [{"valeur": "", "libelle": "Toutes", "n": sum(compteurs.values())}]
        + [{"valeur": v, "libelle": l, "n": compteurs.get(v, 0)} for v, l in Commande.Statut.choices]
        + [{"valeur": "a_encaisser", "libelle": "À encaisser", "n": nb_a_encaisser}]
    )
    page = Paginator(commandes, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "gestion/commandes_liste.html",
        {"page": "commandes", "commandes": page, "statut": statut, "q": q, "onglets": onglets},
    )


@gestionnaire_requis
@require_POST
def commande_paiement(request, pk):
    """Marque rapidement une commande comme payée (ou non) depuis la liste."""
    commande = get_object_or_404(Commande, pk=pk)
    commande.paiement_recu = not commande.paiement_recu
    commande.save()
    if commande.paiement_recu:
        messages.success(request, f"Commande {commande.numero} : paiement reçu à la livraison.")
    else:
        messages.info(request, f"Commande {commande.numero} : paiement marqué comme non reçu.")
    return redirect(request.POST.get("suivant") or "gestion:commandes_liste")


@gestionnaire_requis
def commande_detail(request, pk):
    commande = get_object_or_404(Commande.objects.prefetch_related("lignes__produit"), pk=pk)
    form = CommandeStatutForm(request.POST or None, instance=commande)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Commande {commande.numero} : statut « {commande.get_statut_display()} ».")
        return redirect("gestion:commande_detail", pk=commande.pk)
    total = f"{commande.total:,}".replace(",", " ")
    message_client = (
        f"Bonjour {commande.nom_client}, ici {settings.BOUTIQUE_NOM}. "
        f"Nous avons bien reçu votre commande {commande.numero} d'un montant de {total} FCFA, "
        f"à régler à la livraison ({commande.get_mode_paiement_display().lower()}). "
        f"Nous vous contactons pour convenir de la livraison à {commande.ville}."
    )
    return render(
        request,
        "gestion/commande_detail.html",
        {"page": "commandes", "commande": commande, "form": form, "message_client": message_client},
    )
