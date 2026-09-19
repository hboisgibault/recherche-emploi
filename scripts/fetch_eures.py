#!/usr/bin/env python3
"""Récupère les offres du jour via l'API publique EURES (Europe).

Mots-clés et filtre lus depuis le profil (`profil/guide_recherche.md`) :
changez de profil = éditez le guide, sans toucher au code.
Sans clé API.

API : POST https://europa.eu/eures/api/jv-searchengine/public/jv-search/search

Usage :
    python3 scripts/fetch_eures.py [--days 1] [--pages 3] [--out-dir .]
    python3 scripts/fetch_eures.py --days 7 --countries fr be --lang fr
    python3 scripts/fetch_eures.py --keywords "soudeur" "tuyauteur"

Sorties : offres/AAAA-MM-JJ/offres_eures_AAAA-MM-JJ.csv + .md
(dossier créé automatiquement).
"""

import argparse
import csv
import html as htmlmod
import re
import sys
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERREUR : requests non installé.", file=sys.stderr)
    sys.exit(1)

try:
    from guide_rules import countries_for_zones, is_excluded as guide_is_excluded, load_guide
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from guide_rules import countries_for_zones, is_excluded as guide_is_excluded, load_guide

API_URL = "https://europa.eu/eures/api/jv-searchengine/public/jv-search/search"


# Europe de l'Ouest (codes NUTS pays, minuscules)
DEFAULT_COUNTRIES = ["fr", "be", "nl", "lu", "de", "at", "ch", "it", "es", "pt", "ie"]


