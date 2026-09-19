#!/usr/bin/env python3
"""Collecte quotidienne des offres sur les sites directs (companies.yaml).

Usage :
    python3 scripts/fetch_direct.py
    python3 scripts/fetch_direct.py --only "20.12,Palais" --limit 5
    python3 scripts/fetch_direct.py --companies profil/companies.yaml --out-dir offres --state state_direct.json

Principe : 1 entree = 1 fetch HTML poli + extraction d'offres + hash diff.
Sorties : offres/AAAA-MM-JJ/offres_direct_AAAA-MM-JJ.csv + .md (nouvelles offres uniquement).
Etat : state_direct.json (offres vues + hash pages pour detecter les changements).
"""

import argparse
import csv
import hashlib
import json
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote

try:
    import requests
    import yaml
    from bs4 import BeautifulSoup
except ImportError as e:
    print(f"ERREUR dependance manquante : {e}\nLance : pip install requests beautifulsoup4 pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from guide_rules import KNOWN_CONTRACTS, is_excluded as guide_is_excluded, load_guide
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from guide_rules import KNOWN_CONTRACTS, is_excluded as guide_is_excluded, load_guide

HEADERS = {
    "User-Agent": "RechercheEmploi/1.0 (+usage personnel, 1 req/s max)",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
}

RULES = None  # GuideRules, chargé dans main() depuis le profil (guide_recherche.md)

# Signaux "offre" génériques (mécanique de détection, pas de métier en dur ;
# les intitulés du guide sont ajoutés dynamiquement dans main()).
URL_OFFER_RE = re.compile(r"offre|emploi|job|recrut|carri[eè]re|career|poste|opportunit|rejoindre|vacanc|annonce", re.IGNORECASE)
BASE_OFFER_WORDS = (
    r"recrute|recherche|rejoignez|fiche de poste|offre d.?emploi|postulez"
    r"|assistant|production"
)
TEXT_OFFER_RE = re.compile(rf"\b({BASE_OFFER_WORDS})\b", re.IGNORECASE)
CONTRAT_RE = re.compile(r"\b(" + "|".join(KNOWN_CONTRACTS) + r")\b", re.IGNORECASE)


def build_detection_res(rules) -> None:
    """Enrichit la détection avec le profil : mots-clés du guide + contrats acceptés."""
    global TEXT_OFFER_RE, CONTRAT_RE
    if rules is not None and rules.configured:
        extra = "|".join(re.escape(k) for k in rules.keywords[:20])
        TEXT_OFFER_RE = re.compile(rf"\b({BASE_OFFER_WORDS}|{extra})\b", re.IGNORECASE)
        if rules.accepted:
            CONTRAT_RE = re.compile(
                r"\b(" + "|".join(re.escape(a) for a in rules.accepted) + r")\b", re.IGNORECASE
            )
SKIP_URL_RE = re.compile(
    r"newsletter|faq|contact|mentions-legales|politique-de-confidentialite|plan-du-site"
    r"|credits|cgu|cgv|appel|marches?-publics?|rapports?-annuels?|billetterie|agenda|tarif|horaire"
    r"|boutique|presse|offre-aux-professionnels|coffret|emballage|produit|panier|checkout"
    r"|livraison|eshop|offres?-sp[eé]ciales",
    re.IGNORECASE,
)
SKIP_TEXT = {
    "recrutement", "recruitment", "carrieres", "carrières", "jobs",
    "offres", "offres d'emploi", "nos offres", "appels d'offres",
}
SLUG_OFFER_RE = re.compile(r"/(cdd?u?|cdi|stage|alternance|offre|emploi|job|poste|apply|candidature)[-_]", re.IGNORECASE)


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())[:300]


