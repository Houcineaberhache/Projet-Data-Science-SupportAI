#!/usr/bin/env python3
"""Gestion du corpus SupportAI.

Usage:
    python scripts/manage_corpus.py build      # (re)génère source_manifest.csv
    python scripts/manage_corpus.py validate   # contrôle qualité du corpus

Dépendances : bibliothèque standard uniquement (Python 3.9+).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = ROOT / "data" / "raw" / "corpus"
LANGUAGES = ("fr", "en")
MANIFEST = ROOT / "data" / "source_manifest.csv"
STATS = ROOT / "docs" / "reports" / "corpus_stats.md"

COLUMNS = [
    "doc_id", "record_type", "title", "category", "doc_type", "language",
    "variant", "translation_of",
    "version", "effective_date", "owner", "author", "source_type",
    "source_origin", "source_url", "license", "license_url", "license_status",
    "verified_by", "verified_on", "reuse_permission", "attribution_required",
    "attribution_text", "contains_pii", "sensitivity", "index_in_rag",
    "chunking_profile", "review_status", "word_count", "est_tokens",
    "sha256", "relative_path", "document_format", "document_path", "notes",
]

REQUIRED_FRONT_MATTER = [
    "doc_id", "title", "category", "doc_type", "language",
    "version", "effective_date", "owner", "sensitivity", "source_type",
]

CATEGORIES = {
    "policies", "procedures", "faq", "product_guides",
    "internal_operations", "legal_summaries",
}

CHUNKING = {
    "policy": "policy_clause",
    "procedure": "procedure_steps",
    "faq": "qa_pair",
    "catalogue": "catalogue_section",
    "sop": "sop_section",
    "legal_summary": "legal_clause",
}

CHUNKING_OVERRIDES = {
    "OPS-02": "answer_template",
    "OPS-03": "reference_table",
}

# ---------------------------------------------------------------- registre

DEFAULT_DOC = {
    "record_type": "knowledge_base_document",
    "author": "Aya (Étudiant 1 — Data Engineer)",
    "source_origin": "Rédigé par l'équipe SupportAI pour NovaShop (société fictive)",
    "source_url": "",
    "license": "NovaShop-Proprietary-Synthetic",
    "license_url": "",
    "license_status": "internal_verified",
    "verified_by": "Aya (Étudiant 1)",
    "verified_on": "2026-11-05",
    "reuse_permission": "full_text_index",
    "attribution_required": "no",
    "attribution_text": "© NovaShop — contenu fictif créé pour le projet SupportAI",
    "contains_pii": "no",
    "index_in_rag": "yes",
    "review_status": "approved",
}

NOTES = {
    "POL-01": "Politique socle du retour ; référencée par POL-02, POL-07, PRO-02, FAQ-04.",
    "POL-02": "Délais et modes de remboursement ; dépend de POL-01 pour l'éligibilité.",
    "POL-03": "Zones, frais et délais de livraison ; source des réponses sur les retards.",
    "POL-04": "Garanties et exclusions ; à lire avec REG-02 (garantie légale).",
    "POL-05": "Moyens de paiement, facturation, TVA et ICE.",
    "POL-06": "Données personnelles ; aligné sur REG-03. Contient des données de démonstration.",
    "POL-07": "CGV ; contient des renvois croisés vers POL-01/03/04/05/06 et REG-01.",
    "POL-08": "Annulation et modification ; fenêtre de 2 h à 22 h selon le canal.",
    "POL-09": "Incidents à la livraison ; distinct de la garantie (POL-04).",
    "POL-10": "Codes promo, NovaPoints et cartes cadeaux.",
    "PRO-01": "Procédure de suivi ; fait référence au référentiel OPS-03.",
    "PRO-02": "Procédure de retour ; six codes motif R01-R06.",
    "PRO-03": "Procédure SAV ; huit codes symptôme S01-S08.",
    "PRO-04": "Canaux de contact et règles d'escalade client.",
    "FAQ-01": "Onze paires Q/R sur les commandes et le suivi.",
    "FAQ-02": "Douze paires Q/R sur la livraison.",
    "FAQ-03": "Douze paires Q/R sur le paiement.",
    "FAQ-04": "Treize paires Q/R sur les retours et remboursements, dont le retour partiel d'une commande multi-articles.",
    "FAQ-05": "Douze paires Q/R sur la garantie et le SAV.",
    "FAQ-06": "Douze paires Q/R sur les produits et le stock.",
    "FAQ-07": "Douze paires Q/R sur le compte et les données personnelles.",
    "FAQ-08": "Douze paires Q/R sur les promotions et la fidélité.",
    "CAT-01": "Quatre smartphones ; prix et garanties cohérents avec le catalogue.",
    "CAT-02": "Quatre ordinateurs portables ; autonomie et extensibilité.",
    "CAT-03": "Quatre produits audio ; l'un des rares documents avec contrainte d'hygiène.",
    "CAT-04": "Six accessoires ; garanties de 3 à 6 mois.",
    "CAT-05": "Trois montres connectées ; normes d'étanchéité.",
    "CAT-06": "Trois tablettes ; absence de liseuse e-ink assumée.",
    "OPS-01": "Matrice d'escalade ; sert de règle de transfert humain pour SupportAI.",
    "OPS-02": "Charte de ton et modèles de réponse ; utile comme few-shot de style.",
    "OPS-03": "Référentiel de 14 statuts ; base de la simulation de suivi.",
    "OPS-04": "Trois boutiques ; adresses et téléphones explicitement fictifs.",
    "OPS-05": "Gestion des litiges ; délais et seuils de geste commercial.",
    "REG-01": "Synthèse loi 31-08 ; ne cite pas d'article pour éviter toute erreur.",
    "REG-02": "Synthèse garantie légale / commerciale ; ne cite aucun numéro d'article.",
    "REG-03": "Synthèse loi 09-08 ; aucun numéro de déclaration CNDP inventé.",
    "REG-04": "Mentions légales fictives ; identifiants volontairement neutres.",
}

EXTERNAL = [
    {
        "doc_id": "EXT-01",
        "title": "Loi n° 31-08 relative à la protection du consommateur (texte officiel)",
        "category": "external_reference",
        "doc_type": "legislation",
        "owner": "Royaume du Maroc — SGG",
        "author": "Royaume du Maroc",
        "source_origin": "Bulletin Officiel n° 5932 du 7 avril 2011 ; dahir n° 1-11-03",
        "source_url": "https://www.wipo.int/wipolex/fr/legislation/details/19773",
        "license": "Official-Text-No-Reuse-Claimed",
        "license_status": "verified_link_only",
        "reuse_permission": "citation_only",
        "attribution_text": "Royaume du Maroc, loi n° 31-08, BO n° 5932 du 07/04/2011",
        "review_status": "verified",
        "notes": "Texte législatif officiel. Aucune copie intégrale archivée : notre REG-01 est une synthèse originale. Ne pas indexer.",
    },
    {
        "doc_id": "EXT-02",
        "title": "Loi n° 09-08 relative à la protection des données personnelles (texte officiel)",
        "category": "external_reference",
        "doc_type": "legislation",
        "owner": "Royaume du Maroc — CNDP",
        "author": "Royaume du Maroc",
        "source_origin": "Bulletin Officiel n° 5714 du 5 mars 2009 ; dahir n° 1-09-15",
        "source_url": "https://www.cndp.ma/wp-content/uploads/2023/11/Loi-09-08-Fr.pdf",
        "license": "Official-Text-No-Reuse-Claimed",
        "license_status": "verified_link_only",
        "reuse_permission": "citation_only",
        "attribution_text": "Royaume du Maroc, loi n° 09-08, BO n° 5714 du 05/03/2009",
        "review_status": "verified",
        "notes": "PDF publié par la CNDP. Lien uniquement, pas de copie dans le corpus.",
    },
    {
        "doc_id": "EXT-03",
        "title": "Directive 2011/83/EU sur les droits des consommateurs (EUR-Lex)",
        "category": "external_reference",
        "doc_type": "legislation",
        "owner": "Union européenne",
        "author": "Parlement européen et Conseil",
        "source_origin": "EUR-Lex, CELEX 32011L0083",
        "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32011L0083",
        "license": "EU-Reuse-Decision-2011-833",
        "license_url": "https://eur-lex.europa.eu/content/legal-notice/legal-notice.html",
        "license_status": "verified",
        "reuse_permission": "full_text_reference_only",
        "attribution_text": "© Union européenne, 2011 — réutilisé sous décision 2011/833/EU",
        "review_status": "verified",
        "notes": "Réutilisation autorisée avec mention de la source (décision 2011/833/EU). Sert de comparaison, pas de règle NovaShop.",
    },
    {
        "doc_id": "EXT-04",
        "title": "CFPB Consumer Complaint Database",
        "category": "external_reference",
        "doc_type": "dataset",
        "owner": "U.S. Consumer Financial Protection Bureau",
        "author": "CFPB",
        "source_origin": "consumerfinance.gov/data-research",
        "source_url": "https://www.consumerfinance.gov/data-research/consumer-complaints/",
        "license": "Public-Domain-US-Government",
        "license_status": "verified_link_only",
        "reuse_permission": "citation_only",
        "attribution_text": "Source : CFPB Consumer Complaint Database",
        "review_status": "verified",
        "notes": "Le CFPB indique que les récits déjà publiés sont dans le domaine public au sens FOIA. Utilisable pour la typologie des plaintes, pas pour le contenu NovaShop.",
    },
    {
        "doc_id": "EXT-05",
        "title": "Creative Commons — Frequently Asked Questions",
        "category": "external_reference",
        "doc_type": "webpage",
        "owner": "Creative Commons",
        "author": "Creative Commons",
        "source_origin": "creativecommons.org/faq",
        "source_url": "https://creativecommons.org/faq/",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_status": "verified_link_only",
        "reuse_permission": "full_text_reference_only",
        "attribution_text": "« Frequently Asked Questions » © Creative Commons, CC BY 4.0",
        "review_status": "verified",
        "notes": "Sert de référence pour formuler les règles de licence du corpus. Non indexé.",
    },
    {
        "doc_id": "EXT-06",
        "title": "Wikipedia — Customer support (article encyclopédique)",
        "category": "external_reference",
        "doc_type": "webpage",
        "owner": "Wikimedia Foundation",
        "author": "Contributeurs Wikipédia",
        "source_origin": "en.wikipedia.org",
        "source_url": "https://en.wikipedia.org/wiki/Customer_support",
        "license": "CC-BY-SA-4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "license_status": "verified_link_only",
        "reuse_permission": "citation_only",
        "attribution_text": "Wikipédia, « Customer support », CC BY-SA 4.0",
        "review_status": "verified",
        "notes": "Contexte général uniquement. Le partage à l'identique (SA) interdit toute réutilisation dans un corpus propriétaire.",
    },
    {
        "doc_id": "EXT-07",
        "title": "BANKING77 — jeu de données d'intentions client (PolyAI)",
        "category": "external_reference",
        "doc_type": "dataset",
        "owner": "PolyAI",
        "author": "Casanueva et al. (2020)",
        "source_origin": "Hugging Face / GitHub PolyAI-LDN/task-specific-datasets",
        "source_url": "https://huggingface.co/datasets/PolyAI/banking77",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_status": "verified",
        "reuse_permission": "full_text_reference_only",
        "attribution_text": "BANKING77, PolyAI (2020), CC BY 4.0",
        "review_status": "verified",
        "notes": "Licence CC BY 4.0 confirmée sur la fiche du jeu de données et le dépôt GitHub. Sert de benchmark externe pour la classification d'intentions.",
    },
]

EXTERNAL_DEFAULT = {
    "record_type": "external_reference",
    "language": "fr",
    "variant": "",
    "translation_of": "",
    "version": "n/a",
    "effective_date": "",
    "verified_by": "Aya (Étudiant 1)",
    "verified_on": "2026-11-05",
    "attribution_required": "yes",
    "contains_pii": "no",
    "sensitivity": "public",
    "index_in_rag": "no",
    "chunking_profile": "not_indexed",
    "word_count": "",
    "est_tokens": "",
    "sha256": "",
    "relative_path": "",
    "document_format": "",
    "document_path": "",
    "license_url": "",
}

# ---------------------------------------------------------------- helpers


def parse_front_matter(path: Path) -> tuple[dict, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, parts[2].lstrip("\n")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", text)


def shingles(text: str, k: int = 5) -> set[str]:
    words = normalize(text).split()
    return {" ".join(words[i:i + k]) for i in range(max(0, len(words) - k + 1))}


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def est_tokens(words: int) -> int:
    # Approximation française : ~1,35 token par mot pour les tokenizers sous-word.
    return int(round(words * 1.35))


DOCUMENTS_MANIFEST = ROOT / "data" / "processed" / "documents" / "manifest_documents.csv"


def load_delivered() -> dict[tuple[str, str], dict]:
    """Indexe les fichiers livrables (PDF/DOCX/FAQ) par (doc_id, langue)."""
    if not DOCUMENTS_MANIFEST.exists():
        return {}
    index: dict[tuple[str, str], dict] = {}
    with DOCUMENTS_MANIFEST.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            index[(row["doc_id"], row["language"])] = row
    return index


# ---------------------------------------------------------------- build


def collect_documents() -> list[dict]:
    delivered = load_delivered()
    rows = []
    for language in LANGUAGES:
        for path in sorted((CORPUS_ROOT / language).glob("*.md")):
            meta, body = parse_front_matter(path)
            if not meta:
                print(f"[ERREUR] front matter absent : {path.name}", file=sys.stderr)
                continue
            doc_id = meta["doc_id"]
            words = len(body.split())
            row = dict(DEFAULT_DOC)
            row.update(meta)
            row["record_type"] = "knowledge_base_document"
            row["language"] = language
            row["variant"] = "original" if language == "fr" else "translation"
            row["translation_of"] = "" if language == "fr" else doc_id
            row["chunking_profile"] = CHUNKING_OVERRIDES.get(
                doc_id, CHUNKING.get(meta["doc_type"], "policy_clause")
            )
            row["word_count"] = str(words)
            row["est_tokens"] = str(est_tokens(words))
            row["sha256"] = sha256(path)
            row["relative_path"] = path.relative_to(ROOT).as_posix()
            info = delivered.get((doc_id, language), {})
            row["document_format"] = info.get("format", "")
            row["document_path"] = info.get("relative_path", "")
            suffix = "" if language == "fr" else " · English translation"
            row["notes"] = NOTES.get(doc_id, "") + suffix
            rows.append(row)
    return rows


def build() -> None:
    rows = collect_documents()
    for ext in EXTERNAL:
        row = dict(EXTERNAL_DEFAULT)
        row.update(ext)
        rows.append(row)

    with MANIFEST.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"source_manifest.csv : {len(rows)} lignes "
          f"({sum(r['record_type'] == 'knowledge_base_document' for r in rows)} documents, "
          f"{len(EXTERNAL)} références externes)")
    write_stats([r for r in rows if r["record_type"] == "knowledge_base_document"])


def write_stats(rows: list[dict]) -> None:
    by_cat = Counter(r["category"] for r in rows)
    by_chunk = Counter(r["chunking_profile"] for r in rows)
    words = [int(r["word_count"]) for r in rows]
    total_words = sum(words)
    unique_docs = len({r["doc_id"] for r in rows})
    STATS.parent.mkdir(exist_ok=True)
    lines = [
        "# Statistiques du corpus SupportAI / Corpus statistics",
        "",
        "> Fichier généré automatiquement par `scripts/manage_corpus.py build`.",
        "",
        f"- Documents logiques : **{unique_docs}**",
        f"- Fichiers indexables : **{len(rows)}** (2 langues)",
        f"- Volume total : **{total_words:,} mots** (~{est_tokens(total_words):,} tokens)".replace(",", " "),
        f"- Longueur moyenne : **{statistics.mean(words):.0f} mots** "
        f"(min {min(words)}, max {max(words)}, médiane {statistics.median(words):.0f})",
        "",
        "## Répartition par langue",
        "",
        "| Langue | Fichiers | Mots |",
        "| --- | ---: | ---: |",
    ]
    for lang in LANGUAGES:
        lang_rows = [r for r in rows if r["language"] == lang]
        lines.append(
            f"| {lang} | {len(lang_rows)} | {sum(int(r['word_count']) for r in lang_rows)} |"
        )
    lines += [
        "",
        "## Répartition par catégorie",
        "",
        "| Catégorie | Fichiers | Mots |",
        "| --- | ---: | ---: |",
    ]
    for cat, count in sorted(by_cat.items()):
        cat_words = sum(int(r["word_count"]) for r in rows if r["category"] == cat)
        lines.append(f"| {cat} | {count} | {cat_words} |")
    lines += ["", "## Profils de découpage", "", "| Profil | Fichiers |", "| --- | ---: |"]
    for chunk, count in sorted(by_chunk.items()):
        lines.append(f"| {chunk} | {count} |")

    by_format = Counter(r.get("document_format") or "non généré" for r in rows)
    lines += ["", "## Formats de livraison", "",
              "| Format | Fichiers |", "| --- | ---: |"]
    for fmt, count in sorted(by_format.items()):
        lines.append(f"| {fmt} | {count} |")

    STATS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"docs/reports/corpus_stats.md : généré ({total_words} mots)")


# ---------------------------------------------------------------- validate

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"\+212[\s.-]?[5-7][\s.-]?(?:\d[\s.-]?){8}")
IBAN_RE = re.compile(r"\bMA\d{2}[\s]?(?:\d{4}[\s]?){5,6}\b")
CARD_RE = re.compile(r"\b(?:\d[ -]?){15,18}\d\b")
FORBIDDEN = ("lorem ipsum", "todo:", "à compléter", "à remplir")

ALLOWED_EMAILS = {"support@novashop.ma", "retours@novashop.ma",
                  "contact@novashop.ma", "dpo@novashop.ma"}
ALLOWED_PHONES = {"+212 5 22 00 00 00", "+212 6 00 00 00 00",
                  "+212 5 22 00 00 01", "+212 5 37 00 00 02",
                  "+212 5 24 00 00 03", "+212 5 22 00 00 09"}


def validate() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    files = sorted(p for lang in LANGUAGES for p in (CORPUS_ROOT / lang).glob("*.md"))
    if not files:
        print("Aucun document trouvé.", file=sys.stderr)
        return 1

    docs: dict[tuple[str, str], dict] = {}
    for path in files:
        meta, body = parse_front_matter(path)
        name = path.name
        for key in REQUIRED_FRONT_MATTER:
            if not meta.get(key):
                errors.append(f"{name} : champ obligatoire manquant « {key} »")
        if not meta:
            continue
        doc_id = meta.get("doc_id", "")
        language = meta.get("language", "")
        if not name.startswith(doc_id):
            errors.append(f"{name} : doc_id « {doc_id} » incohérent avec le nom de fichier")
        if (doc_id, language) in docs:
            errors.append(f"{name} : doublon ({doc_id}, {language})")
        if language != path.parent.name:
            errors.append(f"{name} : langue « {language} » incohérente avec le dossier « {path.parent.name} »")
        if meta.get("category") not in CATEGORIES:
            errors.append(f"{name} : catégorie inconnue « {meta.get('category')} »")

        words = len(body.split())
        if words < 120:
            errors.append(f"{name} : document trop court ({words} mots, minimum 120)")
        if words > 1500:
            warnings.append(f"{name} : document long ({words} mots), vérifier le découpage")
        if meta.get("doc_type") == "faq" and body.count("\n## ") < 5:
            errors.append(f"{name} : document FAQ avec moins de 5 questions")
        if meta.get("doc_type") == "faq" and "?" not in body:
            errors.append(f"{name} : aucune question détectée")

        lowered = body.lower()
        for token in FORBIDDEN:
            if token in lowered:
                errors.append(f"{name} : marqueur de travail inachevé « {token} »")

        for email in EMAIL_RE.findall(body):
            if email.rstrip(".,;").lower() not in ALLOWED_EMAILS:
                warnings.append(f"{name} : adresse courriel non déclarée « {email} »")
        for phone in PHONE_RE.findall(body):
            if phone.strip(" .-") not in ALLOWED_PHONES:
                warnings.append(f"{name} : numéro non fictif potentiel « {phone} »")
        for pattern, label in ((IBAN_RE, "IBAN"), (CARD_RE, "numéro de carte")):
            if pattern.search(body):
                errors.append(f"{name} : {label} potentiel détecté")

        docs[(doc_id, language)] = {"path": path, "meta": meta, "body": body, "words": words}

    # doublons exacts et quasi-doublons, langue par langue
    for language in LANGUAGES:
        keys = sorted(k for k in docs if k[1] == language)
        seen: dict[str, str] = {}
        for key in keys:
            norm = normalize(docs[key]["body"])
            if norm in seen:
                errors.append(f"Contenu identique : {key[0]} et {seen[norm]} ({language})")
            seen[norm] = key[0]
        sh = {k: shingles(docs[k]["body"]) for k in keys}
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                score = jaccard(sh[a], sh[b])
                if score > 0.30:
                    warnings.append(f"Quasi-doublon ({score:.0%}) : {a[0]} / {b[0]} ({language})")

    # parité FR <-> EN
    by_id: dict[str, set[str]] = {}
    for doc_id, language in docs:
        by_id.setdefault(doc_id, set()).add(language)
    for doc_id, langs in sorted(by_id.items()):
        absent = set(LANGUAGES) - langs
        if absent:
            errors.append(f"{doc_id} : variante(s) manquante(s) {sorted(absent)}")
            continue
        fr, en = docs[(doc_id, "fr")], docs[(doc_id, "en")]
        for field in ("category", "doc_type", "version", "effective_date", "sensitivity"):
            if fr["meta"].get(field) != en["meta"].get(field):
                errors.append(f"{doc_id} : champ « {field} » divergent entre FR et EN")
        h_fr = fr["body"].count("\n## ")
        h_en = en["body"].count("\n## ")
        if h_fr != h_en:
            warnings.append(f"{doc_id} : structure divergente ({h_fr} sections FR / {h_en} EN)")
        n_fr = set(re.findall(r"\d+", fr["body"]))
        n_en = set(re.findall(r"\d+", en["body"]))
        diff = n_fr ^ n_en
        if diff:
            warnings.append(f"{doc_id} : valeurs numériques propres à une langue {sorted(diff)[:6]}")
        ratio = en["words"] / max(fr["words"], 1)
        if not 0.60 <= ratio <= 1.25:
            warnings.append(f"{doc_id} : ratio de longueur EN/FR = {ratio:.2f}")

    # cohérence manifeste <-> corpus
    if not MANIFEST.exists():
        errors.append("source_manifest.csv absent — lancer « build » d'abord")
    else:
        with MANIFEST.open(encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
        manifest_keys = {(r["doc_id"], r["language"]) for r in rows
                         if r["record_type"] == "knowledge_base_document"}
        missing = set(docs) - manifest_keys
        extra = manifest_keys - set(docs)
        if missing:
            errors.append(f"Documents absents du manifeste : {sorted(missing)}")
        if extra:
            errors.append(f"Lignes du manifeste sans fichier : {sorted(extra)}")
        for row in rows:
            if row["record_type"] != "knowledge_base_document":
                continue
            doc = docs.get((row["doc_id"], row["language"]))
            if not doc:
                continue
            if row["sha256"] != sha256(doc["path"]):
                errors.append(f"{row['doc_id']} : empreinte SHA-256 obsolète — relancer « build »")
            if row["word_count"] != str(doc["words"]):
                warnings.append(f"{row['doc_id']} : word_count désynchronisé")
            if row["index_in_rag"] == "yes" and row["license_status"] not in {
                "internal_verified", "verified", "presumed_public_domain"
            }:
                errors.append(f"{row['doc_id']} : document indexé avec licence non vérifiée")

    for line in warnings:
        print(f"[AVERTISSEMENT] {line}")
    for line in errors:
        print(f"[ERREUR] {line}")

    print(f"\n{len(docs)} documents contrôlés — "
          f"{len(errors)} erreur(s), {len(warnings)} avertissement(s)")
    return 1 if errors else 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build", "validate"])
    args = parser.parse_args()
    if args.command == "build":
        build()
        return 0
    return validate()


if __name__ == "__main__":
    raise SystemExit(main())
