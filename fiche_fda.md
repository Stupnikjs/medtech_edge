# Fiche de référence — Codes FDA 510(k)

Référence pour parser/interpréter les données `openFDA Device 510(k) Clearances`.

## 1. Les champs de ton échantillon

| Champ | Description |
|---|---|
| `k_number` | Identifiant unique de la soumission (ex: K053654). Le préfixe = année de dépôt approx. |
| `applicant` | Fabricant/déposant. **Champ clé pour le mapping vers un ticker coté.** |
| `decision_date` | Date de la décision FDA. |
| `decision_code` / `decision_description` | Résultat de la review (voir section 2). |
| `clearance_type` | Traditional / Special / Abbreviated (voie de dépôt). |
| `product_code` | Code produit 3 lettres = catégorie réglementaire précise du dispositif. |
| `advisory_committee` | Panel médical qui classe le produit (code, voir section 3). |
| `advisory_committee_description` | Nom complet du panel. |
| `review_advisory_committee` | Panel qui a réellement fait la review (peut différer du panel de classification si le device a changé de catégorie). |
| `third_party_flag` | Y/N — review faite par un organisme tiers accrédité plutôt que la FDA directement. |
| `statement_or_summary` | "Summary" = résumé public détaillé dispo. "Statement" = à demander au fabricant. |
| `expedited_review_flag` | Y/N/vide — review accélérée accordée. |

## 2. Codes de décision (`decision_code`)

Le seul code que tu croises dans ton échantillon est **SESE** (Substantially Equivalent — Standard). Mais la liste complète officielle FDA est plus riche, utile pour ton filtrage de signal :

### Substantiellement équivalent (device autorisé)
| Code | Signification |
|---|---|
| `SE` | Substantially Equivalent (le cas standard) |
| `SD` | Équivalent, avec médicament associé |
| `SK` | Équivalent — Kit |
| `SU` | Équivalent avec limitations |
| `SN` | Équivalent pour certaines indications seulement |
| `SP` | Équivalent — surveillance post-marché requise |
| `SI` | Équivalent — mise sur le marché après inspection |
| `SA` | Équivalent — en attente d'approbation device |
| `SF` | Équivalent — en attente de futures politiques |
| `ST` | Équivalent — soumis à obligation de tracking |
| `SW` | Équivalent — en attente d'approbation médicament |
| `KD` | Équivalent — Kit avec médicament |
| `PT` | Équivalent — soumis à tracking & surveillance post-marché |
| `RN` | Rescinde une décision de non-équivalence antérieure |
| `PR` | Équivalent — proposition de rescision |

### Non équivalent (device rejeté) — **signal négatif fort pour ta stratégie**
| Code | Signification |
|---|---|
| `NE` | **Not Substantially Equivalent** — rejet, le device ne peut pas être commercialisé via 510(k) |
| `SC` | Non équivalent — ne peut pas être mis sur le marché |
| `SL` | Non équivalent — étiquetage non conforme |
| `FB` | Nécessite une PMA (voie plus lourde) au lieu d'un 510(k) |
| `RE` | Rescinde une équivalence précédemment accordée |
| `UD` / `UO` / `OD` | Impossible de déterminer l'équivalence (dossier incomplet) |
| `UR` | Non équivalent — données jugées non fiables |

### Autres codes administratifs
| Code | Signification |
|---|---|
| `WD` | Retiré par le demandeur |
| `DD` | Doublon/supprimé |
| `EX` | Exempté par réglementation |
| `NA` | Pas réglementé activement |
| `ND` | N'est pas considéré comme un dispositif médical |
| `TR` | Dispositif transitoire |
| `K4` | Lettre de clôture émise |

**À retenir pour ton parser** : `SE`/`SESE` = bruit de fond (c'est 90%+ des cas, peu de valeur en soi). Les vrais signaux à surveiller : `NE`, `SC`, `FB`, `RE`, `WD` — bien plus rares et potentiellement corrélés à des mouvements de cours (rejet, pivot forcé vers PMA, retrait volontaire).

## 3. Panels / Advisory Committee (`advisory_committee`)

Liste complète des 19 panels CDRH :

| Code | Nom complet |
|---|---|
| `AN` | Anesthesiology |
| `CV` | Cardiovascular |
| `CH` | Clinical Chemistry |
| `DE` | Dental |
| `EN` | Ear, Nose, Throat |
| `GU` | Gastroenterology, Urology |
| `HO` | General Hospital |
| `HE` | Hematology |
| `IM` | Immunology |
| `MG` | Medical Genetics |
| `MI` | Microbiology |
| `NE` | Neurology |
| `OB` | Obstetrics/Gynecology |
| `OP` | Ophthalmic |
| `OR` | Orthopedic |
| `PA` | Pathology |
| `PM` | Physical Medicine |
| `RA` | Radiology |
| `SU` | General, Plastic Surgery |
| `TX` | Clinical Toxicology |

*Note : `NE` apparaît à la fois comme code décision (Not Substantially Equivalent) et comme code panel (Neurology) — attention à ne jamais confondre les deux colonnes dans ton parsing.*

Pour ta thèse d'investissement (small/mid cap MedTech), les panels les plus pertinents sont probablement `CV` (cardiovasculaire), `OR` (orthopédie), `NE` (neuro), `OP` (ophtalmique) — segments à forte innovation et forte proportion de pure-players cotés, contrairement à `CH`/`HE`/`PA` qui sont dominés par du diagnostic in vitro générique (IVD) avec beaucoup de bruit historique (comme les entrées 1977-1987 dans ton échantillon).

## 4. `product_code` — le champ le plus granulaire

Il n'y a pas de "petite liste" ici : la FDA en maintient plusieurs milliers, chacun définissant précisément une catégorie de device (classe de risque I/II/III, indication, règlement associé). Ce n'est pas une énumération à mémoriser — il faut cross-référencer avec la **FDA Product Classification Database** (accessible via l'API openFDA `/device/classification`) pour obtenir, pour chaque `product_code` : nom du device générique, classe de risque, regulation number.

Concrètement pour ton pipeline : `product_code` est la clé de jointure vers cette table annexe — je te recommande de l'ingérer une fois en local (table de lookup statique, elle change peu) plutôt que d'appeler l'API à chaque enregistrement.

## 5. Ce qui manque encore pour ton parser

- **Mapping `applicant` → ticker coté** : aucune donnée FDA ne fait ce lien nativement. À construire toi-même (fuzzy match sur raison sociale + base manuelle pour les cas ambigus).
- **Table `product_code` → description/classe de risque** : à récupérer une fois via `/device/classification`.
- **Filtrage temporel** : vu la profondeur historique (1976→2026), un `decision_date` récent (ex: 2 ans) éliminera l'essentiel du bruit pour ton use case retail.