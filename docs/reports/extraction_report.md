# Rapport d'extraction documentaire

> Généré par `scripts/extract_documents.py`. Ne pas modifier à la main.

- Documents sources : **74** couples (doc_id, langue)
- Enregistrements extraits : **522**
- Caractères extraits : **212 377**
- Mots extraits : **34 903**
- Échecs : **0**

## Enregistrements par format

| Format | Enregistrements |
| --- | ---: |
| csv | 48 |
| docx | 274 |
| json | 70 |
| jsonl | 74 |
| pdf | 56 |

## Extracteurs utilisés

| Extracteur | Fichiers |
| --- | ---: |
| faq-csv | 4 |
| faq-json | 6 |
| faq-jsonl | 6 |
| ooxml-stdlib | 30 |
| pypdf | 28 |

## Contrôles

| Contrôle | Résultat |
| --- | --- |
| Enregistrements vides | 0 |
| Enregistrements avec accents | 291 / 522 |
| Enregistrements FR avec accents | 260 / 261 |
| Textes strictement dupliqués | 0 |
| Enregistrements nécessitant un OCR | 0 |

## Couverture texte extrait / source

- Ratio minimal : **0.92**
- Ratio médian : **0.97**
- Documents sous 85 % : **0**

## Nettoyage appliqué

| Opération | Occurrences |
| --- | ---: |
| espaces insécables remplacés | 0 |
| caractères invisibles supprimés | 0 |
| ligatures normalisées | 0 |
| caractères de contrôle supprimés | 0 |
| espaces multiples réduits | 0 |
| espaces de fin de ligne supprimés | 0 |
| lignes vides réduites | 0 |
| textes modifiés | 0 |

## Documents nécessitant un OCR

Aucun : tous les PDF contiennent une couche de texte exploitable.

Sortie : `data/processed/extracted/documents.jsonl`
