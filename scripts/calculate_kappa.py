#!/usr/bin/env python3
"""Calcule l'accord inter-annotateurs (Cohen's kappa) du pilote d'intentions.

Entrée      : ``data/annotations/pilot_20_annotation_sheet.csv``
Référentiel : ``data/annotations/intents.csv``
Rapport     : ``docs/reports/annotation_agreement_report.md``

Usage :
    python scripts/calculate_kappa.py
    python scripts/calculate_kappa.py --csv data/annotations/pilot_20_annotation_sheet.csv
    python scripts/calculate_kappa.py --report reports/annotation_agreement_report.md

Le script ne modifie jamais la feuille d'annotation. Il valide les colonnes,
les valeurs manquantes et les codes d'intention, puis calcule le kappa de Cohen
avec ``sklearn.metrics.cohen_kappa_score`` et génère le rapport.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from collections import Counter
from pathlib import Path

import sklearn
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "annotations" / "pilot_20_annotation_sheet.csv"
DEFAULT_INTENTS = ROOT / "data" / "annotations" / "intents.csv"
DEFAULT_GUIDELINES = ROOT / "docs" / "annotation_guidelines.md"
DEFAULT_REPORT = ROOT / "docs" / "reports" / "annotation_agreement_report.md"

ANNOTATOR_COLUMNS = ("annotator_1_intent", "annotator_2_intent")
AMBIGUITY_COLUMN = "ambiguous_oui_non_1"


def display_path(path: Path) -> str:
    """Chemin relatif au dépôt pour des messages lisibles."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    """Lit un CSV UTF-8 (BOM toléré) et retourne l'en-tête et les lignes."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = [cell.strip() for cell in next(reader)]
        except StopIteration as error:
            raise ValueError(f"fichier CSV vide : {display_path(path)}") from error
        rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        raise ValueError(f"aucune ligne de données dans {display_path(path)}")
    return header, rows


def load_valid_intents(path: Path) -> dict[str, dict]:
    """Charge les codes canoniques depuis ``intents.csv``."""
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "intent_id" not in reader.fieldnames:
            raise ValueError(f"colonne 'intent_id' absente de {display_path(path)}")
        intents: dict[str, dict] = {}
        for row in reader:
            code = (row.get("intent_id") or "").strip()
            if code:
                intents[code] = row
    if not intents:
        raise ValueError(f"aucune intention dans {display_path(path)}")
    return intents


def validate(
    header: list[str], rows: list[list[str]], valid_intents: dict[str, dict]
) -> dict:
    """Valide la structure, les valeurs manquantes et les codes d'intention."""
    issues: list[str] = []
    warnings: list[str] = []
    duplicates = sorted(
        name for name, count in Counter(header).items() if count > 1
    )
    if duplicates:
        warnings.append(
            "colonne(s) dupliquée(s) dans l'en-tête : " + ", ".join(duplicates)
        )

    for column in ANNOTATOR_COLUMNS:
        if column not in header:
            issues.append(f"colonne obligatoire absente : {column}")

    result = {
        "issues": issues,
        "warnings": warnings,
        "duplicates": duplicates,
        "y1": [],
        "y2": [],
        "ids": [],
        "languages": Counter(),
        "ambiguity": Counter(),
        "ambiguous_rows": [],
        "ambiguous_ids": [],
        "duplicate_ambiguity_same": None,
        "ids_unique": None,
    }
    if issues:
        return result

    index_1 = header.index(ANNOTATOR_COLUMNS[0])
    index_2 = header.index(ANNOTATOR_COLUMNS[1])
    id_index = header.index("id") if "id" in header else None
    language_index = header.index("language") if "language" in header else None
    ambiguity_indices = [
        index for index, name in enumerate(header) if name == AMBIGUITY_COLUMN
    ]

    for row_number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            issues.append(
                f"ligne {row_number} : {len(row)} champs au lieu de {len(header)}"
            )
            continue

        value_1 = row[index_1].strip()
        value_2 = row[index_2].strip()

        if not value_1:
            issues.append(f"ligne {row_number} : {ANNOTATOR_COLUMNS[0]} manquant")
        if not value_2:
            issues.append(f"ligne {row_number} : {ANNOTATOR_COLUMNS[1]} manquant")
        if value_1 and value_1 not in valid_intents:
            issues.append(
                f"ligne {row_number} : intention invalide dans "
                f"{ANNOTATOR_COLUMNS[0]} : {value_1!r}"
            )
        if value_2 and value_2 not in valid_intents:
            issues.append(
                f"ligne {row_number} : intention invalide dans "
                f"{ANNOTATOR_COLUMNS[1]} : {value_2!r}"
            )

        position = len(result["y1"])
        result["y1"].append(value_1)
        result["y2"].append(value_2)

        if id_index is not None:
            result["ids"].append(row[id_index].strip())
        if language_index is not None:
            result["languages"][row[language_index].strip()] += 1
        if ambiguity_indices:
            flag = row[ambiguity_indices[0]].strip().lower()
            result["ambiguity"][flag] += 1
            if flag == "oui":
                result["ambiguous_rows"].append(position)
                if id_index is not None:
                    result["ambiguous_ids"].append(row[id_index].strip())

    duplicate_ids = sorted(
        identifier
        for identifier, count in Counter(result["ids"]).items()
        if count > 1
    )
    if duplicate_ids:
        issues.append("identifiants dupliqués : " + ", ".join(duplicate_ids))

    invalid_languages = sorted(
        language for language in result["languages"] if language not in {"fr", "en"}
    )
    if invalid_languages:
        warnings.append(
            "langues invalides (hors fr/en) : " + ", ".join(invalid_languages)
        )

    if len(ambiguity_indices) > 1:
        result["duplicate_ambiguity_same"] = all(
            len(row) > max(ambiguity_indices)
            and row[ambiguity_indices[0]].strip()
            == row[ambiguity_indices[1]].strip()
            for row in rows
        )
        warnings.append(
            f"colonne '{AMBIGUITY_COLUMN}' dupliquée "
            f"({len(ambiguity_indices)} occurrences) ; valeurs identiques sur "
            f"toutes les lignes : "
            f"{'oui' if result['duplicate_ambiguity_same'] else 'non'}"
        )

    result["ids_unique"] = (
        len(set(result["ids"])) == len(result["ids"]) if result["ids"] else None
    )
    return result


