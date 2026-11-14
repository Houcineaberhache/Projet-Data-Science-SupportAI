# RAG evaluation set — build report

> Deterministic report. No timestamp is stored.

## Files

| File | Rows | Content |
| --- | ---: | --- |
| `data/annotations/rag_eval.jsonl` | 140 | Questions, gold chunks, relevance and reference answers |
| `data/annotations/robustness_eval.jsonl` | 35 | Robustness cases, outside the 140-question set |
| `data/annotations/rag_eval_with_passages.jsonl` | 140 | Same rows plus `gold_passages` copied from the corpus |
| `docs/reports/rag_eval_review.md` | 39 | 25 sampled questions + all 14 out-of-corpus questions |

## Distribution

| Question type | FR | EN | Total |
| --- | ---: | ---: | ---: |
| `lexical` | 28 | 14 | 42 |
| `semantic` | 40 | 16 | 56 |
| `procedural` | 8 | 20 | 28 |
| `out_of_corpus` | 8 | 6 | 14 |
| **Total** | **84** | **56** | **140** |

- Multi-chunk questions (relevance 2 + 1): **17** (threshold: 15)
- Questions whose reference answer contains a number: **88** (threshold: 20)
- Questions with one deliberate light typo: **21** (~15 % style target)

## Coverage by customer document

Primary document = first gold document of an answerable question. The 14 out-of-corpus questions have no document.

| Document | Questions |
| --- | ---: |
| `FAQ-01` | 4 |
| `FAQ-02` | 4 |
| `FAQ-03` | 4 |
| `FAQ-04` | 5 |
| `FAQ-05` | 5 |
| `FAQ-06` | 4 |
| `FAQ-07` | 4 |
| `FAQ-08` | 4 |
| `POL-01` | 5 |
| `POL-02` | 5 |
| `POL-03` | 5 |
| `POL-04` | 5 |
| `POL-05` | 4 |
| `POL-06` | 4 |
| `POL-07` | 4 |
| `POL-08` | 4 |
| `POL-09` | 4 |
| `POL-10` | 4 |
| `PRO-01` | 4 |
| `PRO-02` | 4 |
| `PRO-03` | 4 |
| `PRO-04` | 4 |
| `CAT-01` | 4 |
| `CAT-02` | 4 |
| `CAT-03` | 4 |
| `CAT-04` | 4 |
| `CAT-05` | 4 |
| `CAT-06` | 4 |
| `OPS-04` | 4 |
| `REG-04` | 4 |
| **Total answerable** | **126** |

## Validation checks

| # | Check | Result |
| ---: | --- | --- |
| 1 | 1. Structure, ids, types, languages and field values | **OK** |
| 2 | 2. Gold chunks exist, are customer/indexable and docs agree | **OK** |
| 3 | 3. answerable=false => empty/null; answerable=true => relevance 2 | **OK** |
| 4 | 4. Every number in gold_answer is grounded in a gold chunk | **OK** |
| 5 | 5. Question != section title; semantic questions avoid title keywords | **OK** |
| 6 | 6. No exact duplicate and no quasi-duplicate (Jaccard >= 0.8) | **OK** |
| 7 | 7. Out-of-corpus questions: three nearest chunks shown for human control | **OK** |

All seven checks are expected to be OK before `build` writes this report.

## Out-of-corpus questions and nearest chunks

The three nearest customer/indexable chunks are shown by word overlap. They are controls, not gold evidence: none of them answers the question.

### RET-0127 [fr]

**Question:** Proposez-vous un service de reprise pour mon ancien téléphone ?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.059 | `REG-04#c2` | 2. Hébergement |
| 0.050 | `POL-03#c8` | 8. Adresse incorrecte |
| 0.045 | `FAQ-06#c8` | Puis-je commander un produit non référencé sur le site ? |

### RET-0128 [fr]

**Question:** Puis-je acheter une extension de garantie de 24 mois ?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.111 | `FAQ-05#c8` | La réparation est-elle garantie ? |
| 0.100 | `CAT-06#c5` | 5. Conditions de vente |
| 0.091 | `CAT-02#c5` | 5. Extension et entretien |

### RET-0129 [fr]

**Question:** Faites-vous des remises pour les étudiants ?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.000 | `CAT-01#c1` | 1. Gammes disponibles |
| 0.000 | `CAT-01#c2` | 2. Critères de choix |
| 0.000 | `CAT-01#c3` | 3. Contenu de la boîte |

