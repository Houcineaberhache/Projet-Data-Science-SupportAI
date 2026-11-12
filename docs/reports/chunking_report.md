# Rapport de découpage / Chunking report

> Généré par `scripts/chunk_corpus.py`. Ne pas modifier à la main.
> Aucun horodatage : deux exécutions produisent un rapport identique.

## 1. Synthèse

- Chunks : **678** (339 FR + 339 EN)
- Documents : **74** (37 FR + 37 EN)
- Sections `##` : **678** (339 FR + 339 EN)
- Chunks scindés (`part` non nul) : **0**
- Chunks exclus (`too_short`) : **6** (3 FR + 3 EN)
- Chunks avec tableau : **88**
- Chunks avec référence documentaire : **124**
- Chunks avec montant en MAD : **80**
- Longueur des chunks (mots) : min **5**, médiane **37.0**, moyenne **46.4**, max **221**

## 2. Volumes par langue et catégorie

| Langue | Catégorie | Documents | Chunks | Mots | Tokens estimés |
| --- | --- | ---: | ---: | ---: | ---: |
| fr | faq | 8 | 96 | 3 175 | 4 281 |
| fr | internal_operations | 5 | 40 | 2 270 | 3 066 |
| fr | legal_summaries | 4 | 34 | 1 751 | 2 365 |
| fr | policies | 10 | 94 | 5 137 | 6 934 |
| fr | procedures | 4 | 36 | 1 806 | 2 438 |
| fr | product_guides | 6 | 39 | 2 237 | 3 019 |
| **fr** | **Total** | **37** | **339** | **16 376** | **22 103** |
| en | faq | 8 | 96 | 2 878 | 3 878 |
| en | internal_operations | 5 | 40 | 2 148 | 2 902 |
| en | legal_summaries | 4 | 34 | 1 573 | 2 121 |
| en | policies | 10 | 94 | 4 688 | 6 322 |
| en | procedures | 4 | 36 | 1 699 | 2 292 |
| en | product_guides | 6 | 39 | 2 097 | 2 831 |
| **en** | **Total** | **37** | **339** | **15 083** | **20 346** |
| **Total** | | **74** | **678** | **31 459** | **42 449** |

## 3. Distribution des tailles

| Langue | 0–14 | 15–30 | 31–60 | 61–100 | 101–200 | 201–300 | > 300 | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fr | 4 | 82 | 167 | 63 | 22 | 1 | 0 | 339 |
| en | 6 | 113 | 153 | 49 | 17 | 1 | 0 | 339 |
| **Total** | 10 | 195 | 320 | 112 | 39 | 2 | 0 | **678** |

La distribution compte les chunks par `word_count` du texte seul. La règle `too_short` inclut le titre de section et s'applique au couple FR/EN : certains chunks de 0–14 mots restent indexés si leur contrepartie linguistique est substantielle (voir section 5).

## 4. Chunks scindés

Aucun chunk scindé : aucune section ne dépasse 300 mots (maximum observé : 221 mots).

## 5. Chunks exclus (`too_short`)

| Chunk ID | Langue | Mots | Titre de section | Raison |
| --- | --- | ---: | --- | --- |
| `POL-01#c9` | en | 10 | 9. Contact | `too_short` |
| `POL-01#c9` | fr | 12 | 9. Contact | `too_short` |
| `REG-02#c8` | en | 7 | 8. Monitoring | `too_short` |
| `REG-02#c8` | fr | 6 | 8. Suivi | `too_short` |
| `REG-03#c9` | en | 5 | 9. Monitoring | `too_short` |
| `REG-03#c9` | fr | 5 | 9. Suivi | `too_short` |

La décision est prise au niveau du couple FR/EN du même `chunk_id` : un chunk n'est exclu que si ses deux variantes sont courtes. Un chunk court dans une seule langue n'est donc pas exclu si sa contrepartie est substantielle ; la parité d'indexation est conservée.

## 6. Couverture du texte source

Le corps du fichier Markdown est compté après le front matter, avant retrait du titre, du bloc fictif et des titres de section. Les chunks contiennent le préambule éventuel dans leur première section.

| Langue | Mots corps | Mots chunks | Écart | Titre du document | Avertissement fictif | Titres de section (`##`) | Non classé |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fr | 18 680 | 16 376 | 2 304 | 266 | 27 | 2 011 | 0 |
| en | 17 238 | 15 083 | 2 155 | 239 | 29 | 1 887 | 0 |
| **Total** | **35 918** | **31 459** | **4 459** | **505** | **56** | **3 898** | **0** |

L'écart observé est de **2 304 mots en FR** et **2 155 mots en EN**, soit environ 2 250 mots par langue ; le total des deux langues est **4 459 mots**. Les catégories expliquent tout l'écart observé : titre `#`, avertissement fictif (bloc et séparateur) et titres de section `##`. La colonne « Non classé » doit rester à zéro ; si elle ne l'est pas, l'écart est signalé sans être corrigé.

## 7. Méthode

- Une section `##` = un chunk ; les sous-titres `###` restent dans le texte de leur section.
- Au-delà de 300 mots, découpage par paragraphes avec suffixe `.1`, `.2`, … et `part` renseigné ; les tableaux Markdown restent entiers.
- `chunk_id` = `<DOC_ID>#c<n>` où `n` est l'ordre de la section ; la clé unique est `(chunk_id, language)`.
- `word_count` compte les mots du texte du chunk (hors titre de section) ; `text_for_embedding` ajoute le titre du document et le titre de section.
- `audience` = `customer` si `sensitivity` vaut `public`, sinon `internal` ; `index_in_rag` vient du manifeste et passe à `false` pour `too_short`.
- `amounts_mad` normalise les espaces, trie numériquement et conserve les montants avant « MAD » ; `cross_refs` trie les références documentaires.
- Aucun horodatage, aucun embedding, aucune dépendance externe.
