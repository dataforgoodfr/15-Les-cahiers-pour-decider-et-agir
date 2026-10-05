"""Notes posées sur les pages des cahiers, statut et qualification des pages.

Le carnet est un journal JSONL, en ajout seul : chaque ligne est un
événement (note, modification, suppression, statut, qualification). On rejoue le journal
pour connaître l'état courant ; rien n'est jamais réécrit, donc une coupure
au milieu d'une écriture ne perd que la dernière ligne.

Une note porte une position en points PDF, dans le repère de la page telle
qu'elle sort du PDF (rotation du PDF comprise, rotation de l'affichage
non) : un point (x0 = x1, y0 = y1) ou un rectangle. Son texte est libre et
peut citer le cahier : il reste local, et `positions()` est la seule vue des
notes à partager.

Un rétablissement lève le masque d'un repérage d'une liste à masquer
(`annotation.listes`) : le relecteur juge que ce n'est pas une donnée
personnelle. Il garde l'identifiant et le cadre du repérage, pour s'appliquer
encore si l'analyse change ses identifiants.

Une qualification porte sur toute la page (ou, page 0, sur le cahier) : un
problème tranché à la main (page tournée, illisible…), le type de page
vérifié, qui corrige ou confirme le typage, ou une remarque libre.
"""

import json
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

STATUTS = ("vue", "a_revoir")
CHAMPS_NOTE = ("fichier", "page", "x0", "y0", "x1", "y1", "etiquette", "texte")
CHAMPS_MODIFIABLES = ("x0", "y0", "x1", "y1", "etiquette", "texte")
PROBLEMES = (
    "page tournée",
    "ordre des pages",
    "page manquante",
    "illisible",
    "coupée",
    "doublon",
)
TYPES = ("dactylographiée", "manuscrite", "mixte", "vierge")


