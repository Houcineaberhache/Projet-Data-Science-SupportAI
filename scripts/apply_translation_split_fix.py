"""Applique la correction de fuite de traduction pour le gel v1.1.

La correction est volontairement minimale : aucun texte, aucune étiquette et
aucune annotation n'est modifié. Seul le champ ``split`` des exemples du groupe
``TR-0001`` est réécrit pour regrouper les deux traductions dans le même split.

La source canonique ``data/annotations/intent_dataset.jsonl`` reste intacte :
elle est la source du gel v1.0. La sortie est une source dérivée versionnée,
``data/annotations/intent_dataset_v1.1.jsonl``, utilisée uniquement par v1.1.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "annotations" / "intent_dataset.jsonl"
TARGET = ROOT / "data" / "annotations" / "intent_dataset_v1.1.jsonl"
SPLITS = ("train", "val", "test")

GROUP = {
    "group_id": "TR-0001",
    "target_split": "test",
    "members": ["INT-0421", "INT-0445"],
    "reason": (
        "Meme intention warranty_claim, meme nombre 14 mois et meme propos "
        "batterie/garantie en FR et en EN."
    ),
}

ANNOTATION_SOURCES = {
    # Train non sondé : étiquette issue de la cible privée, sans annotation publique.
    "INT-0421": "data/annotations/_private/intent_candidates.jsonl",
    "INT-0445": "data/annotations/blind/annotate_aya_done.csv",
    "INT-0223": "data/annotations/blind/annotate_aya_done.csv",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> tuple[list[bytes], list[dict]]:
    raw_lines = [line for line in path.read_bytes().splitlines(keepends=True) if line.strip()]
    rows = [json.loads(line.decode("utf-8")) for line in raw_lines]
    return raw_lines, rows


def replace_split(raw: bytes, old: str, new: str) -> bytes:
    needle = f'"split": "{old}"'.encode("utf-8")
    replacement = f'"split": "{new}"'.encode("utf-8")
    if raw.count(needle) != 1:
        raise ValueError(f"Champ split introuvable ou ambigu : {raw[:120]!r}")
    return raw.replace(needle, replacement, 1)


def main() -> int:
    raw_lines, rows = load_jsonl(SOURCE)
    by_id = {row["id"]: row for row in rows}
    target_split = GROUP["target_split"]
    members = GROUP["members"]

    if target_split not in SPLITS:
        raise ValueError(f"Split cible inconnu : {target_split}")
    missing = [identifier for identifier in members if identifier not in by_id]
    if missing:
        raise ValueError(f"Exemples absents de la source : {missing}")
    selected = [by_id[identifier] for identifier in members]
    if len({row["intent"] for row in selected}) != 1:
        raise ValueError("Les exemples du groupe n'ont pas la même intention")
    if len({row["language"] for row in selected}) != len(selected):
        raise ValueError("Le groupe n'est pas multilingue")
    if len({row["split"] for row in selected}) == 1:
        raise ValueError("Les exemples du groupe sont déjà dans le même split")

    for identifier, relative_path in ANNOTATION_SOURCES.items():
        annotation_source = ROOT / relative_path
        if identifier not in annotation_source.read_text(encoding="utf-8-sig"):
            raise ValueError(f"{identifier} absent de {relative_path}")

    changes = []
    for index, row in enumerate(rows):
        if row["id"] not in members:
            continue
        original = row["split"]
        raw_lines[index] = replace_split(raw_lines[index], original, target_split)
        updated = json.loads(raw_lines[index].decode("utf-8"))
        if updated["split"] != target_split:
            raise ValueError(f"Split non appliqué pour {row['id']}")
        changes.append(
            {
                "id": row["id"],
                "original_split": original,
                "new_split": target_split,
                "annotation_source": ANNOTATION_SOURCES[row["id"]],
            }
        )

    TARGET.write_bytes(b"".join(raw_lines))

    _, written = load_jsonl(TARGET)
    counts = Counter(row["split"] for row in written)
    print(f"Source v1.0 : {SOURCE.relative_to(ROOT)} — {sha256_file(SOURCE)}")
    print(f"Source v1.1 : {TARGET.relative_to(ROOT)} — {sha256_file(TARGET)}")
    for change in changes:
        print(
            f"  {change['id']}: {change['original_split']} -> {change['new_split']} "
            f"({change['annotation_source']})"
        )
    print("Effectifs v1.1 : " + ", ".join(f"{split}={counts[split]}" for split in SPLITS))
    print(f"Total : {len(written)} exemples")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
