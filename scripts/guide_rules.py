#!/usr/bin/env python3
"""Règles de filtrage génériques lues depuis le profil (`guide_recherche.md`).

Zéro liste métier en dur ici : tout vient des lignes d'en-tête du guide :
    Contrat : CDI ou CDD. Pas de stage.
    Exclusions : tournage, maquettiste, teinturière

Utilisé par fetch_direct.py, fetch_eures.py et fetch_jobspy.py pour que
changer de profil = éditer le guide, sans toucher au code.

Si le guide est absent ou encore placeholder (`[...]`, `À personnaliser`),
aucun filtre n'est appliqué (bénéfice du doute) et `configured` vaut False.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# Vocabulaire contrat connu (détection, pas filtrage : le filtrage vient du guide).
KNOWN_CONTRACTS = [
    "CDI", "CDD", "CDDU", "CDI-CDD",
    "interim", "intérim", "intermittent",
    "freelance", "benevolat", "bénévolat",
]

# Refus courants -> variantes cherchées dans les offres (FR + EN).
REFUSAL_SYNONYMS = {
    "stage": ["stag", "internship", "intern", "job d", "summer job"],
    "alternance": ["alternance"],
    "apprentissage": ["apprent"],
}

PLACEHOLDER_RE = re.compile(r"\[.*?\]")
REFUSE_CLAUSE_RE = re.compile(
    r"(?:pas\s+de|hors|sauf|except[eé]|ni|no)\s+([^.,;()]+)", re.IGNORECASE
)


def norm(s: str) -> str:
    """Minuscules + accents supprimés pour un matching insensible aux accents."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.lower()).strip()


def find_guide(explicit: str | None = None) -> Path | None:
    """Localise le guide : explicite > profil/guide_recherche.md > guide_recherche.md (rétrocompat)."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates += [Path("profil/guide_recherche.md"), Path("guide_recherche.md")]
    # + chemin relatif au dossier scripts/ (lancé depuis scripts/ ou racine)
    here = Path(__file__).resolve().parent
    candidates += [here.parent / "profil" / "guide_recherche.md", here.parent / "guide_recherche.md"]
    for c in candidates:
        if c.is_file():
            return c
    return None


def _header_line(text: str, key: str) -> str:
    m = re.search(rf"(?im)^\s*{key}\s*:\s*(.+?)\s*$", text)
    return m.group(1).strip() if m else ""


def _is_placeholder(line: str) -> bool:
    if not line:
        return True
    stripped = PLACEHOLDER_RE.sub("", line).strip(" ,;.-")
    if not stripped:
        return True
    return bool(re.search(r"personnaliser|préciser|vos |non précisé|selon préférence", stripped, re.IGNORECASE))


def parse_contrat(line: str) -> tuple[list[str], list[str]]:
    """Retourne (acceptés, refusés) depuis la ligne `Contrat:` du guide."""
    if _is_placeholder(line):
        return [], []
    accepted: list[str] = []
    nline = norm(line)
    for c in KNOWN_CONTRACTS:
        if norm(c) in nline:
            # Ne pas compter comme accepté un type cité dans une clause de refus.
            refused_zone = " ".join(m.group(1) for m in REFUSE_CLAUSE_RE.finditer(line))
            if norm(c) not in norm(refused_zone):
                accepted.append(c.upper() if len(c) <= 6 and c.isalpha() else c)
    refused: list[str] = []
    for m in REFUSE_CLAUSE_RE.finditer(line):
        chunk = norm(m.group(1))
        for key, variants in REFUSAL_SYNONYMS.items():
            if key in chunk or any(v in chunk for v in variants):
                refused.append(key)
        # Terme de refus inconnu (ex : "pas de bénévolat") : garder tel quel.
        if not any(key in chunk for key in REFUSAL_SYNONYMS):
            for tok in re.split(r"\s*(?:,|/| et | ou )\s*", m.group(1).strip()):
                if tok and len(tok) > 2:
                    refused.append(tok.strip().lower())
    return sorted(set(accepted)), sorted(set(refused))


def parse_exclusions(line: str) -> list[str]:
    """Découpe la ligne `Exclusions:` sur virgules/points-virgules."""
    if _is_placeholder(line):
        return []
    terms: list[str] = []
    for tok in re.split(r"[;,]", PLACEHOLDER_RE.sub("", line)):
        tok = tok.strip(" .-")
        tok = re.sub(r"(?i)^(?:pas\s+de\s+|hors\s+|ni\s+)", "", tok).strip()
        if len(tok) > 1:
            terms.append(tok.lower())
    return terms


def parse_keywords(text: str) -> list[str]:
    """Intitulés de recherche : section `Intitulés portails` (puis repli `Mots-clés`,
    puis puces des familles métier). La section `Compétences` n'est jamais cherchée."""
    kws: list[str] = []
    # Priorité : nouvelle section `Intitulés portails`, sinon ancien `Mots-clés` (rétrocompat).
    # Le corps s'arrête à la prochaine section (#) pour ne pas aspirer `Compétences`.
    m = re.search(
        r"(?im)^.*intitul[ée]s\s+portails.*$\n(?P<body>(?:(?!^#{1,6}\s).*(\n|$))*)",
        text,
    ) or re.search(
        r"(?im)^.*mots-cl[ée]s.*$\n(?P<body>(?:(?!^#{1,6}\s).*(\n|$))*)",
        text,
    )
    if m:
        body = m.group("body")
        for tok in re.split(r"[,`\n]", body):
            tok = tok.strip(" `*-–—")
            if len(tok) > 2 and not tok.startswith(("[", "#")) and "[" not in tok and "]" not in tok:
                kws.append(tok)
                if len(kws) >= 20:
                    break
    if not kws:
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("- ") and len(s) > 4 and not s.startswith("- ["):
                kws.append(s[2:].strip())
    # Déduplique en gardant l'ordre.
    seen, out = set(), []
    for k in kws:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            out.append(k)
    return out[:20]