class Carnet:
    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.verrou = threading.Lock()

    def evenements(self) -> list[dict]:
        if not self.chemin.exists():
            return []
        with self.chemin.open(encoding="utf-8") as f:
            return [json.loads(ligne) for ligne in f if ligne.strip()]

    def _ecrire(self, evenement: dict) -> dict:
        evenement["cree"] = datetime.now(UTC).isoformat(timespec="seconds")
        with self.verrou:
            self.chemin.parent.mkdir(parents=True, exist_ok=True)
            with self.chemin.open("a", encoding="utf-8") as f:
                f.write(json.dumps(evenement, ensure_ascii=False) + "\n")
        return evenement

    def noter(self, note: dict) -> dict:
        evenement = {k: note[k] for k in CHAMPS_NOTE if k in note}
        evenement["page"] = int(evenement["page"])
        for k in ("x0", "y0", "x1", "y1"):
            evenement[k] = round(float(evenement[k]), 1)
        return self._ecrire({"type": "note", "id": uuid.uuid4().hex, **evenement})

    def modifier(self, ident: str, champs: dict) -> dict:
        changes = {k: champs[k] for k in CHAMPS_MODIFIABLES if k in champs}
        for k in ("x0", "y0", "x1", "y1"):
            if k in changes:
                changes[k] = round(float(changes[k]), 1)
        return self._ecrire({"type": "modification", "id": ident, **changes})

    def supprimer(self, ident: str) -> dict:
        return self._ecrire({"type": "suppression", "id": ident})

    def marquer(
        self, fichier: str, page: int, statut: str | None, tache: str | None = None
    ) -> dict:
        """Statut d'une page pour une tâche (« contributions »,
        « anonymisation »…), ou pour toutes si `tache` est None."""
        if statut not in (*STATUTS, None):
            raise ValueError(f"statut inconnu : {statut}")
        return self._ecrire(
            {
                "type": "statut",
                "fichier": fichier,
                "page": int(page),
                "statut": statut,
                "tache": tache,
            }
        )

    def statuts(
        self, tache: str | None = None, exacte: bool = False
    ) -> dict[tuple[str, int], str]:
        """Statut de chaque page pour une tâche : le dernier posé pour elle ou
        pour toutes (pour elle seule si `exacte`). Sans tâche, le dernier
        posé, quelle qu'en soit la tâche."""
        statuts = {}
        acceptees = (tache,) if exacte else (None, tache)
        for e in self.evenements():
            if e["type"] != "statut":
                continue
            if tache is not None and e.get("tache") not in acceptees:
                continue
            cle = (e["fichier"], e["page"])
            if e["statut"]:
                statuts[cle] = e["statut"]
            else:
                statuts.pop(cle, None)
        return statuts

    def retablir(
        self, fichier: str, page: int, marque: dict, retabli: bool = True
    ) -> dict:
        """Lève (ou remet) le masque d'un repérage d'une liste à masquer."""
        return self._ecrire(
            {
                "type": "retablissement",
                "fichier": fichier,
                "page": int(page),
                "marque": str(marque["id"]),
                **{k: round(float(marque[k]), 1) for k in ("x0", "y0", "x1", "y1")},
                "etiquette": marque.get("etiquette"),
                "retabli": bool(retabli),
            }
        )

    def retablis(self) -> dict[tuple[str, int, str], dict]:
        """Repérages rétablis, par (fichier, page, identifiant) : leur cadre
        et leur étiquette."""
        sortie = {}
        for e in self.evenements():
            if e["type"] != "retablissement":
                continue
            cle = (e["fichier"], e["page"], e["marque"])
            if e["retabli"]:
                sortie[cle] = {
                    k: e[k] for k in ("fichier", "page", "x0", "y0", "x1", "y1")
                } | {"id": e["marque"], "etiquette": e["etiquette"]}
            else:
                sortie.pop(cle, None)
        return sortie

    def qualifier(self, fichier: str, page: int, champ: str, valeur) -> dict:
        """Qualifie une page (page 0 : le cahier entier).

        Un problème prend une valeur booléenne : décocher un problème détecté
        par une analyse est une information, on la garde. Le type vérifié
        prend une valeur de TYPES (None l'efface), la remarque un texte libre.
        """
        if champ in PROBLEMES:
            valeur = bool(valeur)
        elif champ == "remarque":
            valeur = str(valeur or "")
        elif champ != "type" or valeur not in (*TYPES, None):
            raise ValueError(f"qualification inconnue : {champ} = {valeur}")
        return self._ecrire(
            {
                "type": "qualification",
                "fichier": fichier,
                "page": int(page),
                "champ": champ,
                "valeur": valeur,
            }
        )

    def qualifications(self, remarques: bool = True) -> dict[tuple[str, int], dict]:
        """Par page : problèmes tranchés à la main ({nom: bool}), type vérifié
        et remarque. Une analyse passe `remarques=False` : la remarque est un
        texte libre qui peut citer le cahier."""
        pages: dict[tuple[str, int], dict] = {}
        for e in self.evenements():
            if e["type"] != "qualification":
                continue
            page = pages.setdefault(
                (e["fichier"], e["page"]),
                {"problemes": {}, "type": None, "remarque": ""},
            )
            if e["champ"] in ("type", "remarque"):
                page[e["champ"]] = e["valeur"]
            else:
                page["problemes"][e["champ"]] = e["valeur"]
        if not remarques:
            for page in pages.values():
                page.pop("remarque")
        return pages

    def etat(self) -> tuple[dict[str, dict], dict[tuple[str, int], str]]:
        """Notes vivantes par identifiant, et statut de chaque page."""
        notes, statuts = {}, {}
        for e in self.evenements():
            if e["type"] == "note":
                notes[e["id"]] = {k: v for k, v in e.items() if k != "type"}
            elif e["type"] == "modification" and e["id"] in notes:
                notes[e["id"]].update(
                    {k: v for k, v in e.items() if k in CHAMPS_MODIFIABLES}
                )
            elif e["type"] == "suppression":
                notes.pop(e["id"], None)
            elif e["type"] == "statut":
                cle = (e["fichier"], e["page"])
                if e["statut"]:
                    statuts[cle] = e["statut"]
                else:
                    statuts.pop(cle, None)
        return notes, statuts

    def positions(self) -> list[dict]:
        """Les notes sans leur texte : ce qu'on peut lire sans voir le cahier."""
        notes, _ = self.etat()
        return [
            {
                k: n[k]
                for k in ("id", "fichier", "page", "x0", "y0", "x1", "y1", "etiquette")
            }
            for n in notes.values()
        ]
