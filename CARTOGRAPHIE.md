# Cartographie « Qui fait quoi en informatique graphique ? »

Page : https://afig-asso.github.io/research-team/

La page présente les équipes de recherche françaises en informatique graphique : un annuaire (repris de
`data.yaml`), puis deux tableaux croisés thèmes × équipes et secteurs d'application × équipes, et une fiche par équipe.
Elle est régénérée automatiquement à chaque modification du dépôt (`.github/workflows/cartographie.yml`).

## Corriger une information

- **Annuaire** (nom, site, correspondant, thèmes de l'équipe) : `data.yaml`, puis `python scripts/generate.py` pour le README.
- **Fiche d'une équipe** (synthèse, expertise, thèmes principaux, secteurs, publications représentatives) :
  `cartographie/fiches/<Labo>_<Equipe>.yaml`. Les identifiants de thèmes et de secteurs sont ceux de
  `cartographie/vocabulaire.json` ; les identifiants de publications sont ceux de `cartographie/donnees/publications/`.
  Pour masquer un thème ou un secteur attribué à tort par le calcul : listes `themes_exclus` et `applications_exclues`.
- Ou par courriel : contact@asso-afig.fr.

Avant de proposer une modification : `python scripts/carto_verifier.py --public` (0 erreur attendue).
Pour voir la page en local : `python scripts/carto_generer.py --public`, puis ouvrir `_site/index.html`.

## Comment les intensités sont calculées

À partir des publications 2011-2026 (HAL, complété par OpenAlex) des permanents de chaque équipe actifs en
informatique graphique. Chaque thème et secteur a une liste de mots-clés (`cartographie/motscles.yaml`) ; une
publication compte 1 si un mot-clé spécifique est dans son titre, de 0,1 à 0,8 s'il n'apparaît que dans le résumé.
L'intensité d'une case est la part (pondérée) des publications de l'équipe sur le thème.

`cartographie/donnees/` contient les résultats de ce calcul (scores, effectifs, titres et liens des publications ;
ni résumés ni liste nominative des membres). Ils sont mis à jour périodiquement par l'AFIG.
