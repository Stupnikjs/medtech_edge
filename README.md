# clinique_ai

Logiciel d'extraction d'informations depuis des documents scientifiques liés aux
études cliniques dans l'industrie pharmaceutique, en phase de développement.

## Objectif

Éclairer les investisseurs sur l'état actuel du pipeline clinique d'une biotech
ou d'un labo pharma donné, à partir de publications et documents sources.

## Premier challenge technique

Ingérer une publication ou un document — préalablement sélectionné par un
humain pour éviter le spam — via un agent IA qui extrait les données
pertinentes, puis les intègre dans la base de données.

## Pipeline

```
PubMed / autres sources
        │
        ▼
  DocumentBrut          (parsing brut : titre, abstract, date, source)
        │
        ▼
  Agent d'extraction    (LLM → JSON structuré selon schéma Pydantic)
        │
        ▼
  EtudeExtraite          (données validées : molécule, phase, endpoint,
        │                 p-value, type d'étude, niveau de confiance...)
        ▼
  Base de données
```

## Structure du projet

```
clinique_ai/
├── models/
│   ├── __init__.py
│   └── schemas.py          # DocumentBrut, EtudeExtraite, TypeSource, TypeEtude
├── pubmed_parser.py        # ingestion + parsing PubMed (Bio.Entrez)
├── agent_extraction.py     # agent d'extraction LLM (via litellm)
└── README.md
```

## Schémas de données

- **`DocumentBrut`** — sortie du parsing, avant extraction IA (titre, abstract
  brut, date, source, payload complet pour traçabilité).
- **`EtudeExtraite`** — sortie de l'agent IA : molécule, cible thérapeutique,
  mécanisme d'action, phase, statut, taille d'échantillon, randomisation,
  double aveugle, endpoint primaire, p-value, `type_etude` (RCT,
  observationnelle, méta-analyse, préclinique, autre), et un score de
  confiance obligatoire (`confiance_extraction`) avec justification
  (`raisonnement`).

## Setup

### 1. Dépendances Python

```bash
pip install biopython pydantic python-dotenv --break-system-packages
```

### 2. Clé API PubMed (NCBI)

Gratuite, sans restriction gênante — sert juste à l'identification et
augmente le rate limit de 3 à 10 req/s.

```bash
export NCBI_API_KEY="ta_clé_ncbi"
```

### 3. Agent d'extraction — modèle LLM local via Ollama

Aucune clé API, aucun rate limit : tourne entièrement en local.

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve &
ollama pull qwen2.5:7b-instruct
```

Le modèle est configurable via variable d'environnement (`EXTRACTION_MODEL`),
grâce à `litellm` qui découple le code du provider — un changement de modèle
ne touche à rien d'autre dans le pipeline.

### 4. Test du pipeline complet

```bash
python pubmed_parser.py       # test du parsing seul
python agent_extraction.py    # test parsing + extraction IA
```

## État actuel

- [x] Parsing PubMed → `DocumentBrut` (avec gestion d'erreurs réseau,
      throttling, abstract structuré par section, extraction de date)
- [x] Schémas Pydantic de validation (`DocumentBrut`, `EtudeExtraite`)
- [x] Agent d'extraction découplé du modèle LLM (`litellm`)
- [ ] Insertion en base de données
- [ ] Interface / restitution pour l'investisseur