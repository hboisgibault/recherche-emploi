#!/usr/bin/env python3
"""Récupère les offres du jour via JobSpy (Indeed + LinkedIn + Google).

Termes de recherche et filtre lus depuis le profil (`profil/guide_recherche.md`) :
changez de profil = éditez le guide, sans toucher au code.

Usage :
    python3 scripts/fetch_jobspy.py [--hours 24] [--results 20] [--fr-only] [--out-dir .]
    python3 scripts/fetch_jobspy.py --hours 72 --results 30 --sites indeed linkedin
    python3 scripts/fetch_jobspy.py --location "Lyon, France" --max-terms 8

Sorties : offres/AAAA-MM-JJ/offres_jobspy_AAAA-MM-JJ.csv + .md
(dossier créé automatiquement).
"""

import argparse
import csv
import re
import sys
from datetime import date
from pathlib import Path

try:
    from jobspy import scrape_jobs
except ImportError:
    print("ERREUR : python-jobspy non installé. Lance : pip install -U python-jobspy", file=sys.stderr)
    sys.exit(1)

import pandas as pd

try:
    from guide_rules import is_excluded as guide_is_excluded, load_guide
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from guide_rules import is_excluded as guide_is_excluded, load_guide

# Termes de recherche : lus depuis le guide (voir main). Pas de liste en dur ici.

# Lieux de repli par défaut pour les requêtes dérivées du guide.
# (voir --location / --country pour forcer).

def is_excluded(title: str, description: str, job_type: str, rules=None) -> bool:
    """Filtre du guide (Contrat/Exclusions). Guide non configuré = rien filtré."""
    if rules is None:
        return False
    rejected, _ = guide_is_excluded(title, description, job_type, rules)
    return rejected


def run_searches(searches, sites, results_wanted: int, hours_old: int, verbose: int,
                 fetch_descriptions: bool = False) -> pd.DataFrame:
    frames = []
    for term, location, country in searches:
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=term,
                location=location,
                country_indeed=country,
                results_wanted=results_wanted,
                hours_old=hours_old,
                verbose=verbose,
                linkedin_fetch_description=fetch_descriptions,
            )
        except Exception as e:
            print(f"! échec '{term}' à {location} : {e}", file=sys.stderr)
            continue
        if df is None or df.empty:
            continue
        df["query"] = term
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def desc_excerpt(v, limit: int) -> str:
    """Extrait une ligne de description (colonne pandas possiblement NaN)."""
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    s = re.sub(r"\s+", " ", str(v).strip())
    if not s or s.lower() == "nan":
        return ""
    return s[:limit] + ("…" if len(s) > limit else "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Offres du jour via JobSpy")
    ap.add_argument("--hours", type=int, default=24, help="ancienneté max en heures (défaut: 24)")
    ap.add_argument("--results", type=int, default=20, help="résultats par requête et par site (défaut: 20)")
    ap.add_argument("--sites", nargs="+", default=["indeed", "linkedin", "google"],
                    help="sites JobSpy (défaut: indeed linkedin google)")
    ap.add_argument("--fr-only", action="store_true", help="sans effet conservé pour compatibilité")
    ap.add_argument("--location", default="Paris, France", help="lieu des requêtes dérivées du guide")
    ap.add_argument("--country", default="France", help="pays Indeed des requêtes dérivées du guide")
    ap.add_argument("--max-terms", type=int, default=12, help="nb max de termes du guide utilisés (défaut: 12)")
    ap.add_argument("--guide", default=None, help="chemin du guide_recherche.md (défaut: profil/guide_recherche.md)")
    ap.add_argument("--keywords", nargs="*", default=None, help="termes de recherche (défaut: ceux du guide)")
    ap.add_argument("--fetch-descriptions", action="store_true",
                    help="récupère aussi la description complète LinkedIn (lent : +1 requête/offre)")
    ap.add_argument("--desc-limit", type=int, default=600,
                    help="longueur max de l'extrait description dans le .md (défaut: 600)")
    ap.add_argument("--out-dir", default="offres", help="dossier de sortie (défaut: offres)")
    ap.add_argument("--verbose", type=int, default=0)
    args = ap.parse_args()

    rules = load_guide(args.guide)
    print(f"# {rules.describe()}")
    terms = args.keywords or rules.keywords
    if not terms:
        print("ERREUR : aucun terme de recherche.", file=sys.stderr)
        print("Renseignez les intitulés dans profil/guide_recherche.md ou passez --keywords.", file=sys.stderr)
        return 2
    searches = [(t, args.location, args.country) for t in terms[: args.max_terms]]

    print(f"{len(searches)} requêtes x {args.sites} (dernières {args.hours}h)...")
    df = run_searches(searches, args.sites, args.results, args.hours, args.verbose,
                      args.fetch_descriptions)
    if df.empty:
        print("Aucune offre trouvée.")
        return 0

    # Déduplique titre + entreprise + lieu
    for col in ["title", "company", "location"]:
        if col not in df.columns:
            df[col] = ""
    df = df.drop_duplicates(subset=["title", "company", "location"])

    # Filtre du guide (Contrat/Exclusions).
    mask = df.apply(
        lambda r: not is_excluded(
            str(r.get("title", "")),
            str(r.get("description", "")),
            str(r.get("job_type", "")),
            rules,
        ),
        axis=1,
    )
    df = df[mask]

    if "date_posted" in df.columns:
        df = df.sort_values(by="date_posted", ascending=False)  # type: ignore[call-overload]

    today = date.today().isoformat()
    out_dir = Path(args.out_dir)
    dated_dir = out_dir / today
    out_dir.mkdir(parents=True, exist_ok=True)
    dated_dir.mkdir(parents=True, exist_ok=True)
    csv_path = dated_dir / f"offres_jobspy_{today}.csv"
    md_path = dated_dir / f"offres_jobspy_{today}.md"
    df.to_csv(csv_path, quoting=csv.QUOTE_NONNUMERIC, index=False)

    lines = [f"# Offres JobSpy du {today}", f"{len(df)} offres — {rules.describe()}", ""]
    cols = [c for c in ["title", "company", "location", "job_type", "date_posted", "job_url", "query",
                         "description"]
            if c in df.columns]
    sub = pd.DataFrame(df[cols])
    for _, r in sub.iterrows():
        lines.append(f"## {r.get('title', '?')} — {r.get('company', '?')}")
        lines.append(f"- Lieu : {r.get('location', '?')} | Contrat : {r.get('job_type', '?')} | "
                     f"Publié : {r.get('date_posted', '?')} | Requête : {r.get('query', '?')}")
        if r.get("job_url"):
            lines.append(f"- Lien : {r.get('job_url')}")
        desc = desc_excerpt(r.get("description"), args.desc_limit) if "description" in df.columns else ""
        if desc:
            lines.append(f"- Description : {desc}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK : {len(df)} offres -> {csv_path} + {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
