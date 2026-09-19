---
name: job-collect
description: Collecte brute des offres du jour via les 3 scripts (sites directs + EURES + JobSpy). Utiliser quand l'utilisateur dit "collecte du jour", "lance les fetch", "run collecte".
triggers:
  - /job-collect
  - collecte du jour
  - lance les fetch
  - run collecte
---

# Collecter les offres brutes du jour

Ne fait que collecter. Ni filtre métier, ni sélection : c'est le skill `job-select` qui s'en charge.

## 1. Commandes (depuis la racine, dans l'ordre)

```bash
python3 scripts/fetch_direct.py
python3 scripts/fetch_eures.py --days 1
python3 scripts/fetch_jobspy.py --hours 24
```

Attendre la fin de chaque script. En cas d'échec d'un script, noter l'erreur et continuer avec les sorties disponibles.

Périmètre géo : les pays EURES et le lieu JobSpy sont dérivés de la ligne `Zone:` du guide
(repli : Europe de l'Ouest / Paris si ligne absente). Forçage ponctuel possible :
`--countries fr be` (eures), `--location "Lyon, France" --country France` (jobspy).

Variantes :
- Debug ciblé : `python3 scripts/fetch_direct.py --only "Palais,le19M" --limit 5`
- Rattrapage week-end : `--days 3` (eures) / `--hours 72` (jobspy)
- France seule : `fetch_jobspy.py --hours 24 --fr-only`
- Bruit/lenteur EURES ou JobSpy : vérifier que la section `Intitulés portails` du guide
  ne contient que des intitulés de poste précis (jamais de stack seule type `React`,
  `Ruby on Rails`, `Python`). En debug, forcer des intitulés resserrés :
  `fetch_eures.py --countries fr --keywords "Lead Developer Fullstack"`
  / `fetch_jobspy.py --keywords "Lead Developer Fullstack" --max-terms 4 --results 10 --sites indeed`.

## 2. Sorties attendues

Dossier du jour `offres/AAAA-MM-JJ/` (créé automatiquement) :
- `offres_direct_AAAA-MM-JJ.csv` / `.md` (nouvelles offres uniquement, dédup via `state_direct.json`)
- `offres_eures_AAAA-MM-JJ.csv` / `.md`
- `offres_jobspy_AAAA-MM-JJ.csv` / `.md`

Si un couple CSV/MD manque, signaler quelle source a échoué au lieu d'inventer des offres.

## 3. Erreurs fréquentes

| Symptôme | Cause probable | Action |
|---|---|---|
| `403` Welcome to the Jungle / ATS | anti-bot | passer par JobSpy ou visite manuelle, ne pas insister en boucle |
| `429` EURES | trop de requêtes | pause 1s déjà dans le script, relancer plus tard |
| `python-jobspy non installé` | dépendance manquante | `pip install -U python-jobspy` |
| `requests / bs4 / yaml manquant` | dépendance manquante | `pip install requests beautifulsoup4 pyyaml` |
| `profil/companies.yaml introuvable` | mauvais dossier | lancer depuis la racine du dépôt |

## 4. Vérifier

- `ls offres/$(date +%F)/` contient les 3 paires CSV/MD (ou le rapport d'échec explicite).
- Ne jamais éditer `state_direct.json` à la main, ne jamais modifier `profil/guide_recherche.md` ici.