@dataclass
class GuideRules:
    """Règles compilées depuis le guide. `configured=False` = aucun filtre."""

    source: str = ""
    configured: bool = False
    accepted: list[str] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    exclusions: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    def describe(self) -> str:
        if not self.configured:
            return "filtre guide : non configuré (guide absent ou placeholders)"
        parts = []
        if self.accepted:
            parts.append("contrats acceptés: " + "/".join(self.accepted))
        if self.refused:
            parts.append("refusés: " + ", ".join(self.refused))
        if self.exclusions:
            parts.append("exclusions: " + ", ".join(self.exclusions))
        return "filtre guide (" + self.source + ") : " + (" ; ".join(parts) or "aucun")


def load_guide(explicit: str | None = None) -> GuideRules:
    path = find_guide(explicit)
    if path is None:
        return GuideRules()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return GuideRules()
    contrat_line = _header_line(text, "Contrat")
    excl_line = _header_line(text, "Exclusions")
    accepted, refused = parse_contrat(contrat_line)
    exclusions = parse_exclusions(excl_line)
    rules = GuideRules(
        source=str(path),
        configured=bool(accepted or refused or exclusions),
        accepted=accepted,
        refused=refused,
        exclusions=exclusions,
        keywords=parse_keywords(text),
    )
    return rules


def is_excluded(title: str, description: str = "", job_type: str = "",
                rules: GuideRules | None = None) -> tuple[bool, str]:
    """Dit si une offre est rejetée par le guide. Retourne (rejetée, motif)."""
    if rules is None or not rules.configured:
        return False, ""
    hay_title = norm(f"{title} {job_type}")
    hay_full = norm(f"{title} {description} {job_type}")
    for r in rules.refused:
        variants = REFUSAL_SYNONYMS.get(r, [r])
        if any(norm(v) in hay_title for v in variants):
            return True, f"contrat refusé ({r})"
    for term in rules.exclusions:
        if norm(term) in hay_full:
            return True, f"exclusion ({term})"
    if rules.accepted:
        # Contrat renseigné mais aucun type accepté dedans → rejeté. Vide = gardé.
        contract_zone = norm(f"{title} {job_type}")
        if contract_zone.strip() and not any(
            norm(a) in contract_zone for a in rules.accepted
        ):
            # Ne rejeter que si un vocabulaire contrat est détecté (évite les faux positifs).
            if any(norm(k) in contract_zone for k in KNOWN_CONTRACTS):
                return True, "contrat hors liste"
    return False, ""
