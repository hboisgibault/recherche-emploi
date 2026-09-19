# Profil

Toutes les entrées utilisateur vivent ici. Changer de profil = éditer ces fichiers, sans toucher au code.

- `cv.pdf` ou `cv.md` : votre CV (informatif, lu par `profil-builder`).
- `guide_recherche.md` : LA référence — en-tête `Profil / Zone / Contrat / Exclusions`, familles métier, mots-clés. Lu à chaque run par `scripts/guide_rules.py` (filtres + termes de recherche).
- `companies.yaml` : cibles directes (sites entreprises/ateliers). Champs minimaux : `nom, lieu, url_site, priorite`.