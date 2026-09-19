# Recherche d'emploi — agent quotidien

Chaque matin : collecte des offres (sites d'entreprises, EURES, Indeed/LinkedIn/Google),
sélection selon votre profil, un seul briefing à lire.

## Démarrage (première fois)

1. Remplissez votre profil dans `profil/` :
   - `profil/guide_recherche.md` — métiers, zone, contrats, exclusions, mots-clés.
     Tout le filtrage et la recherche en découlent, sans toucher au code.
   - `profil/companies.yaml` — entreprises à surveiller en direct (une entrée = un site).
   - `profil/cv.pdf` (optionnel) — votre CV, lu par le skill `profil-builder`.
2. Installez les dépendances :
   ```bash
   pip install requests beautifulsoup4 pyyaml pandas python-jobspy
   ```

Avec un agent : `/profil-builder` fait l'étape 1 avec vous.

## Run du matin

```bash
python3 scripts/fetch_direct.py
python3 scripts/fetch_eures.py --days 1
python3 scripts/fetch_jobspy.py --hours 24
```

Puis sélection → `offres/AAAA-MM-JJ/briefing_AAAA-MM-JJ.md` (le seul fichier à lire :
Top à lire + Autres + compteurs de rejet).

Avec un agent : `/daily-run` enchaîne collecte + sélection et affiche le Top.
Autres skills : `/job-collect` (collecte seule), `/job-select` (sélection seule).
Voir `.agents/skills/`.

En cas d'échec d'une source (403 anti-bot, 429, ATS bloqué), notez l'erreur et
continuez avec les sorties disponibles — ne relancez pas en boucle.

## Structure

```
profil/                  ← VOS ENTRÉES (les seuls fichiers à éditer)
  guide_recherche.md       métiers, zone, contrats, exclusions, mots-clés
  companies.yaml           sites d'entreprises à surveiller
  cv.pdf                   votre CV (optionnel)
scripts/                 ← le code (générique, piloté par le guide)
  guide_rules.py           parse Contrat/Exclusions/mots-clés du guide
  fetch_direct.py          sites de companies.yaml (+ hash diff via state_direct.json)
  fetch_eures.py           API publique EURES (mots-clés du guide, --keywords pour forcer)
  fetch_jobspy.py          Indeed/LinkedIn/Google (termes du guide, --location/--country)
offres/AAAA-MM-JJ/       ← sorties du jour (CSV bruts + selection_* + briefing_*)
state_direct.json        ← état runtime (offres vues, hash pages). Ne pas éditer.
.agents/skills/          ← profil-builder, job-collect, job-select, daily-run
```

## Comment marche le filtrage

Zéro critère en dur : `scripts/guide_rules.py` lit à chaque run les lignes
`Contrat:` (acceptés + `Pas de / hors / sauf X`) et `Exclusions:` du guide.
Guide vide ou placeholders → aucun filtre + mention `filtre guide : non configuré`.
La sélection (`job-select`) ajoute un score 0-10 expliquable (mot-clé titre,
priorité entreprise, zone, contrat, fraîcheur).
