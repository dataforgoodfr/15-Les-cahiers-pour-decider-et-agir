import argparse

import instructor
from openai import OpenAI
from openai.types.chat import (
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)
from pydantic import BaseModel, Field


# 1. Structure "plate" beaucoup plus digeste pour un modèle local
class SegmentTexte(BaseModel):
    extrait_exact: str = Field(
        description="Le sous-texte exact et complet, mot pour mot."
    )
    theme: str = Field(
        description="Le grand thème (doit faire partie de la liste autorisée)."
    )
    sous_theme: str = Field(
        description="Le sous-thème (doit correspondre au thème choisi)."
    )
    justification: str = Field(
        description="Courte justification de ce choix."
    )

class AnalyseTexte(BaseModel):
    segments: list[SegmentTexte] = Field(
        description="Liste des idées extraites du texte."
    )

# 2. La taxonomie passée directement dans le texte du prompt
TAXONOMIE = """
Voici la liste STRICTE des thèmes et sous-thèmes autorisés :
1. Démocratie et citoyenneté (Démocratie participative, Droits et libertés, 
Élections et représentation, Mandat et statut des élus, Réforme des 
institutions, Transparence de l'information)
2. Transition écologique (Agriculture, Consommation, Éducation, Énergie, 
Fiscalité et réglementation, Protection de l'environnement, Transports)
3. Fiscalité et dépenses publiques (Équilibre des finances, Justice fiscale, 
Réduction des impôts, Simplification fiscale)
4. Organisation de l'État (Aménagement du territoire, Fonction publique, 
Organisation des collectivités, Sécurité intérieure, Simplification)
5. Économie et emploi (Banques et finance, Compétitivité, Économie 
responsable, Mondialisation, Partage de la valeur, Rôle de l'État, Travail)
6. Pouvoir d’achat (Augmentation des revenus, Coût de la vie)
7. Éducation et formation (Budget, Corps enseignant, Égalité, Formation)
8. Santé et solidarité (Intégration, Lien social, Protection sociale)
"""

if __name__ == "__main__":
    # Configuration de l'analyseur d'arguments en ligne de commande
    parser = argparse.ArgumentParser(
        description="Analyse un texte brut et extrait ses grandes idées."
    )
    parser.add_argument(
        "texte",
        type=str,
        help="Le texte brut à analyser (entre guillemets)."
    )
    
    # Récupération de l'argument passé par l'utilisateur
    args = parser.parse_args()
    texte_brut = args.texte

    # Connexion à Ollama
    client = instructor.from_openai(
        OpenAI(
            base_url="http://localhost:11434/v1",
            api_key="ollama",
        ),
        mode=instructor.Mode.JSON,
    )

    system_prompt = (
        "Sépare le texte fourni en grandes idées. Pour chaque idée, extrais "
        "le texte verbatim. Assigne le 'theme' et le 'sous_theme' en "
        f"choisissant UNIQUEMENT dans cette liste :\n{TAXONOMIE}\n"
        "Réponds uniquement au format JSON."
    )

    # Appel au modèle Mistral
    analyse = client.chat.completions.create(
        model="mistral",
        response_model=AnalyseTexte,
        messages=[
            ChatCompletionSystemMessageParam(
                role="system",
                content=system_prompt,
            ),
            ChatCompletionUserMessageParam(
                role="user",
                content=texte_brut,
            ),
        ],
        temperature=0.0,
    )

    # Affichage des résultats
    for i, segment in enumerate(analyse.segments, 1):
        print(f"--- Idée {i} ---")
        print(f"Texte      : {segment.extrait_exact}")
        print(f"Thème      : {segment.theme}")
        print(f"Sous-thème : {segment.sous_theme}")
        print(f"Raison     : {segment.justification}\n")