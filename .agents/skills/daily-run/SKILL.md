---
name: daily-run
description: Run du matin en une commande : collecte brute puis sélection et briefing des meilleures offres. Utiliser quand l'utilisateur dit "run du matin", "offres du jour", "cherche les offres".
triggers:
  - /daily-run
  - run du matin
  - offres du jour
  - cherche les offres
---

# Run du matin (seul skill à appeler chaque jour)

Enchaîne `job-collect` → `job-select`, affiche le Top. Les autres skills ne servent qu'au debug ou à l'init.

## 1. Séquence

1. **Collecter** (skill `job-collect`) :
```bash
python3 scripts/fetch_direct.py
python3 scripts/fetch_eures.py --days 1
python3 scripts/fetch_jobspy.py --hours 24
```
Noter les sources KO et continuer avec les disponibles. Ne pas relancer en boucle un site en 403/429.

2. **Sélectionner** (skill `job-select`) : fusion + dédup, filtre dur (stages, exclusions du guide, contrats), score 0-10, écriture de `offres/AAAA-MM-JJ/selection_AAAA-MM-JJ.md` et `offres/AAAA-MM-JJ/briefing_AAAA-MM-JJ.md`.

3. **Présenter** : afficher le Top (score ≥ 6, max 10 offres) + compteurs (`N nouvelles, Rejetées : N, sources KO : ...`). Renvoyer vers `offres/AAAA-MM-JJ/briefing_AAAA-MM-JJ.md` pour le détail.

## 2. Variantes

- Pressé : `fetch_direct.py` seul + sélection (rapide, < 1 min).
- Rattrapage : `--days 3` / `--hours 72` + `--fr-only` si le volume Europe est trop gros.
- Debug : appeler `/job-collect` ou `/job-select` seuls au lieu de tout relancer.
- Bruit/lenteur EURES ou JobSpy : la section `Intitulés portails` du guide doit contenir
  uniquement des intitulés de poste précis (jamais de stack seule type `React`). Sinon,
  renvoyer vers `/profil-builder` pour corriger le guide plutôt que relancer en boucle.

## 3. Règles

- Toujours lancer depuis la racine du dépôt (là où sont `profil/companies.yaml` et `profil/guide_recherche.md`).
- Ne jamais éditer `state_direct.json`, `profil/guide_recherche.md` ou `profil/companies.yaml` pendant le run.
- Ne jamais inventer d'offre : chaque ligne du Top vient d'un CSV du jour avec son lien.
- Durée typique : 5-10 min en full, à lancer une fois le matin (pas de cron : anti-bot JobSpy/WTTJ).
