# Découpage des contributions (#5)

```bash
uv run python -m contributions
```

Repère où commencent les contributions des cahiers tirés pour l'association
(#21), par des règles décrites dans `regles.py` : courriels imprimés et
formulaires à gabarit répété. Les autres cahiers restent à découper, par une
méthode encore à décider.

L'en-tête d'un formulaire se reconnaît à l'OCR près (75 % de caractères
communs) ; quand il est méconnaissable, deux autres lignes de la première
page du formulaire suffisent. Ces débuts trouvés « à l'OCR près » ont leur
propre liste à revoir. Sur les deux cahiers parisiens tirés (lus en entier),
la règle trouve 89 formulaires sur 89 et 93 sur 93, sans début en trop.
La règle des courriels n'est pas encore mesurée : il manque des pages
annotées.

## Définition

Une contribution est un texte d'un même auteur, ou d'un même groupe, d'un
seul tenant. Une liste de propositions numérotées par une même personne
compte pour une contribution ; un compte rendu de réunion collective aussi.

## Annoter la référence

Pour mesurer les règles, il faut une référence faite à la main sur les 100
cahiers du tirage. Les lecteurs comptent déjà leurs contributions pour
choisir la leur : il suffit de noter en plus où chacune commence.

1. Lancer `uv run python -m contributions` : il écrit les listes
   « Courriels repérés » et « Formulaires (gabarits) repérés » pour l'outil
   d'annotation.
2. Lancer `uv run python -m annotation` et choisir une liste. Les marques
   orange sont les débuts trouvés par la règle.
3. Sur chaque page, poser une note « début de contribution » à chaque vrai
   début (un clic au début de sa première ligne), puis marquer la page vue
   (`v` passe à la suivante). Une page sans début se marque vue sans note.
4. Relancer `uv run python -m contributions` : il affiche la précision (part
   des débuts trouvés qui sont justes) et le rappel (part des vrais débuts
   trouvés) sur les pages vues. Un début trouvé est juste s'il tombe à moins
   de 30 points (environ deux lignes) d'une note.