def page_hash(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def is_le19m_offer(href: str) -> bool:
    # /fr/savoir-faire/carrieres/<slug> sans query string = offre ; avec ?category/?recruiter = filtre
    p = urlparse(href)
    return "/carrieres/" in p.path and p.path.rstrip("/").split("/")[-1] not in ("carrieres",) and not p.query


def extract_offers(company: dict, html: str, base_url: str) -> list[dict]:
    """Extraction generique + regles specifiques (le19M, Palais, PDF)."""
    soup = BeautifulSoup(html, "html.parser")
    offers: list[dict] = []
    seen_urls: set[str] = set()
    base_norm = base_url.rstrip("/")
    is_le19m = "le19m.com" in base_url
    excludes = [e.lower() for e in (company.get("exclude") or [])]
    for a in soup.find_all("a", href=True):
        href_val = a.get("href", "")
        if isinstance(href_val, list):
            href_val = href_val[0] if href_val else ""
        raw_href = str(href_val).strip()
        if not raw_href or raw_href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        text = clean_text(a.get_text())
        href = urljoin(base_url, raw_href)
        if href.rstrip("/") == base_norm:
            continue  # auto-lien
        href_match = unquote(href)  # les ATS encodent les accents (%c3%a9)
        if any(x in href_match.lower() for x in excludes):
            continue  # exclu par entreprise (ex: pages categories ATS)
        uparse = urlparse(href_match)
        path = uparse.path.lower()
        url_target = path + ("?" + uparse.query.lower() if uparse.query else "")
        if SKIP_URL_RE.search(href_match) or text.lower().replace("’", "'") in SKIP_TEXT:
            continue

        is_pdf_offer = path.endswith(".pdf") and re.search(r"offre|fiche|poste|recrut|annonce", href_match + " " + text, re.IGNORECASE)
        if is_le19m:
            # le19M : seules les fiches /carrieres/<slug> (sans query) et les PDF comptent,
            # les liens ?category= / ?recruiter= sont des filtres, pas des offres.
            if is_le19m_offer(href_match):
                kind, title = "offre", text or raw_href.split("/")[-1].replace("-", " ")
            elif is_pdf_offer:
                kind, title = "pdf", text or Path(path).name
            else:
                continue
        elif is_le19m_offer(href_match):
            kind, title = "offre", text or raw_href.split("/")[-1].replace("-", " ")
        elif is_pdf_offer:
            kind, title = "pdf", text or Path(path).name
        elif URL_OFFER_RE.search(url_target) and len(text) >= 15:
            kind, title = "offre", text
        elif (
            TEXT_OFFER_RE.search(text)
            and 15 <= len(text) <= 250
            and (CONTRAT_RE.search(text) or SLUG_OFFER_RE.search(path))
        ):
            kind, title = "mention", text
        else:
            continue
        if len(title) < 8 or href in seen_urls:
            continue
        seen_urls.add(href)
        m = CONTRAT_RE.search(title)
        offers.append({
            "titre": title,
            "url_offre": href,
            "contrat": m.group(1).upper() if m else "",
            "kind": kind,
        })
    return offers


def is_excluded(title: str) -> bool:
    """Filtre du guide (Contrat/Exclusions). Guide non configuré = rien filtré."""
    if RULES is None:
        return False
    rejected, _ = guide_is_excluded(title, "", "", RULES)
    return rejected


def fetch_html(session: requests.Session, url: str, timeout: int) -> str | None:
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        if "text/html" not in r.headers.get("Content-Type", "text/html"):
            return None
        return r.text
    except Exception as e:
        print(f"! fetch echoue {url} : {e}", file=sys.stderr)
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="Offres directes quotidiennes (sites entreprises)")
    ap.add_argument("--companies", default="profil/companies.yaml")
    ap.add_argument("--out-dir", default="offres", help="dossier de sortie (défaut: offres)")
    ap.add_argument("--state", default="state_direct.json")
    ap.add_argument("--only", default="", help="filtre sous-chaine sur nom, ex: '20.12,Palais'")
    ap.add_argument("--limit", type=int, default=0, help="limite nb entreprises (0 = toutes)")
    ap.add_argument("--delay", type=float, default=1.0, help="pause entre requetes (s)")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--guide", default=None, help="chemin du guide_recherche.md (défaut: profil/guide_recherche.md)")
    ap.add_argument("--keep-stage", action="store_true", help="ne pas appliquer le filtre du guide")
    args = ap.parse_args()

    global RULES
    RULES = load_guide(args.guide)
    build_detection_res(RULES)
    print(f"# {RULES.describe()}")

    comps_path = Path(args.companies)
    if not comps_path.exists():
        print(f"ERREUR : {comps_path} introuvable", file=sys.stderr)
        return 1
    companies = yaml.safe_load(comps_path.read_text(encoding="utf-8")) or []

    if args.only:
        keys = [k.strip().lower() for k in args.only.split(",") if k.strip()]
        companies = [c for c in companies if any(k in str(c.get("nom", "")).lower() for k in keys)]
    if args.limit:
        companies = companies[: args.limit]
    if not companies:
        print("Aucune entreprise selectionnee.")
        return 0

    state_path = Path(args.state)
    state = {"seen": {}, "pages": {}}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.setdefault("seen", {})
            state.setdefault("pages", {})
        except Exception:
            pass

    session = requests.Session()
    session.headers.update(HEADERS)
    today = date.today().isoformat()
    new_rows: list[dict] = []
    surveyed: list[dict] = []

    for i, c in enumerate(companies):
        nom = c.get("nom", "?")
        fetch_url = c.get("url") or c.get("url_site")
        if not fetch_url:
            print(f"- {nom} : pas d'URL, ignore")
            continue
        print(f"[{i + 1}/{len(companies)}] {nom} -> {fetch_url}")
        html = fetch_html(session, fetch_url, args.timeout)
        if i < len(companies) - 1:
            time.sleep(args.delay)
        if html is None:
            surveyed.append({"nom": nom, "statut": "fetch_ko", "url": fetch_url})
            continue
        h = page_hash(html)
        old_h = state["pages"].get(nom)
        changed = old_h is not None and old_h != h
        state["pages"][nom] = h

        if (c.get("type") == "sans_page"):
            surveyed.append({"nom": nom, "statut": "surveillee_changee" if changed else "surveillee_inchangee", "url": fetch_url})
            continue
        offers = extract_offers(c, html, fetch_url)
        n_new = 0
        for o in offers:
            if not args.keep_stage and is_excluded(o["titre"]):
                continue
            key = f"{nom}|{o['titre']}|{o['url_offre']}"
            if key in state["seen"]:
                continue
            state["seen"][key] = today
            n_new += 1
            new_rows.append({
                "date_vue": today,
                "entreprise": nom,
                "secteur": c.get("secteur", ""),
                "lieu": c.get("lieu", ""),
                "titre": o["titre"],
                "contrat": o["contrat"],
                "url_offre": o["url_offre"],
                "url_source": fetch_url,
                "type": c.get("type", ""),
            })
        surveyed.append({"nom": nom, "statut": f"{len(offers)} detectees / {n_new} nouvelles", "url": fetch_url})

    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")

    out_dir = Path(args.out_dir) / today
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"offres_direct_{today}.csv"
    md_path = out_dir / f"offres_direct_{today}.md"
    if not new_rows and csv_path.exists():
        print(f"OK : 0 nouvelles offres, fichiers du jour conserves ({csv_path})")
        return 0
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date_vue", "entreprise", "secteur", "lieu", "titre", "contrat", "url_offre", "url_source", "type"])
        w.writeheader()
        w.writerows(new_rows)
    lines = [f"# Offres directes du {today}", f"{len(new_rows)} nouvelles offres — {RULES.describe()}", ""]
    for r in new_rows:
        lines.append(f"## {r['titre']}")
        lines.append(f"- Entreprise : {r['entreprise']} ({r['secteur']}, {r['lieu']}) | Contrat : {r['contrat'] or '?'}")
        lines.append(f"- Offre : {r['url_offre']}")
        lines.append(f"- Source : {r['url_source']}")
        lines.append("")
    lines.append("---\n\n## Relevé par entreprise")
    for s in surveyed:
        lines.append(f"- {s['nom']} : {s['statut']} — {s['url']}")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    print(f"OK : {len(new_rows)} nouvelles offres sur {len(companies)} entreprises -> {csv_path} + {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
