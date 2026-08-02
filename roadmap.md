# Roadmap d'intégration — Outil de scoring MedTech

## Contexte du projet

Outil d'agrégation de données réglementaires FDA (dispositifs médicaux) transformées en score de robustesse, destiné à deux publics : investisseurs retail (score par ticker) et fonds VC/PE (due diligence par dispositif).

**Principe validé** : parsing + agrégation pur data engineering, sans expertise clinique nécessaire en v1. L'architecture sépare la donnée brute (`RawClearanceRecord`) de la couche produit (`Device`, `Company`, scores, `ClearanceEvent`).

---

## Phase 0 — Fondations (déjà fait)

- [x] Parser `openFDA device/510k` avec pagination, filtres (date, applicant, product_code, advisory_committee)
- [x] Modèles de données définis : `RawClearanceRecord`, `Device`, `Company`, `DeviceScore`, `ClearanceEvent`, `TickerScore`
- [x] Fonction de scoring composite pondéré (5 composants)

---

## Phase 1 — Compléter les sources de données réglementaires

**Objectif** : couvrir tous les pathways de clearance FDA, pas seulement le 510(k).

| Tâche | Endpoint | Alimente |
|---|---|---|
| Parser PMA (même structure que 510k) | `device/pma` | `clearance_pathway_score`, `risk_class_score` |
| Parser De Novo | `device/denovo` | `clearance_pathway_score` (signal d'innovation) |
| Parser recalls | `device/enforcement` | `recall_history_score` |
| Parser établissements | `device/registrationlisting` | désambiguïsation filiales/maison-mère |

**Critère de sortie de phase** : les 3 pathways de clearance (510k/PMA/De Novo) et les recalls sont dans une base commune, avec un `source` distinct par type.

---

## Phase 2 — Mapping company → ticker (goulot d'étranglement)

**Objectif** : résoudre `applicant_raw` (texte brut FDA) vers une entité `Company` canonique avec ticker.

1. Récupérer `company_tickers.json` (SEC, gratuit, mis à jour quotidiennement)
2. Construire un premier mapping par correspondance exacte (nom nettoyé/normalisé)
3. Fuzzy matching (ex: `rapidfuzz`) pour les variantes ("Medtronic Inc" vs "Medtronic Vascular")
4. Table de correspondance manuelle pour les cas ambigus restants (probablement <100 entreprises pour couvrir 80% du volume — la distribution est très concentrée sur quelques gros filers)
5. Marquer `is_investable = False` pour tout ce qui ne matche aucun ticker (filiales de boîtes privées, sous-traitants)

**Critère de sortie de phase** : >80% des `RawClearanceRecord` des 12 derniers mois rattachés à une `Company` avec ticker connu, pour l'univers des ~200-300 tickers medtech identifiés.

**Risque identifié** : matching approximatif peut mal attribuer une clearance à la mauvaise société. Prévoir un flag `mapping_confidence` sur chaque `Company` pour distinguer mapping certain vs probable.

---

## Phase 3 — Materiality score

**Objectif** : pondérer chaque dispositif selon son importance réelle pour l'entreprise (un produit phare ≠ un accessoire mineur).

1. Intégrer SEC EDGAR full-text search (API gratuite)
2. Compter les mentions du `device_name` / nom de gamme produit dans les 10-K et 8-K des 12 derniers mois
3. Normaliser en score 0-100 (ex: percentile de fréquence de mention vs autres produits de la même entreprise)

**Critère de sortie de phase** : `materiality_score` calculé et non figé à une valeur par défaut pour au moins les tickers small/mid-cap suivis.

---

## Phase 4 — Adverse events (MAUDE) — la plus complexe

**Objectif** : enrichir `recall_history_score` avec un signal de sécurité plus fin que les seuls recalls.

1. Parser `device/event` (MAUDE)
2. **Filtrer impérativement** sur les rapports sérieux (décès, hospitalisation, mise en jeu du pronostic vital, incapacité permanente) — sans ce filtre le signal est noyé
3. Normaliser par volume d'usage du dispositif (un produit très diffusé génère mécaniquement plus de rapports sans que ce soit un problème de sécurité) — proxy possible : nombre de 510(k)/PMA liés au même `product_code` comme approximation de la diffusion

**Critère de sortie de phase** : score de sécurité qui ne pénalise pas artificiellement les dispositifs les plus utilisés.

*Peut être fait après le lancement du MVP — non bloquant pour shipper.*

---

## Phase 5 — Agrégation et exposition produit

**Objectif** : passer du score par dispositif au score par ticker, exposé via API/frontend.

1. Implémenter `TickerScore.composite_score()` avec vraies données (déjà codé, à brancher)
2. Génération automatique des `headline` pour `ClearanceEvent` (template simple, pas de LLM nécessaire au début)
3. Historisation (`score_trend`) — snapshot mensuel minimum, aligné sur la fréquence de mise à jour openFDA
4. Endpoint API : `GET /tickers/{ticker}/score`, `GET /tickers/{ticker}/events`, `GET /devices/{device_id}`

**Critère de sortie de phase** : MVP consultable — un utilisateur peut chercher un ticker et voir son score + les événements récents qui l'expliquent.

---

## Phase 6 — Industrialisation

- Scheduler mensuel (cron) aligné sur la fréquence de mise à jour d'openFDA
- Monitoring des échecs de parsing (changements de format FDA)
- Versioning de la méthodologie de score (`score_version`) pour pouvoir comparer/expliquer les évolutions de notation dans le temps
- (Optionnel, hors scope MVP) Extension EUDAMED pour couverture Europe — statut de l'API à revérifier au moment venu

---

## Hors scope volontaire pour le MVP

- Lecture/interprétation d'essais cliniques pivots (pertinent seulement pour Classe III à fort enjeu, à traiter en revue manuelle ciblée plus tard, pas en automatisation)
- Détection automatique du "predicate creep" (nécessite jugement clinique)
- Couverture Europe (EUDAMED) — à évaluer une fois le MVP US validé
