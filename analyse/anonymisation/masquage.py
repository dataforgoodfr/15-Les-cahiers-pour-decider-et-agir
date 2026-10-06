"""Ce qu'il faut masquer, d'après les repérages et la relecture (issue #7).

La relecture est inversée : dans le doute, on cache. Tout repérage (règles,
modèles, zones de formulaire) est masqué par défaut ; le relecteur rétablit
les fausses alertes et encadre les oublis d'une note de donnée personnelle.
Ce qui reste à masquer :

    repérages − rétablis + notes

Des cadres en points PDF, jamais le texte.
"""

import hashlib

CHAMPS = ("x0", "y0", "x1", "y1")
INCLUS = 0.8  # part d'un cadre dans un autre pour qu'il y soit tenu inclus


def aire(r: dict) -> float:
    return max(0.0, r["x1"] - r["x0"]) * max(0.0, r["y1"] - r["y0"])


def dans(a: dict, b: dict) -> float:
    """Part de l'aire de `a` comprise dans `b` (un point : 1 ou 0)."""
    if aire(a) == 0:
        x, y = (a["x0"] + a["x1"]) / 2, (a["y0"] + a["y1"]) / 2
        return float(b["x0"] <= x <= b["x1"] and b["y0"] <= y <= b["y1"])
    largeur = min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])
    hauteur = min(a["y1"], b["y1"]) - max(a["y0"], b["y0"])
    if largeur <= 0 or hauteur <= 0:
        return 0.0
    return largeur * hauteur / aire(a)


def identifier(r: dict) -> str:
    """Identifiant stable d'un repérage : sa page, son cadre, son étiquette."""
    cle = "|".join(
        str(v)
        for v in (r["fichier"], r["page"], *(r[k] for k in CHAMPS), r["etiquette"])
    )
    return hashlib.sha1(cle.encode()).hexdigest()[:12]


def fusionner(reperes: list[dict]) -> list[dict]:
    """Un repérage par endroit : sur chaque page, un cadre inclus dans un
    cadre plus grand déjà gardé disparaît (le plus grand cache davantage).
    Chaque repérage gardé reçoit son identifiant."""
    par_page: dict[tuple, list] = {}
    for r in reperes:
        par_page.setdefault((r["fichier"], r["page"]), []).append(r)
    sortie = []
    for cle in sorted(par_page):
        gardes = []
        for r in sorted(par_page[cle], key=aire, reverse=True):
            if not any(dans(r, g) >= INCLUS for g in gardes):
                gardes.append(r)
        sortie += [r | {"id": identifier(r)} for r in gardes]
    return sortie


def est_retabli(r: dict, retablis: list[dict]) -> bool:
    """Rétabli à la relecture : même identifiant, ou cadre presque tout entier
    dans un cadre rétabli de la même page (l'analyse a pu changer depuis).
    Un grand cadre qui contient un petit cadre rétabli reste masqué."""
    return any(
        (t.get("id") == r.get("id") or dans(r, t) >= INCLUS)
        for t in retablis
        if (t["fichier"], t["page"]) == (r["fichier"], r["page"])
    )


def a_masquer(
    reperes: list[dict], retablis: list[dict], notes: list[dict]
) -> list[dict]:
    """Les cadres à masquer : repérages non rétablis, et notes (les oublis)."""
    gardes = [
        r | {"origine": "repérage"} for r in reperes if not est_retabli(r, retablis)
    ]
    return gardes + [
        {k: n[k] for k in ("fichier", "page", *CHAMPS, "etiquette")}
        | {"origine": "relecture"}
        for n in notes
    ]


def mesurer_relecture(
    reperes: list[dict], retablis: list[dict], notes: list[dict], vues: set
) -> tuple[float, float, int] | None:
    """Sur les pages relues : précision (part des repérages non rétablis) et
    rappel (part des données à masquer qu'un repérage couvrait déjà, les
    autres étant les oublis encadrés à la main)."""
    reperes = [r for r in reperes if (r["fichier"], r["page"]) in vues]
    notes = [n for n in notes if (n["fichier"], n["page"]) in vues]
    if not vues or not reperes:
        return None
    justes = [r for r in reperes if not est_retabli(r, retablis)]
    oublis = [
        n
        for n in notes
        if not any(
            (r["fichier"], r["page"]) == (n["fichier"], n["page"])
            and (dans(n, r) >= 0.5 or dans(r, n) >= 0.5)
            for r in justes
        )
    ]
    precision = len(justes) / len(reperes)
    rappel = len(justes) / (len(justes) + len(oublis)) if justes or oublis else 0.0
    return precision, rappel, len(vues)
