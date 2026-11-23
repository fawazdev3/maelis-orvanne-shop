"""Pays livrés par la boutique et règles des numéros de téléphone.

Pour ouvrir un nouveau pays : il est déjà décrit ci-dessous (Togo, Bénin, Ghana) ;
il suffit de l'ajouter dans BOUTIQUE_PAYS du fichier .env, par exemple BOUTIQUE_PAYS=TG,BJ
Pour un pays qui n'est pas encore dans la liste, ajoute un bloc sur le même modèle.
"""
import re

from django.conf import settings

PAYS = {
    "TG": {
        "nom": "Togo",
        "drapeau": "🇹🇬",
        "indicatif": "228",
        "exemple": "90 12 34 56",
        "villes": [
            "Lomé", "Agoè-Nyivé", "Baguida", "Tsévié", "Aného", "Kpalimé", "Atakpamé", "Notsé",
            "Sokodé", "Kara", "Bassar", "Tchamba", "Badou", "Vogan", "Mango", "Dapaong",
        ],
    },
    "BJ": {
        "nom": "Bénin",
        "drapeau": "🇧🇯",
        "indicatif": "229",
        "exemple": "01 97 12 34 56",
        "villes": [
            "Cotonou", "Abomey-Calavi", "Porto-Novo", "Sèmè-Kpodji", "Ouidah", "Allada", "Bohicon",
            "Abomey", "Lokossa", "Parakou", "Djougou", "Natitingou", "Kandi",
        ],
    },
    "GH": {
        "nom": "Ghana",
        "drapeau": "🇬🇭",
        "indicatif": "233",
        "exemple": "024 123 4567",
        "villes": [
            "Accra", "Tema", "Kasoa", "Kumasi", "Takoradi", "Cape Coast", "Koforidua", "Ho",
            "Aflao", "Tamale",
        ],
    },
}


def codes_actifs():
    """Pays où la boutique livre, réglés dans .env (BOUTIQUE_PAYS=TG,BJ,GH). Le premier est le pays par défaut."""
    from .models import ReglagesSite

    codes = [c for c in ReglagesSite.charger().pays_effectifs if c in PAYS]
    return codes or ["TG"]


def nom_pays(code):
    return PAYS.get(code, {}).get("nom", code)


# ---------------------------------------------------------------- Numéros

def _local(code, chiffres):
    """Renvoie la partie nationale du numéro (sans indicatif) si elle est valide pour ce pays, sinon None."""
    if code == "TG":  # 8 chiffres : 90 12 34 56
        return chiffres if len(chiffres) == 8 else None
    if code == "BJ":  # 10 chiffres commençant par 01 (depuis le 30/11/2024)
        if len(chiffres) == 10 and chiffres.startswith("01"):
            return chiffres
        if len(chiffres) == 8:  # ancien format : on ajoute 01 devant, comme l'a demandé l'ARCEP
            return "01" + chiffres
        return None
    if code == "GH":  # 0 + 9 chiffres au Ghana, 9 chiffres avec l'indicatif
        if len(chiffres) == 10 and chiffres.startswith("0"):
            return chiffres[1:]
        if len(chiffres) == 9 and not chiffres.startswith("0"):
            return chiffres
        return None
    return chiffres if 6 <= len(chiffres) <= 12 else None


def _joli(code, local):
    if code == "GH":
        groupes = [local[:2], local[2:5], local[5:]]
    else:
        groupes = re.findall(r"\d{1,2}", local)
    return " ".join(groupes)


def normaliser_telephone(saisie, code):
    """Transforme ce que le client a tapé en numéro international.

    Renvoie (chiffres_internationaux, affichage), par ex. ("22890123456", "+228 90 12 34 56").
    Lève ValueError avec un message clair si le numéro ne correspond pas au pays.
    Le client peut aussi taper le numéro complet (+229…, 00233…) : le pays est alors reconnu tout seul.
    """
    brut = (saisie or "").strip()
    chiffres = re.sub(r"\D", "", brut)
    international = brut.startswith("+") or chiffres.startswith("00")
    if chiffres.startswith("00"):
        chiffres = chiffres[2:]

    if international:
        for c, infos in PAYS.items():
            if chiffres.startswith(infos["indicatif"]):
                code, chiffres = c, chiffres[len(infos["indicatif"]):]
                break
        else:
            if 8 <= len(chiffres) <= 15:  # numéro étranger : accepté tel quel
                return chiffres, "+" + chiffres
            raise ValueError("Ce numéro n'est pas complet.")
    else:
        indicatif = PAYS[code]["indicatif"]
        if chiffres.startswith(indicatif) and _local(code, chiffres) is None:
            chiffres = chiffres[len(indicatif):]

    local = _local(code, chiffres)
    if local is None:
        infos = PAYS[code]
        raise ValueError(
            f"Ce numéro ne correspond pas au {infos['nom']} (+{infos['indicatif']}). Exemple : {infos['exemple']}. "
            "Pour un numéro d'un autre pays, écrivez-le en entier avec le + (ex. +233…)."
        )
    return PAYS[code]["indicatif"] + local, f"+{PAYS[code]['indicatif']} {_joli(code, local)}"