def search_page(session: requests.Session, keywords, countries, page: int,
                days: int, lang: str, session_id: str) -> dict:
    period = "LAST_DAY" if days <= 1 else ("LAST_THREE_DAYS" if days <= 3 else "LAST_WEEK")
    payload = {
        "resultsPerPage": 50,
        "page": page,
        "sortSearch": "MOST_RECENT",
        "keywords": [{"keyword": k, "specificSearchCode": "EVERYWHERE"} for k in keywords],
        "publicationPeriod": period,
        "occupationUris": [],
        "skillUris": [],
        "requiredExperienceCodes": [],
        "positionScheduleCodes": [],
        "sectorCodes": [],
        "educationAndQualificationLevelCodes": [],
        "positionOfferingCodes": [],
        "locationCodes": countries,
        "euresFlagCodes": [],
        "otherBenefitsCodes": [],
        "requiredLanguages": [],
        "minNumberPost": None,
        "sessionId": session_id,
        "requestLanguage": lang,
    }
    resp = session.post(API_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def extract_offers(data: dict) -> list:
    # Clé réelle observée : "jvs". On couvre les variantes au cas où.
    for key in ("jvs", "jvList", "vacancyList", "results", "vacancies"):
        items = data.get(key)
        if isinstance(items, list) and items:
            return items
    # enveloppe possible { "data": {...} }
    inner = data.get("data")
    if isinstance(inner, dict):
        return extract_offers(inner)
    return []


def to_date(v) -> str:
    if v is None or v == "":
        return ""
    if isinstance(v, (int, float)):  # epoch millis côté EURES
        try:
            return datetime.fromtimestamp(v / 1000, tz=timezone.utc).date().isoformat()
        except (OverflowError, OSError, ValueError):
            return str(v)
    return str(v)


def norm(o: dict) -> dict:
    title = o.get("title") or o.get("occupationLabel") or o.get("jobTitle") or "?"
    employer = o.get("employer")
    if isinstance(employer, dict):
        company = employer.get("name") or "?"
    else:
        company = o.get("employerName") or o.get("company") or "?"
    loc = o.get("location") or o.get("locationLabel") or o.get("country") or ""
    if isinstance(loc, dict):
        loc = loc.get("label") or loc.get("name") or ""
    if not loc and isinstance(o.get("locationMap"), dict):
        # ex. {"FR": ["FRK28"]} -> "FR"
        loc = ", ".join(sorted(o["locationMap"].keys()))
    if not loc:
        loc = "?"
    pub = (to_date(o.get("publicationDate")) or to_date(o.get("creationDate"))
           or to_date(o.get("lastModificationDate")) or to_date(o.get("lastModifiedDate")))
    oid = str(o.get("id") or o.get("jvId") or o.get("vacancyId") or f"{title}|{company}|{loc}")
    url = o.get("url") or o.get("detailsUrl") or ""
    if not url and oid and "|" not in oid:
        url = f"https://eures.europa.eu/fr/jv-se/jv-details/{oid}"
    desc = str(o.get("description") or o.get("summary") or "")
    return {"id": oid, "title": str(title), "company": str(company),
            "location": str(loc), "date": str(pub), "url": str(url), "desc": desc}


def clean_desc(s: str, limit: int = 3000) -> str:
    """Nettoie la description HTML EURES (<br>, entités) et la tronque."""
    s = re.sub(r"<br\s*/?>", "\n", s or "", flags=re.IGNORECASE)
    s = re.sub(r"</p\s*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    s = htmlmod.unescape(s)
    s = re.sub(r"[\u00a0]+", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" +\n", "\n", s)
    s = re.sub(r"\n\s*\n+", "\n", s).strip()
    if len(s) > limit:
        s = s[:limit] + "…"
    return s


def main() -> int:
    ap = argparse.ArgumentParser(description="Offres du jour via EURES")
    ap.add_argument("--days", type=int, default=1, help="fenêtre : 1, 3 ou 7 jours (défaut: 1)")
    ap.add_argument("--pages", type=int, default=1, help="pages de 50 résultats par mot-clé (défaut: 1)")
    ap.add_argument("--countries", nargs="+", default=None,
                    help="pays EURES (défaut: dérivé de la Zone du guide, sinon Europe de l'Ouest)")
    ap.add_argument("--lang", default="fr", help="langue de réponse (défaut: fr)")
    ap.add_argument("--guide", default=None, help="chemin du guide_recherche.md (défaut: profil/guide_recherche.md)")
    ap.add_argument("--keywords", nargs="*", default=None, help="mots-clés (défaut: ceux du guide, sinon repli)")
    ap.add_argument("--out-dir", default="offres", help="dossier de sortie (défaut: offres)")
    args = ap.parse_args()

    rules = load_guide(args.guide)
    print(f"# {rules.describe()}")
    keywords = args.keywords or rules.keywords
    if not keywords:
        print("ERREUR : aucun mot-clé de recherche.", file=sys.stderr)
        print("Renseignez les intitulés dans profil/guide_recherche.md ou passez --keywords.", file=sys.stderr)
        return 2

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json", "User-Agent": "recherche-emploi/1.0"})
    session_id = f"recherche-{uuid.uuid4().hex[:8]}"
    if args.countries is not None:
        countries = [c.lower() for c in args.countries]
    else:
        countries = countries_for_zones(rules.zones) or list(DEFAULT_COUNTRIES)
        print(f"# pays EURES : {','.join(countries)}"
              f" ({'Zone du guide' if countries_for_zones(rules.zones) else 'défaut Europe de l’Ouest'})")

    all_offers: dict = {}
    # NB : les keywords EURES se combinent en ET -> une requête par mot-clé, puis fusion.
    for kw in keywords:
        for page in range(1, args.pages + 1):
            try:
                data = search_page(session, [kw], countries, page, args.days, args.lang, session_id)
            except requests.HTTPError as e:
                print(f"! '{kw}' page {page} : HTTP {e}", file=sys.stderr)
                break
            except Exception as e:
                print(f"! '{kw}' page {page} : {e}", file=sys.stderr)
                break
            items = extract_offers(data)
            for raw in items:
                o = norm(raw)
                rejected, _ = guide_is_excluded(o["title"], o["desc"], "", rules)
                if rejected:
                    continue
                all_offers[o["id"]] = o
            time.sleep(1)  # politesse anti-429
            if len(items) < 50:
                break

    offers = sorted(all_offers.values(), key=lambda o: o["date"], reverse=True)

    today = date.today().isoformat()
    out_dir = Path(args.out_dir)
    dated_dir = out_dir / today
    out_dir.mkdir(parents=True, exist_ok=True)
    dated_dir.mkdir(parents=True, exist_ok=True)
    csv_path = dated_dir / f"offres_eures_{today}.csv"
    md_path = dated_dir / f"offres_eures_{today}.md"

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "title", "company", "location", "date", "url",
                                          "description"])
        w.writeheader()
        for o in offers:
            row = {k: o[k] for k in ["id", "title", "company", "location", "date", "url"]}
            row["description"] = clean_desc(o.get("desc", ""))
            w.writerow(row)

    lines = [f"# Offres EURES du {today}",
             f"{len(offers)} offres (fenêtre {args.days}j, {','.join(countries)})",
             rules.describe(), ""]
    for o in offers:
        lines.append(f"## {o['title']} — {o['company']}")
        lines.append(f"- Lieu : {o['location']} | Publié : {o['date']}")
        if o["url"]:
            lines.append(f"- Lien : {o['url']}")
        excerpt = clean_desc(o.get("desc", ""), limit=500).replace("\n", " ")
        if excerpt:
            lines.append(f"- Description : {excerpt}")
        lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK : {len(offers)} offres -> {csv_path} + {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
