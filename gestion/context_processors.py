from django.conf import settings


def boutique_infos(request):
    """Rend le nom de la boutique, la devise et le nombre de nouvelles commandes disponibles dans les templates."""
    contexte = {
        "BOUTIQUE_NOM": settings.BOUTIQUE_NOM,
        "BOUTIQUE_DEVISE": settings.BOUTIQUE_DEVISE,
    }
    utilisateur = getattr(request, "user", None)
    if utilisateur is not None and utilisateur.is_authenticated and utilisateur.is_staff and request.path.startswith("/gestion/"):
        from boutique.models import Commande

        contexte["nb_nouvelles_commandes"] = Commande.objects.filter(statut=Commande.Statut.NOUVELLE).count()
    return contexte