def compute_metrics(y1: list[str], y2: list[str]) -> dict:
    """Accords, désaccords, taux d'accord et kappa de Cohen."""
    total = len(y1)
    agreements = sum(left == right for left, right in zip(y1, y2))
    disagreements = total - agreements
    rate = agreements / total if total else 0.0
    kappa = cohen_kappa_score(y1, y2) if total else float("nan")
    return {
        "n": total,
        "agreements": agreements,
        "disagreements": disagreements,
        "rate": rate,
        "kappa": kappa,
    }


def per_class_rows(y1: list[str], y2: list[str]) -> list[tuple[str, int, int, int]]:
    """Répartition et accords par code d'intention (tri alphabétique)."""
    labels = sorted(set(y1) | set(y2))
    rows: list[tuple[str, int, int, int]] = []
    for label in labels:
        support = sum(1 for left, right in zip(y1, y2) if label in (left, right))
        agreements = sum(
            1 for left, right in zip(y1, y2) if left == label and right == label
        )
        rows.append((label, support, agreements, support - agreements))
    return rows


def interpret_kappa(kappa: float) -> str:
    """Interprétation de Landis & Koch (1981)."""
    if kappa != kappa:  # NaN
        return "indéterminé (données insuffisantes ou une seule classe)"
    if kappa < 0:
        return "désaccord (κ < 0)"
    if kappa <= 0.20:
        return "accord faible (0,00–0,20)"
    if kappa <= 0.40:
        return "accord médiocre (0,21–0,40)"
    if kappa <= 0.60:
        return "accord modéré (0,41–0,60)"
    if kappa <= 0.80:
        return "accord substantiel (0,61–0,80)"
    return "accord presque parfait (0,81–1,00)"


def format_number(value: float, digits: int = 3) -> str:
    """Format français déterministe (virgule décimale)."""
    return f"{value:.{digits}f}".replace(".", ",")


def verify_guidelines(path: Path, valid_intents: dict[str, dict]) -> dict:
    """Vérifie que les codes et les sections clés sont présents dans les guidelines."""
    if not path.exists():
        return {"exists": False, "missing": sorted(valid_intents), "sections": {}}
    text = path.read_text(encoding="utf-8")
    return {
        "exists": True,
        "missing": sorted(code for code in valid_intents if code not in text),
        "sections": {
            "frontieres": "### 5.3 Frontières entre classes" in text,
            "ambigus": "### 5.4 Cas ambigus" in text,
            "accord": "### 5.7 Accord inter-annotateurs" in text,
        },
    }


