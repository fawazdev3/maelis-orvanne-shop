from django.conf import settings


def boutique_infos(request):
    """Rend le nom de la boutique, la devise et le nombre de nouvelles commandes disponibles dans les templates."""
    from boutique.models import ReglagesSite

    reglages = ReglagesSite.charger()
    contexte = {
        "reglages": reglages,
        "BOUTIQUE_NOM": reglages.nom_boutique,
        "BOUTIQUE_DEVISE": settings.BOUTIQUE_DEVISE,
    }
    utilisateur = getattr(request, "user", None)
    if utilisateur is not None and utilisateur.is_authenticated and utilisateur.is_staff and request.path.startswith("/gestion/"):
        from boutique.models import Commande

        from .roles import est_admin, nom_role, sections_de

        contexte["nb_nouvelles_commandes"] = Commande.objects.filter(statut=Commande.Statut.NOUVELLE).count()
        contexte["est_admin"] = est_admin(utilisateur)
        contexte["acces"] = sections_de(utilisateur)
        contexte["nom_role"] = nom_role(utilisateur)
    return contexte
