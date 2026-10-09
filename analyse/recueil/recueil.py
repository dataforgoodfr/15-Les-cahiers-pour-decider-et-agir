"""Recueil des contributions exportées, pour l'association (issue #21).

Les contributions viennent de `selection` : tirées par `tirage`, délimitées
et caviardées à la main. Tant que les 100 ne sont pas faites, le recueil
n'en montre qu'une partie, qui n'est pas un sous-tirage au hasard : ce sont
les cahiers délimités les premiers. La page de représentativité le dit, en
comparant tailles de communes et régions à la population française.

Ce module prépare les lignes de l'index et le HTML des pages ajoutées ; il
ne lit que des noms de communes, des codes et des comptes.
"""

from collections import Counter
from html import escape

TYPES = ("dactylographiée", "mixte", "manuscrite")


def forme(types: list[str]) -> str:
    """Forme d'une contribution d'après le type de ses pages écrites."""
    ecrites = [t for t in types if t in TYPES]
    if not ecrites:
        return "inconnue"
    if all(t == ecrites[0] for t in ecrites):
        return ecrites[0]
    return "mixte"


def index(selection: list[dict], tirage: dict[str, dict], types: dict) -> list[dict]:
    """Une ligne par contribution exportée, rangée par région, département et
    commune. `types` : type de chaque page, par (fichier, page)."""
    lignes = []
    for s in selection:
        if s["statut"] != "exporté":
            continue
        t = tirage[s["fichier"]]
        debut, fin = int(s["page_debut"]), int(s["page_fin"])
        lignes.append(
            {
                "commune": s["commune"],
                "code_insee": t["code_insee"],
                "departement": s["departement"],
                "region": t["region"],
                "taille": t["taille"],
                "population": int(t["population"]),
                "forme": forme(
                    [types.get((s["fichier"], n), "") for n in range(debut, fin + 1)]
                ),
                "pages": fin - debut + 1,
                "page_debut": debut,
                "page_fin": fin,
                "rang": int(s["rang"]),
                "contributions_du_cahier": int(s["contributions"]),
                "caviardages": int(s["caviardages"]),
                "fichier": s["fichier"],
            }
        )
    lignes.sort(key=lambda x: (x["region"], x["departement"], x["commune"]))
    for n, ligne in enumerate(lignes, 1):
        ligne["numero"] = n
    return [{"numero": x.pop("numero"), **x} for x in lignes]


def comparaison(
    lignes: list[dict], cle: str, habitants: dict[str, int], ordre: list[str]
) -> list[tuple[str, int, float]]:
    """(groupe, contributions du recueil, attendues selon la population)."""
    compte = Counter(x[cle] for x in lignes)
    total = sum(habitants.values())
    return [(g, compte[g], len(lignes) * habitants.get(g, 0) / total) for g in ordre]


def nombre(n: float, decimales: int = 0) -> str:
    texte = f"{n:,.{decimales}f}".replace(",", " ").replace(".", ",")
    return texte


STYLE = """
body { font-family: sans-serif; font-size: 10pt; color: #1d1d1b; }
h1 { font-size: 20pt; margin-bottom: 4pt; }
h2 { font-size: 13pt; margin-top: 14pt; }
p { margin: 4pt 0; line-height: 1.35; }
table { border-collapse: collapse; width: 100%; }
th, td { border-bottom: 1px solid #d9d7d0; padding: 2pt 4pt; text-align: left; }
td.n, th.n { text-align: right; }
.discret { color: #6b6a65; }
"""


def page_de_garde(lignes: list[dict], tires: int, date: str) -> str:
    pages = sum(x["pages"] for x in lignes)
    regions = len({x["region"] for x in lignes})
    return f"""
<h1>Cahiers citoyens du Grand débat national</h1>
<p class="discret">Échantillon provisoire de {len(lignes)} contributions, {date}</p>
<h2>D'où viennent ces contributions</h2>
<p>Les cahiers citoyens ouverts par les communes pendant le Grand débat national
(fin 2018 – début 2019) ont été numérisés par la BnF. Nous avons tiré
{tires} contributions représentatives des habitants de la France entière :
des communes tirées selon leur taille et leur région, puis, dans un cahier de
chaque commune, une contribution prise au hasard.</p>
<p>Ce recueil en présente {len(lignes)}, sur {pages} pages, venant de
{regions} régions : celles dont le cahier est déjà délimité à la main (où
commence et où finit chaque contribution) et caviardé. Les autres suivront.</p>
<h2>Comment lire les pages</h2>
<p>Chaque contribution est précédée d'une page qui indique sa commune et
l'endroit du cahier d'où elle vient. Sur les pages du cahier :</p>
<p>– <b>en gris</b>, ce qui n'appartient pas à la contribution (la fin de la
précédente, le début de la suivante) ;</p>
<p>– <b>en noir</b>, les données personnelles : noms, adresses, signatures,
téléphones, courriels. Dans le doute, elles sont cachées.</p>
<p>Le texte caché a été effacé du document, pas seulement recouvert.</p>
<h2>Limites</h2>
<p>Le tirage n'a porté que sur les cahiers qui ont des pages
dactylographiées, faute de pouvoir encore lire les manuscrits
automatiquement : les cahiers entièrement manuscrits n'y figurent pas. Les {len(lignes)} contributions présentées ne
sont pas un sous-ensemble tiré au hasard des {tires} : la page suivante
compare leur répartition à celle de la population.</p>
"""


def tableau(titre: str, rangs: list[tuple[str, int, float]]) -> str:
    corps = "".join(
        f"<tr><td>{escape(g)}</td><td class='n'>{n}</td>"
        f"<td class='n'>{nombre(a, 1)}</td></tr>"
        for g, n, a in rangs
        if n or a >= 0.05
    )
    return (
        f"<h2>{escape(titre)}</h2><table><tr><th></th><th class='n'>contributions</th>"
        f"<th class='n'>attendues selon la population</th></tr>{corps}</table>"
    )


def page_representativite(tailles, regions) -> str:
    return (
        "<h1>Représentativité</h1>"
        "<p>Nombre de contributions du recueil, et nombre attendu si elles "
        "suivaient la population française (recensement 2017).</p>"
        + tableau("Taille de la commune", tailles)
        + tableau("Région", regions)
    )


def sommaire(lignes: list[dict]) -> str:
    corps = "".join(
        f"<tr><td class='n'>{x['numero']}</td><td>{escape(x['commune'])}</td>"
        f"<td>{escape(x['departement'])}</td><td>{escape(x['region'])}</td>"
        f"<td>{escape(x['forme'])}</td><td class='n'>{x['pages']}</td></tr>"
        for x in lignes
    )
    return (
        "<h1>Sommaire</h1><table><tr><th class='n'>n°</th><th>commune</th>"
        "<th>dép.</th><th>région</th><th>forme</th>"
        f"<th class='n'>pages</th></tr>{corps}</table>"
    )


def page_de_titre(x: dict) -> str:
    pages = (
        f"page {x['page_debut']}"
        if x["page_debut"] == x["page_fin"]
        else f"pages {x['page_debut']} à {x['page_fin']}"
    )
    return f"""
<p class="discret">Contribution {x["numero"]}</p>
<h1>{escape(x["commune"])}</h1>
<p>{escape(x["region"])}, département {escape(x["departement"])}</p>
<p>Commune de {nombre(x["population"])} habitants ({escape(x["taille"])})</p>
<h2>Dans le cahier</h2>
<p>Contribution {x["rang"]} sur {x["contributions_du_cahier"]} du cahier
citoyen de la commune, {pages}. Forme : {escape(x["forme"])}.</p>
"""
