from django import template

register = template.Library()


@register.filter
def fcfa(valeur):
    """Affiche un montant au format « 12 500 FCFA »."""
    if valeur is None or valeur == "":
        return "—"
    try:
        montant = int(valeur)
    except (TypeError, ValueError):
        return valeur
    return f"{montant:,}".replace(",", " ") + " FCFA"


@register.simple_tag(takes_context=True)
def url_avec(context, **params):
    """Reconstruit la query string courante en remplaçant certains paramètres (pagination, filtres)."""
    requete = context["request"].GET.copy()
    for cle, valeur in params.items():
        if valeur in (None, ""):
            requete.pop(cle, None)
        else:
            requete[cle] = valeur
    chaine = requete.urlencode()
    return f"?{chaine}" if chaine else "?"