### RET-0130 [fr]

**Question:** Puis-je commander par téléphone ?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.158 | `FAQ-07#c10` | Puis-je commander sans fournir mon numéro de téléphone ? |
| 0.111 | `FAQ-01#c1` | Comment passer une commande ? |
| 0.105 | `FAQ-06#c8` | Puis-je commander un produit non référencé sur le site ? |

### RET-0131 [fr]

**Question:** Proposez-vous un emballage cadeau ?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.059 | `FAQ-08#c3` | Puis-je cumuler plusieurs codes promo ? |
| 0.050 | `FAQ-03#c10` | Puis-je utiliser un code promo et une carte cadeau ensemble ? |
| 0.048 | `CAT-04#c4` | 4. Conditions de vente |

### RET-0132 [fr]

**Question:** Puis-je payer avec PayPal ou Apple Pay ?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.065 | `FAQ-03#c3` | Puis-je payer en plusieurs fois ? |
| 0.053 | `FAQ-08#c3` | Puis-je cumuler plusieurs codes promo ? |
| 0.050 | `FAQ-08#c10` | Puis-je obtenir le remboursement d'un produit acheté en promotion ? |

### RET-0133 [fr]

**Question:** Combien coûte la réparation d'un écran cassé ?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.107 | `FAQ-05#c2` | La garantie couvre-t-elle une chute ou un écran cassé ? |
| 0.091 | `FAQ-02#c2` | Combien coûte la livraison ? |
| 0.087 | `FAQ-05#c5` | Combien de temps prend une réparation ? |

### RET-0134 [fr]

**Question:** Puis-je obtenir une facture en anglais ?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.111 | `FAQ-05#c11` | Que faire si je perds ma facture ? |
| 0.111 | `FAQ-08#c10` | Puis-je obtenir le remboursement d'un produit acheté en promotion ? |
| 0.107 | `FAQ-03#c6` | Puis-je obtenir une facture au nom de mon entreprise ? |

### RET-0135 [en]

**Question:** Do you offer a referral bonus for existing customers?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.050 | `POL-10#c9` | 9. Promotional dispute |
| 0.048 | `FAQ-06#c8` | Can I order a product that is not listed on the site? |
| 0.048 | `FAQ-08#c11` | What should I do if a promotion was not applied? |

### RET-0136 [en]

**Question:** Can I hire a laptop for a week?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.033 | `CAT-04#c3` | 3. Usage precautions |
| 0.018 | `CAT-04#c5` | 5. Frequently asked questions |
| 0.000 | `CAT-01#c1` | 1. Available ranges |

### RET-0137 [en]

**Question:** Do you offer a price-match guarantee against other retailers?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.054 | `POL-10#c2` | 2. General promo code rules |
| 0.048 | `FAQ-08#c10` | Can I get a refund for a product bought on promotion? |
| 0.045 | `FAQ-08#c4` | Does the promo code apply to discounted products? |

### RET-0138 [en]

**Question:** Can I get a tax refund for purchases made as a tourist?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.105 | `FAQ-08#c10` | Can I get a refund for a product bought on promotion? |
| 0.083 | `FAQ-03#c6` | Can I get an invoice in my company's name? |
| 0.083 | `FAQ-04#c12` | Can I return a product bought in store? |

### RET-0139 [en]

**Question:** Do you provide a loaner device while mine is repaired?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.045 | `FAQ-05#c7` | What happens if the product cannot be repaired? |
| 0.043 | `CAT-01#c6` | 6. Care advice |
| 0.042 | `CAT-06#c5` | 5. Sales conditions |

### RET-0140 [en]

**Question:** Can I pre-order a product that is out of stock?

| Overlap | Chunk | Heading |
| ---: | --- | --- |
| 0.190 | `FAQ-06#c1` | How do I know if a product is in stock? |
| 0.136 | `FAQ-06#c7` | Will an out-of-stock product be restocked? |
| 0.111 | `FAQ-08#c10` | Can I get a refund for a product bought on promotion? |

## What was not done

- `reviewed_by` is still `null` for every row. Aya performs the final human review.
- No retrieval metric (Recall@k, MRR, nDCG) was computed: this task builds the evaluation set, it does not run a retriever.
- The contradictory and prompt-injection robustness categories are out of scope for this task.