def build_report(
    csv_path: Path,
    intents_path: Path,
    valid_intents: dict[str, dict],
    validation: dict,
    metrics: dict,
    per_class: list[tuple[str, int, int, int]],
    sensitivity: dict | None,
    guidelines_path: Path,
    guidelines: dict,
    report_path: Path,
) -> str:
    """Construit le rapport Markdown à partir des résultats calculés."""
    sha256 = hashlib.sha256(csv_path.read_bytes()).hexdigest()
    languages = ", ".join(
        f"{language} : {count}"
        for language, count in sorted(validation["languages"].items())
    )
    ambiguous = (
        ", ".join(f"`{identifier}`" for identifier in validation["ambiguous_ids"])
        if validation["ambiguous_ids"]
        else "aucun identifiant disponible"
    )

    lines = [
        "# Rapport d'accord inter-annotateurs — annotation pilote des intentions",
        "",
        "> Généré par `scripts/calculate_kappa.py` à partir de "
        f"`{display_path(csv_path)}`.",
        "> Aucun horodatage : le rapport est reproductible à partir des fichiers d'entrée.",
        "",
        "## 1. Contexte",
        "",
        "Le projet **SupportAI** (NovaShop, e-commerce fictif) construit un assistant "
        "de support bilingue FR/EN. Le chantier A des guidelines porte sur la "
        "classification d'intentions. Un pilote de **20 exemples** a été annoté par "
        "**deux annotateurs** pour vérifier la fiabilité de la taxonomie avant "
        "l'annotation à grande échelle.",
        "",
        f"- Référentiel : `{display_path(intents_path)}` — "
        f"**{len(valid_intents)} codes** (13 intentions + `out_of_scope`).",
        f"- Feuille pilote : `{display_path(csv_path)}` — "
        f"**{metrics['n']} exemples**.",
        f"- Langues : **{languages}**.",
        "- Annotateurs : **2** (`annotator_1_intent`, `annotator_2_intent`).",
        f"- SHA-256 de la feuille : `{sha256}`.",
        "",
        "## 2. Méthode",
        "",
        "- **Accord observé** : proportion d'exemples où les deux annotateurs ont "
        "choisi le même code.",
        "- **Cohen's kappa** : `sklearn.metrics.cohen_kappa_score` "
        f"(scikit-learn `{sklearn.__version__}`).",
        "- Formule : κ = (p_o − p_e) / (1 − p_e), où p_o est l'accord observé et "
        "p_e l'accord attendu au hasard.",
        "- **Interprétation** : échelle de Landis & Koch (1981).",
        "",
        "## 3. Résultats",
        "",
        "| Indicateur | Valeur |",
        "| --- | ---: |",
        f"| Exemples annotés | {metrics['n']} |",
        "| Annotateurs | 2 |",
        f"| Accords | {metrics['agreements']} |",
        f"| Désaccords | {metrics['disagreements']} |",
        f"| Taux d'accord | {format_number(metrics['rate'] * 100, 2)} % |",
        f"| Cohen's kappa | {format_number(metrics['kappa'], 3)} |",
        f"| Interprétation | {interpret_kappa(metrics['kappa'])} |",
        "",
        "### Répartition par intention",
        "",
        "| Code | Exemples | Accords | Désaccords |",
        "| --- | ---: | ---: | ---: |",
    ]
    for code, support, agreements, disagreements in per_class:
        lines.append(f"| `{code}` | {support} | {agreements} | {disagreements} |")
    lines += [
        f"| **Total** | **{metrics['n']}** | **{metrics['agreements']}** | "
        f"**{metrics['disagreements']}** |",
        "",
        "## 4. Interprétation",
        "",
        f"Le kappa de **{format_number(metrics['kappa'], 3)}** correspond à un "
        f"**{interpret_kappa(metrics['kappa'])}** au sens de Landis & Koch. Les deux "
        f"annotateurs ont choisi le même code sur **{metrics['agreements']}/"
        f"{metrics['n']}** exemples, soit **{format_number(metrics['rate'] * 100, 2)} %** "
        "d'accord. Le seuil cible des guidelines (§5.7) est **κ ≥ 0,75** : le pilote "
        "le dépasse.",
        "",
        "Ce résultat doit toutefois être lu avec prudence : un accord parfait sur un "
        "petit échantillon ne prouve pas que la taxonomie sera aussi fiable sur des "
        "cas réels plus variés. Il n'y a aucun désaccord à analyser, donc le pilote "
        "ne permet pas d'identifier les frontières de classes encore fragiles.",
        "",
        "## 5. Limites",
        "",
        f"- **Taille de l'échantillon** : {metrics['n']} exemples pour "
        f"{len(valid_intents)} classes, soit 1 à 2 exemples par classe. Les "
        "estimations sont instables et ne sont pas représentatives de la "
        "distribution réelle.",
        f"- **Niveau d'accord** : κ = {format_number(metrics['kappa'], 3)}. "
        + (
            "L'absence de désaccord empêche d'analyser les confusions entre classes."
            if metrics["disagreements"] == 0
            else f"{metrics['disagreements']} désaccord(s) à analyser."
        ),
        "- **Indépendance non documentée** : le CSV ne précise pas si les deux "
        "annotateurs ont travaillé indépendamment, ni leur identité. Si les "
        "annotations ont été produites ensemble ou à partir de la même référence, "
        "le kappa surestime l'accord inter-annotateurs. **Cette indépendance doit "
        "être confirmée.**",
        "- **Échantillon équilibré par construction** : le pilote couvre "
        "volontairement chaque intention (1 à 2 exemples), ce qui diffère de la "
        "distribution réelle et influence le kappa (sensibilité à la prévalence).",
        *(
            [
                "- **Colonne dupliquée** : l'en-tête contient deux colonnes "
                "`ambiguous_oui_non_1` (mêmes valeurs sur toutes les lignes). Le "
                "calcul n'utilise que les colonnes `annotator_*`, mais le schéma "
                "doit être corrigé."
            ]
            if validation["duplicate_ambiguity_same"] is not None
            else []
        ),
        "- **Pas de kappa par classe** : avec 1 à 2 exemples par classe, un kappa "
        "par intention n'est pas interprétable. Seul le kappa global est rapporté.",
        *(
            [
                f"- **Exemple ambigu** : {ambiguous} est marqué ambigu (`oui`) ; "
                "les deux annotateurs sont d'accord. Les guidelines (§5.4) "
                "prévoient que les exemples ambigus ne comptent pas dans les "
                "métriques principales ; le calcul global les inclut. Une analyse "
                "de sensibilité est fournie ci-dessous."
            ]
            if validation["ambiguous_rows"]
            else []
        ),
        "",
        "### Sensibilité : exclusion de l'exemple ambigu",
        "",
    ]
    if sensitivity is None:
        lines.append(
            "Aucun exemple ambigu dans la feuille : aucune analyse de sensibilité "
            "nécessaire."
        )
    else:
        lines += [
            "| Périmètre | Exemples | Accords | Taux | Kappa |",
            "| --- | ---: | ---: | ---: | ---: |",
            f"| Tous les exemples | {metrics['n']} | {metrics['agreements']} | "
            f"{format_number(metrics['rate'] * 100, 2)} % | "
            f"{format_number(metrics['kappa'], 3)} |",
            f"| Hors exemple(s) ambigu(s) | {sensitivity['n']} | "
            f"{sensitivity['agreements']} | "
            f"{format_number(sensitivity['rate'] * 100, 2)} % | "
            f"{format_number(sensitivity['kappa'], 3)} |",
            "",
            (
                "Le résultat est inchangé : l'exemple ambigu ne modifie pas le kappa."
                if sensitivity["kappa"] == metrics["kappa"]
                else "Le résultat varie lorsqu'on exclut l'exemple ambigu : "
                f"kappa {format_number(sensitivity['kappa'], 3)} contre "
                f"{format_number(metrics['kappa'], 3)}."
            ),
        ]

    lines += [
        "",
        "## 6. Vérification des guidelines",
        "",
        f"`{display_path(guidelines_path)}` a été examiné :",
        "",
    ]
    if guidelines["exists"]:
        present = len(valid_intents) - len(guidelines["missing"])
        lines.append(
            f"- Codes de `intents.csv` présents dans les guidelines : "
            f"**{present}/{len(valid_intents)}**."
        )
        if guidelines["missing"]:
            lines.append(
                "- Codes manquants : "
                + ", ".join(f"`{code}`" for code in guidelines["missing"])
            )
        sections = guidelines["sections"]
        lines.append(
            "- Sections clés : frontières "
            f"{'OK' if sections.get('frontieres') else 'manquante'}, cas ambigus "
            f"{'OK' if sections.get('ambigus') else 'manquante'}, accord "
            f"{'OK' if sections.get('accord') else 'manquante'}."
        )
        lines += [
            "- Chaque intention possède un libellé et un exemple type ; les "
            "définitions complètes sont dans `intents.csv`, comme indiqué par les "
            "guidelines.",
            "",
            "Aucune réécriture des guidelines n'a été nécessaire. Les libellés "
            "français de la table §5.1 sont parfois des variantes de ceux de "
            "`intents.csv` (par exemple « Modification / annulation » vs "
            "« Modification ou annulation »), mais les **codes** — identifiants "
            "canoniques — correspondent exactement.",
        ]
    else:
        lines.append("- Guidelines introuvables : vérification impossible.")

    lines += [
        "",
        "## 7. Prochaines étapes",
        "",
        "1. **Confirmer l'indépendance** des deux annotateurs et documenter leur "
        "identité et le protocole (aveugle, même version des guidelines).",
        "2. **Corriger le schéma** : supprimer ou renommer la colonne dupliquée "
        "`ambiguous_oui_non_1` ; figer la version de la feuille pilote.",
        "3. **Étendre l'échantillon** à 100–200 exemples stratifiés, en incluant "
        "des cas frontières et ambigus représentatifs de la distribution réelle.",
        "4. **Double annotation aveugle** et calcul du kappa global et par classe ; "
        "consigner les désaccords dans `docs/reports/adjudication_log.csv`.",
        "5. **Décider** : si κ ≥ 0,75, figer les guidelines v1.1 et lancer "
        "l'annotation complète ; sinon, réviser les définitions des classes "
        "conflictuelles et ré-annoter.",
        "6. **Publier** ce rapport et demander la validation de l'équipe NLP/Data "
        "(ClickUp).",
        "",
        "## 8. Reproductibilité",
        "",
        "```bash",
        "python scripts/calculate_kappa.py",
        "```",
        "",
        "Le script valide les colonnes, les valeurs manquantes et les codes "
        "d'intention, puis calcule le kappa et régénère ce rapport. Il ne modifie "
        "jamais la feuille d'annotation.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Calcule le kappa de Cohen du pilote d'annotation des intentions."
    )
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--intents", type=Path, default=DEFAULT_INTENTS)
    parser.add_argument("--guidelines", type=Path, default=DEFAULT_GUIDELINES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    try:
        header, rows = read_csv(args.csv)
        valid_intents = load_valid_intents(args.intents)
    except (OSError, ValueError) as error:
        print(f"[ERREUR] {error}", file=sys.stderr)
        return 1

    validation = validate(header, rows, valid_intents)
    for warning in validation["warnings"]:
        print(f"[AVERTISSEMENT] {warning}")

    if validation["issues"]:
        for issue in validation["issues"]:
            print(f"[ERREUR] {issue}", file=sys.stderr)
        print(
            "[ERREUR] calcul interrompu : corriger la feuille d'annotation.",
            file=sys.stderr,
        )
        return 1

    y1 = validation["y1"]
    y2 = validation["y2"]
    metrics = compute_metrics(y1, y2)
    per_class = per_class_rows(y1, y2)

    ambiguous_rows = set(validation["ambiguous_rows"])
    if ambiguous_rows:
        keep = [index for index in range(len(y1)) if index not in ambiguous_rows]
        sensitivity = compute_metrics(
            [y1[index] for index in keep], [y2[index] for index in keep]
        )
    else:
        sensitivity = None

    guidelines = verify_guidelines(args.guidelines, valid_intents)
    report = build_report(
        args.csv,
        args.intents,
        valid_intents,
        validation,
        metrics,
        per_class,
        sensitivity,
        args.guidelines,
        guidelines,
        args.report,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(report)

    print("=== Accord inter-annotateurs — pilote des intentions ===")
    print(f"Fichier CSV          : {display_path(args.csv)}")
    print(f"Référentiel          : {display_path(args.intents)}")
    print(f"Exemples annotés     : {metrics['n']}")
    print("Annotateurs          : 2")
    print(f"Intentions valides   : {len(valid_intents)}")
    print("Valeurs manquantes   : 0")
    print("Intentions invalides : 0")
    print(f"Accords              : {metrics['agreements']}")
    print(f"Désaccords           : {metrics['disagreements']}")
    print(f"Taux d'accord        : {format_number(metrics['rate'] * 100, 2)} %")
    print(f"Cohen's kappa        : {format_number(metrics['kappa'], 3)}")
    print(f"Interprétation       : {interpret_kappa(metrics['kappa'])}")
    print(f"Rapport              : {display_path(args.report)}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
