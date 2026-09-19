# Recherche d'emploi — agent quotidien

Chaque matin, l'agent collecte les offres (sites d'entreprises, EURES,
Indeed/LinkedIn/Google), les sélectionne selon votre profil, et vous présente
un seul briefing à lire.

Tout passe par l'agent et ses skills — aucune commande à retenir.

## Installation

1. **Clonez le dépôt**, puis placez-vous dedans :
   ```bash
   git clone https://github.com/hboisgibault/recherche-emploi.git
   cd recherche-emploi
   ```
2. **Lancez votre agent (OpenCode, Claude Code...) depuis ce dossier** —
   c'est important : les skills, les scripts et le profil sont lus
   en chemins relatifs (`profil/`, `scripts/`, `offres/`).
3. Installez les dépendances (Python 3.10+ requis) :
   ```bash
   pip install -r requirements.txt
   ```

Cela installe `requests`, `beautifulsoup4` et `pyyaml` (collecte sites directs),
plus `pandas` et `python-jobspy` (collecte Indeed/LinkedIn/Google).
Sans ces dépendances, l'agent vous dira ce qui manque et comment l'installer.

## Démarrage (première fois)

1. **Déposez d'abord votre CV** dans `profil/` : `profil/cv.pdf` ou `profil/cv.md`.
   Sans lui, l'agent ne connaît ni vos compétences ni votre parcours.
2. Demandez ensuite à l'agent : **« crée mon profil »** (skill `/profil-builder`).
   Il lit votre CV, vous pose 6 questions max et remplit `profil/` :
- `profil/guide_recherche.md` — métiers, zone, contrats, exclusions, mots-clés.
  Tout le filtrage et la recherche en découlent, sans toucher au code.
- `profil/companies.yaml` — entreprises à surveiller en direct.
- `profil/cv.pdf` (optionnel) — votre CV, déposez-le, l'agent le lit.

## Chaque matin

Demandez à l'agent : **« offres du jour »** (skill `/daily-run`).
Il collecte, sélectionne et affiche le Top des offres avec, pour chacune,
le lien et 1-2 lignes expliquant pourquoi elle correspond à votre profil.
Le détail est dans `offres/AAAA-MM-JJ/briefing_AAAA-MM-JJ.md`.

## Les skills

| Skill | Quand l'appeler |
|---|---|
| `/daily-run` | le run du matin (collecte + sélection + Top) — le seul au quotidien |
| `/job-collect` | collecte brute seule (debug une source en échec) |
| `/job-select` | sélection seule sur les CSV déjà collectés |
| `/profil-builder` | créer ou mettre à jour le profil |

Voir `.agents/skills/` pour le détail de chacun.

## Structure

```
profil/                  ← VOS ENTRÉES (les seuls fichiers à éditer)
  guide_recherche.md       métiers, zone, contrats, exclusions, mots-clés
  companies.yaml           sites d'entreprises à surveiller
  cv.pdf                   votre CV (optionnel)
scripts/                 ← exécutés par l'agent (génériques, pilotés par le guide)
  guide_rules.py           parse Contrat/Exclusions/mots-clés du guide
  fetch_direct.py          sites de companies.yaml (+ hash diff via state_direct.json)
  fetch_eures.py           API publique EURES (mots-clés du guide)
  fetch_jobspy.py          Indeed/LinkedIn/Google (termes du guide)
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
