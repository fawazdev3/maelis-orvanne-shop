"""Rôles du back-office.

Un rôle donne accès à des « sections ». Le rôle Administrateur a toujours tout (il ne se modifie pas).
Les autres rôles (Comptabilité, ou ceux que vous créez) se règlent dans Équipe > Rôles.
Un compte « superutilisateur » (createsuperuser) est toujours administrateur.
"""
ADMINISTRATEUR = "Administrateur"
COMPTABILITE = "Comptabilité"

SECTIONS = [
    ("commandes", "Commandes"),
    ("produits", "Produits et catégories"),
    ("stock", "Stock"),
    ("statistiques", "Statistiques"),
    ("depenses", "Dépenses"),
    ("livraison", "Tarifs de livraison"),
    ("equipe", "Équipe et rôles"),
    ("reglages", "Réglages du site"),
]
CODES = [c for c, _ in SECTIONS]


def est_admin(user):
    return bool(
        user.is_authenticated and user.is_staff and (user.is_superuser or user.groups.filter(name=ADMINISTRATEUR).exists())
    )


def sections_de(user):
    """Ensemble des sections accessibles (mis en cache sur l'objet user pour la requête)."""
    if not (user.is_authenticated and user.is_staff):
        return set()
    if not hasattr(user, "_sections_mo"):
        if est_admin(user):
            user._sections_mo = set(CODES)
        else:
            from .models import AccesRole

            sections = set()
            for acces in AccesRole.objects.filter(role__user=user):
                sections.update(acces.liste)
            user._sections_mo = sections
    return user._sections_mo


def peut(user, section):
    return section in sections_de(user)


def nom_role(user):
    if user.is_superuser:
        return ADMINISTRATEUR
    g = user.groups.first()
    return g.name if g else "Aucun rôle"
