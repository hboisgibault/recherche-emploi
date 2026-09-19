---
name: profil-builder
description: Crée ou met à jour le profil de recherche d'emploi (profil/guide_recherche.md + amorce profil/companies.yaml) depuis le CV et 5 réponses utilisateur. Utiliser quand l'utilisateur dit "crée mon profil", "init profil", ou dépose un CV.
triggers:
  - /profil-builder
  - crée mon profil
  - init profil
  - nouveau profil recherche
---

# Builder le profil de recherche

Une seule exécution par utilisateur. Le profil change rarement, le run du matin le lit sans le modifier.

## 1. Collecter les entrées (6 questions max)

1. CV : lire `profil/cv.pdf` ou `profil/cv.md` (voir `profil/README.md`). Si absent, demander de le déposer.
2. Métiers visés (liste libre, ex : soudeur, comptable, designer objet).
3. Zones acceptées (ex : Paris, Île-de-France + remote). Cette ligne pilote le périmètre
   de recherche : pays EURES + lieu JobSpy. La formuler en lieux séparés par virgules
   (`Paris, Lyon + remote`) ; ajouter `remote` si accepté. Pas de filtre dur sur le lieu
   en sortie (formats sources trop hétérogènes) — la Zone cadre les requêtes, et le
   bonus lieu du scoring (`job-select`) fait le reste.
4. Contrats acceptés (ex : CDI/CDD uniquement, pas de stage).
5. Exclusions (ex : peinture, plomberie, téléprospection).
6. Optionnel : 5-10 entreprises cibles connues.

Ne pas poser plus de questions. Proposer des valeurs par défaut tirées du CV.

## 2. Écrire `profil/guide_recherche.md` (template fixe)

```md
# Guide recherche d'emploi
Profil : ...
Zone : ...
Contrat : CDI ou CDD. Pas de stage.
Salaire : ...
Télétravail : ...
Exclusions : ...

## 1. <Famille métier 1>
- <intitulé exact 1>
## 2. <Famille métier 2>
...
### Intitulés portails (recherche EURES/JobSpy) :
`<intitulé 1>`, `<intitulé 2>`, ...
### Compétences (jamais cherchées) :
`<stack/outil 1>`, `<stack/outil 2>`, ...
```

Règles : intitulés courts et cherchables (pas de phrases). Chaque famille = 5-10 intitulés.
Les Intitulés portails sont les SEULS termes envoyés en recherche (EURES + JobSpy) : 5-8 max,
que des intitulés de poste précis et discriminants, cherchables tels quels
(ex : `Lead Developer Fullstack`, `Développeur Backend Python`).
INTERDIT en recherche : termes de stack/outils seuls (`React`, `Ruby on Rails`, `Python`, `Heroku`...) —
sauf inclus dans un intitulé complet. Un terme large = bruit + lenteur (ex : `React` seul
ramène des milliers d'offres hors sujet sur EURES et JobSpy).
Les Compétences listent la stack/outils pour la sélection et le scoring uniquement, jamais pour la recherche.

## 3. Amorcer `profil/companies.yaml` (sans écraser l'existant)

- Si `profil/companies.yaml` existe déjà : ajouter uniquement les nouvelles entreprises citées, jamais de suppression.
- Nouvelle entrée minimale :
```yaml
- nom: <Nom>
  secteur: <secteur libre>
  lieu: <Ville>
  type: page_recruit
  statut: a_verifier
  url_site: <URL ou vide>
  notes: "À vérifier au 1er run."
  priorite: moyenne
```
- Ne jamais inventer d'URL. Si inconnue, laisser vide + `statut: a_verifier`.
- Types valides : `page_recruit | sans_page | ats_externe | job_board_niche`.

## 4. Vérifier

- `profil/guide_recherche.md` relisible en 30 secondes (en-tête + mots-clés).
- `profil/companies.yaml` chargeable : `python3 -c "import yaml; yaml.safe_load(open('profil/companies.yaml'))"`.
- Ne toucher ni à `scripts/`, ni à `offres/`, ni à `state_direct.json`.
