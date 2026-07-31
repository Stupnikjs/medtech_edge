# Architecture du projet — Veille pipeline diabète (B2B investisseurs/labos)

## 1. Vision du produit

Outil B2B destiné aux investisseurs biotech et équipes Business Development de labos pharma,
permettant de suivre les molécules en développement clinique sur le diabète, avec pour chaque
molécule : sa phase actuelle, une probabilité de succès pour passer au stade suivant, et le
niveau de saturation concurrentielle de son segment thérapeutique.

Positionnement volontaire : outil d'**information factuelle et scientifique**, jamais de
recommandation financière ("investis/n'investis pas"). L'utilisateur croise les données
lui-même pour former sa décision.

---

## 2. Flux de données global

```
Sources externes (PubMed, ClinicalTrials.gov, EPAR, FDA, communiqués)
        │
        ▼
Filtrage / pré-sélection (type de publication, présence NCT ID, récence)
        │
        ▼
Parsing (Python : lxml/biopython, pymupdf, trafilatura)
        │
        ▼
Rattachement à une molécule (agent IA : recherche existante ou création)
        │
        ▼
Extraction structurée (agent IA : phase, endpoints, résultats, sécurité)
        │
        ├──► Moteur de probabilité de succès (statistique, basé sur historique + ajustements)
        │
        └──► Moteur de saturation de marché (agrégation transversale par cible thérapeutique)
                │
                ▼
        API REST (FastAPI) ← lit uniquement les tables agrégées/calculées
                │
                ▼
        Dashboard / contenu public (LinkedIn, Substack)
```

---

## 3. Répartition des rôles

| Tâche | Responsable |
|---|---|
| Identifier les molécules diabète à suivre | Toi (veille stratégique) |
| Valider créations / trancher doublons ambigus | Toi (au début, décisions à faible confiance) |
| Rechercher et parser les documents liés à une molécule | Agent d'extraction |
| Extraire les champs structurés (phase, endpoints, résultats) | Agent d'extraction |
| Calculer la probabilité de succès | Moteur statistique dédié |
| Calculer la saturation de marché | Moteur d'agrégation dédié |
| Interpréter et publier l'analyse finale | Toi |

---

## 4. Schéma de données (types principaux)

- **Molécule** — identité, cible, mécanisme, aire thérapeutique, sponsor (texte libre), phase actuelle
- **Phase** — un essai clinique par entrée (design, endpoints, résultats, sécurité)
- **Document** — sources brutes (PubMed, CT.gov, PDF), texte, embedding vectoriel, traçabilité
- **Market** — agrégation calculée par cible thérapeutique (nb concurrents par stade, niveau de saturation)
- **Taux de transition historiques** — table de référence pour calculer la probabilité de succès
- **Agent decisions** — log d'audit de toutes les actions de l'agent (création, fusion, extraction, confiance, raisonnement)

---

## 5. Fiche molécule (objet central de l'API)

```json
{
  "molecule": {
    "id": 42,
    "nom": "...",
    "nom_code": "...",
    "cible_therapeutique": "...",
    "mecanisme_action": "...",
    "aire_therapeutique": "diabète type 2",
    "sponsor": "...",
    "phase_actuelle": "phase3",

    "probabilite_succes": {
      "valeur": 62,
      "phase_visee": "phase3_vers_approbation",
      "nb_etudes_utilisees": 4,
      "detail": { "prior_historique": 45, "ajustements": [] },
      "date_calcul": "..."
    },

    "saturation_marche": {
      "cible_therapeutique": "GLP-1 receptor",
      "niveau": "eleve",
      "nb_concurrents_meme_stade": 6,
      "nb_concurrents_total": 14,
      "date_calcul": "..."
    },

    "etudes": ["..."],
    "sources": ["..."]
  }
}
```

---

## 6. Endpoints API

```
GET  /molecules                      liste avec filtres (aire, phase, sponsor)
GET  /molecules/{id}                 fiche complète
GET  /molecules/{id}/etudes          détail des essais liés
GET  /molecules/{id}/probabilite     détail du calcul de probabilité
GET  /markets                        liste des segments avec saturation
GET  /markets/{cible_therapeutique}  détail saturation + molécules du segment
POST /molecules                      ajouter une molécule à suivre (déclenche l'ingestion)
```

---

## 7. Stack technique retenue

| Composant | Choix | Justification |
|---|---|---|
| Base de données | PostgreSQL + pgvector | Structuré et vectoriel dans un seul système |
| API | FastAPI (Python) | Cohérent avec le pipeline d'extraction, doc auto-générée |
| Parsing PubMed | biopython (Entrez) + lxml | API officielle, gestion XML native |
| Parsing ClinicalTrials.gov | requests (API v2 JSON) | API ouverte, pas de clé requise |
| Parsing PDF | pymupdf (fitz) | Rapide, bonne extraction texte + tableaux |
| Parsing HTML | trafilatura | Extraction propre d'articles (hors nav/pubs) |
| Extraction structurée | API Claude (function calling) | Précision sur données scientifiques, JSON structuré |
| Validation de schéma | Pydantic | Rejet strict des données incomplètes/malformées |

---

## 8. Garde-fous qualité

- Aucune donnée n'entre en base sans validation Pydantic préalable
- Chaque extraction IA porte un score de `confiance` — sous un seuil, validation humaine requise
- Table `agent_decisions` : audit trail complet (action, ancienne/nouvelle valeur, raisonnement, confiance)
- `methode_version` sur les tables de scores pour permettre le recalcul sans perdre l'historique
- Séparation stricte : score scientifique / probabilité de succès / saturation marché — jamais fusionnés en un score financier unique

---

## 9. Statut du projet

- [x] Choix du segment (diabète) et du positionnement (B2B, information factuelle)
- [x] Schéma de données (molécules, phases, documents, markets)
- [x] Modules de parsing (PubMed, ClinicalTrials.gov, PDF)
- [ ] Connexion SQL (insertion des documents parsés)
- [ ] Agent de rattachement molécule + extraction structurée
- [ ] Moteur de calcul de probabilité de succès
- [ ] Moteur de calcul de saturation de marché
- [ ] API REST (FastAPI)
- [ ] Premier contenu public (LinkedIn/Substack) pour construire la crédibilité
