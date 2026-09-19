---
name: job-select
description: Sélectionne les meilleures offres du jour depuis les CSV bruts et produit le briefing (selection + briefing). Utiliser quand l'utilisateur dit "sélectionne", "fais le briefing", "trie les offres".
triggers:
  - /job-select
  - sélectionne les offres
  - fais le briefing
  - trie les offres
---

# Sélectionner et présenter les meilleures offres

Lit les sorties brutes de `job-collect`, applique `profil/guide_recherche.md`, écrit un seul fichier à lire.

## 1. Entrées à lire

- `offres/AAAA-MM-JJ/offres_direct_*.csv`, `offres_eures_*.csv`, `offres_jobspy_*.csv` (AAAA-MM-JJ = aujourd'hui).
- `profil/guide_recherche.md` : en-tête (Profil / Zone / Contrat / Exclusions) + intitulés métiers + mots-clés.
- `profil/companies.yaml` : colonne `priorite` (`haute` = bonus).

Si un CSV manque (source KO au `job-collect`), travailler avec les disponibles et le signaler en tête du briefing.

## 2. Fusion + dédup

- Concaténer les 3 sources, dédupliquer sur `titre + entreprise + lieu` (insensible à la casse, espaces normalisés).
- Garder pour chaque offre : titre, entreprise, lieu, contrat, url_offre, source (direct/eures/jobspy).

## 3. Filtre dur (éliminatoire, 100% piloté par le guide)

Principe : aucune liste en dur dans ce skill. Tout vient des lignes `Contrat:` et `Exclusions:` de `profil/guide_recherche.md`, lues à chaque run.

1. **Contrats refusés** : extraire de la ligne `Contrat:` les types refusés (formulations type `Pas de X`, `hors X`, `pas de X` — ex : `Pas de stage` → stage, internship, alternance, apprentissage). Toute offre dont le titre ou le champ contrat matche un type refusé → rejetée.
2. **Exclusions métier** : découper la ligne `Exclusions:` sur les virgules (en ignorant les placeholders `[À personnaliser...]` vides). Chaque terme restant → rejeté si présent (match insensible à la casse, racine du mot) dans titre ou description.
3. **Contrats acceptés** : extraire de la ligne `Contrat:` les types acceptés (ex : `CDI ou CDD` → CDI, CDD + variantes CDDU/CDD-CDI). Si le champ contrat de l'offre est renseigné et ne matche aucun type accepté → rejetée. Si non renseigné, garder (bénéfice du doute).
4. Si les lignes `Contrat:` / `Exclusions:` sont vides ou encore placeholders `[...]`, ne rien filtrer sur ce critère et le signaler en tête du briefing (`Filtre contrat : non configuré`).

Compter les rejetés par règle pour le rapport final (`Rejetées : N (contrat refusé: x, exclusion: y, contrat hors liste: z)`).

## 4. Score 0-10 (expliquable, pas de LLM)

- +3 : un intitulé ou mot-clé du guide dans le titre.
- +2 : entreprise `priorite: haute` dans `profil/companies.yaml`, ou source `direct`.
- +2 : lieu compatible avec la ligne `Zone:` du guide (parsée à chaque run, ex : villes/pays cités ; placeholder `[...]` = pas de bonus, pas de malus).
- +1 : contrat = premier type accepté de la ligne `Contrat:` du guide (ex : si `CDI ou CDD`, bonus pour CDI).
- +1 : publiée depuis < 48h.
- Plafond 10. Seuil : `≥6` = Top à lire, `3-5` = Autres, `<3` = ignorées (comptées seulement).

## 5. Sorties (seules écritures autorisées)

- `offres/AAAA-MM-JJ/selection_AAAA-MM-JJ.md` : offres retenues, format par offre :
  `titre, entreprise, lieu, contrat, source/lien, 1-2 lignes pourquoi elle correspond`.
- `offres/AAAA-MM-JJ/briefing_AAAA-MM-JJ.md` : fichier unique à lire, structure :
```md
# Briefing du AAAA-MM-JJ
N nouvelles (X direct, Y eures, Z jobspy) — Rejetées : N

## Top à lire (score ≥ 6)
## {titre} — {entreprise} ({score}/10)
- Lieu : ... | Contrat : ...
- Lien : ...
- Pourquoi : <mots-clés matchés + source>

## Autres (3-5)
...

## Rejetées : N (rappel règles)
```

## 6. Vérifier

- Chaque offre du Top a un lien valide et une ligne "Pourquoi" traçable (mot-clé ou priorité, pas d'invention).
- Relance le lendemain sans doublon : la dédup fusion + `state_direct.json` (côté direct) l'assurent.
- Ne toucher ni à `scripts/`, ni à `state_direct.json`, ni au `profil/guide_recherche.md`.
