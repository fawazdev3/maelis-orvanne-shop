from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from boutique.models import Categorie, Commande, Produit, TarifLivraison
from boutique.whatsapp import fiche_livraison, messages_client

from .decorators import acces_requis, gestionnaire_requis
from .forms import CategorieForm, CommandeStatutForm, ConnexionForm, ProduitForm, TarifLivraisonForm, CompteForm, RoleForm


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

@acces_requis("produits")
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


@acces_requis("produits")
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


@acces_requis("produits")
def produit_modifier(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    form = ProduitForm(request.POST or None, request.FILES or None, instance=produit)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Le produit « {produit.nom} » a été mis à jour.")
        return redirect("gestion:produits_liste")
    return render(request, "gestion/produit_form.html", {"page": "produits", "form": form, "produit": produit})


@acces_requis("produits")
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


@acces_requis("produits")
@require_POST
def produit_basculer(request, pk, champ):
    """Active ou désactive rapidement « visible » ou « en stock » depuis la liste."""
    produit = get_object_or_404(Produit, pk=pk)
    if champ == "en_stock" and produit.stock is not None:
        messages.info(request, f"Le stock de « {produit.nom} » est suivi en quantité : utilisez la page Stock.")
    elif champ in ("actif", "en_stock"):
        setattr(produit, champ, not getattr(produit, champ))
        produit.save(update_fields=[champ, "date_modification"])
        libelle = "visible" if champ == "actif" else "en stock"
        etat = "oui" if getattr(produit, champ) else "non"
        messages.success(request, f"« {produit.nom} » — {libelle} : {etat}.")
    return redirect(request.POST.get("suivant") or "gestion:produits_liste")


# ---------------------------------------------------------------- Catégories

@acces_requis("produits")
def categories_liste(request):
    categories = Categorie.objects.annotate(nb_produits=Count("produits"))
    return render(request, "gestion/categories_liste.html", {"page": "categories", "categories": categories})


@acces_requis("produits")
def categorie_ajouter(request):
    form = CategorieForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        categorie = form.save()
        messages.success(request, f"La catégorie « {categorie.nom} » a été créée.")
        return redirect("gestion:categories_liste")
    return render(request, "gestion/categorie_form.html", {"page": "categories", "form": form, "categorie": None})


@acces_requis("produits")
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


@acces_requis("produits")
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

@acces_requis("commandes")
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
            Q(numero__icontains=q) | Q(nom_client__icontains=q) | Q(telephone__icontains=q) | Q(telephone_international__icontains="".join(ch for ch in q if ch.isdigit()) or q) | Q(ville__icontains=q)
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


@acces_requis("commandes")
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


@acces_requis("commandes")
def commande_detail(request, pk):
    commande = get_object_or_404(Commande.objects.prefetch_related("lignes__produit"), pk=pk)
    form = CommandeStatutForm(request.POST or None, instance=commande)
    if request.method == "POST" and form.is_valid():
        form.save()
        commande.recalculer_total()  # les frais de livraison ont pu changer
        messages.success(request, f"Commande {commande.numero} mise à jour.")
        return redirect("gestion:commande_detail", pk=commande.pk)
    return render(
        request,
        "gestion/commande_detail.html",
        {
            "page": "commandes",
            "commande": commande,
            "form": form,
            "messages_client": messages_client(commande),
            "fiche": fiche_livraison(commande),
        },
    )


# ---------------------------------------------------------------- Tarifs de livraison

@acces_requis("livraison")
def livraison_tarifs(request, pk=None):
    """Liste des tarifs + formulaire d'ajout (ou de modification si pk est donné) sur la même page."""
    tarif = get_object_or_404(TarifLivraison, pk=pk) if pk else None
    form = TarifLivraisonForm(request.POST or None, instance=tarif)
    if request.method == "POST" and form.is_valid():
        t = form.save()
        messages.success(request, f"Tarif « {t.ville or 'Autres villes'} » enregistré.")
        return redirect("gestion:livraison_tarifs")
    from boutique.pays import PAYS, codes_actifs

    groupes = []
    for code, infos in PAYS.items():
        tarifs = TarifLivraison.objects.filter(pays=code)
        if tarifs or code in codes_actifs():
            groupes.append({"code": code, "nom": infos["nom"], "tarifs": tarifs, "livre": code in codes_actifs()})
    return render(
        request,
        "gestion/livraison_tarifs.html",
        {"page": "livraison", "form": form, "tarif": tarif, "groupes": groupes},
    )


@acces_requis("livraison")
@require_POST
def livraison_tarif_supprimer(request, pk):
    tarif = get_object_or_404(TarifLivraison, pk=pk)
    tarif.delete()
    messages.success(request, f"Tarif « {tarif.ville or 'Autres villes'} » supprimé.")
    return redirect("gestion:livraison_tarifs")


# ---------------------------------------------------------------- Équipe et rôles

def _contexte_equipe(request, **extra):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Group

    from .roles import ADMINISTRATEUR, SECTIONS, nom_role

    noms = dict(SECTIONS)
    comptes = [{"u": u, "role": nom_role(u)} for u in get_user_model().objects.filter(is_staff=True).order_by("-is_active", "username")]
    roles = []
    for g in Group.objects.annotate(nb=Count("user")).order_by("name"):
        if g.name == ADMINISTRATEUR:
            pages = ["Tout"]
            # les superutilisateurs (createsuperuser) sont administrateurs même sans le groupe
            g.nb += get_user_model().objects.filter(is_staff=True, is_superuser=True).exclude(groups=g).count()
        else:
            acces = getattr(g, "acces", None)
            pages = [noms[c] for c in (acces.liste if acces else []) if c in noms]
        roles.append({"g": g, "nb": g.nb, "pages": pages, "fixe": g.name == ADMINISTRATEUR})
    return {"page": "equipe", "comptes": comptes, "roles": roles, **extra}


@acces_requis("equipe")
def equipe(request, pk=None):
    from django.contrib.auth import get_user_model

    compte = get_object_or_404(get_user_model(), pk=pk, is_staff=True) if pk else None
    form = CompteForm(request.POST or None, compte=compte, moi=request.user)
    if request.method == "POST" and form.is_valid():
        c = form.enregistrer()
        messages.success(request, f"Compte « {c.username} » enregistré.")
        return redirect("gestion:equipe")
    return render(request, "gestion/equipe.html", _contexte_equipe(request, form=form, compte=compte, mode="compte"))


@acces_requis("equipe")
@require_POST
def compte_basculer(request, pk):
    """Désactive ou réactive un compte (un compte désactivé ne peut plus se connecter)."""
    from django.contrib.auth import get_user_model

    compte = get_object_or_404(get_user_model(), pk=pk, is_staff=True)
    if compte == request.user:
        messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
    else:
        compte.is_active = not compte.is_active
        compte.save(update_fields=["is_active"])
        messages.success(request, f"Compte « {compte.username} » {'réactivé' if compte.is_active else 'désactivé'}.")
    return redirect("gestion:equipe")


@acces_requis("equipe")
@require_POST
def compte_supprimer(request, pk):
    from django.contrib.auth import get_user_model

    compte = get_object_or_404(get_user_model(), pk=pk, is_staff=True)
    if compte == request.user:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
    else:
        nom = compte.username
        compte.delete()  # ses dépenses et arrivages restent, sans nom d'auteur
        messages.success(request, f"Compte « {nom} » supprimé.")
    return redirect("gestion:equipe")


@acces_requis("equipe")
def role_form(request, pk=None):
    from django.contrib.auth.models import Group

    from .roles import ADMINISTRATEUR

    role = get_object_or_404(Group, pk=pk) if pk else None
    if role and role.name == ADMINISTRATEUR:
        messages.info(request, "Le rôle Administrateur a toujours accès à tout : il ne se modifie pas.")
        return redirect("gestion:equipe")
    form = RoleForm(request.POST or None, role=role)
    if request.method == "POST" and form.is_valid():
        r = form.enregistrer()
        messages.success(request, f"Rôle « {r.name} » enregistré.")
        return redirect("gestion:equipe")
    return render(request, "gestion/equipe.html", _contexte_equipe(request, form=form, role=role, mode="role"))


@acces_requis("equipe")
@require_POST
def role_supprimer(request, pk):
    from django.contrib.auth.models import Group

    from .roles import ADMINISTRATEUR

    role = get_object_or_404(Group, pk=pk)
    if role.name == ADMINISTRATEUR:
        messages.error(request, "Le rôle Administrateur ne peut pas être supprimé.")
    elif role.user_set.exists():
        messages.error(request, f"Le rôle « {role.name} » est encore attribué à des comptes : changez-leur de rôle d'abord.")
    else:
        nom = role.name
        role.delete()
        messages.success(request, f"Rôle « {nom} » supprimé.")
    return redirect("gestion:equipe")


@acces_requis("commandes")
@require_POST
def commande_supprimer(request, pk):
    """Supprime une commande (commande de test, doublon…). Si elle était livrée, son stock est d'abord remis."""
    commande = get_object_or_404(Commande, pk=pk)
    numero = commande.numero
    if commande.stock_deduit:
        commande.statut = Commande.Statut.ANNULEE
        commande.save()
    commande.delete()
    messages.success(request, f"Commande {numero} supprimée.")
    return redirect("gestion:commandes_liste")
