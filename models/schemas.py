"""
Modeles de donnees - Outil de scoring MedTech (version simple)
=================================================================

Meme structure que models.py, mais en Python classique :
classes normales, pas de dataclasses/enums/typing avance.
Plus verbeux a ecrire, mais plus simple a lire et a modifier.
"""

import uuid
from datetime import datetime


# ---------------------------------------------------------------------------
# 1. RawClearanceRecord - miroir brut de la donnee FDA, jamais modifie
# ---------------------------------------------------------------------------

class RawClearanceRecord:
    def __init__(self, k_number, device_name, applicant_raw, decision_date,
                 decision_code, clearance_type, product_code, advisory_committee, source):
        self.k_number = k_number
        self.device_name = device_name
        self.applicant_raw = applicant_raw
        self.decision_date = decision_date          # objet date
        self.decision_code = decision_code
        self.clearance_type = clearance_type         # "Traditional" / "Special" / "Abbreviated"
        self.product_code = product_code
        self.advisory_committee = advisory_committee
        self.source = source                          # "openFDA_510k" / "openFDA_pma" / "openFDA_denovo"
        self.ingested_at = datetime.now()
    

# ---------------------------------------------------------------------------
# 2. Device - entite normalisee, dedupliquee
# ---------------------------------------------------------------------------

class Device:
    def __init__(self, canonical_name, normalized_name,  product_code, device_class, advisory_committee, company_id):
        self.device_id = str(uuid.uuid4())
        self.canonical_name = canonical_name
        self.normalized_name = normalized_name
        self.product_code = product_code
        self.device_class = device_class              # "I" / "II" / "III"
        self.advisory_committee = advisory_committee
        self.company_id = company_id
        self.clearance_history = []                    # liste de RawClearanceRecord
        self.status = "active"                          # "active" / "discontinued" / "recalled"

    def first_clearance_date(self):
        if not self.clearance_history:
            return None
        return min(r.decision_date for r in self.clearance_history)

    def latest_clearance_date(self):
        if not self.clearance_history:
            return None
        return max(r.decision_date for r in self.clearance_history)


# ---------------------------------------------------------------------------
# 3. Company - entite canonique resolue depuis les applicant_raw
# ---------------------------------------------------------------------------

class Company:
    def __init__(self, canonical_name, normalized_name, ticker=None, exchange=None, market_cap_tier="private"):
        self.company_id = str(uuid.uuid4())
        self.canonical_name = canonical_name
        self.normalized_name = normalized_name,
        self.known_aliases = []                         # ex: "Medtronic Inc", "Medtronic PLC"
        self.ticker = ticker
        self.exchange = exchange                         # "NASDAQ", "EURONEXT"...
        self.market_cap_tier = market_cap_tier            # "micro" / "small" / "mid" / "large" / "private"
        self.devices = []                                  # liste de Device

    def is_investable(self):
        """Un investisseur retail ne peut agir que sur du cote."""
        return self.ticker is not None


# ---------------------------------------------------------------------------
# 4. DeviceScore - score atomique, versionne
# ---------------------------------------------------------------------------

# Ponderation par defaut - facile a changer sans toucher au reste du code
DEFAULT_SCORE_WEIGHTS = {
    "clearance_pathway_score": 0.20,
    "speed_score": 0.15,
    "risk_class_score": 0.15,
    "recall_history_score": 0.20,
    "materiality_score": 0.30,
}


def compute_composite_score(components, weights=None):
    """Combine les composants du score en une note unique 0-100.

    `components` est un dict avec les 5 cles ci-dessus.
    `weights` permet de surcharger la ponderation par defaut,
    utile pour comparer plusieurs versions de methodologie.
    """
    w = weights or DEFAULT_SCORE_WEIGHTS
    total = 0
    for key, weight in w.items():
        total += components.get(key, 0) * weight
    return round(total, 2)


class DeviceScore:
    def __init__(self, device_id, components, score_version="v1.0", confidence=1.0):
        self.device_id = device_id
        self.components = components                     # dict: clearance_pathway_score, speed_score, etc.
        self.score_version = score_version
        self.confidence = confidence                       # data manquante = confiance plus basse
        self.computed_at = datetime.now()
        self.composite_score = compute_composite_score(components)


# ---------------------------------------------------------------------------
# 5. ClearanceEvent - couche "produit", separee du raw record
# ---------------------------------------------------------------------------

class ClearanceEvent:
    def __init__(self, device_id, company_id, event_type, event_date, headline, score_delta=0.0):
        self.event_id = str(uuid.uuid4())
        self.device_id = device_id
        self.company_id = company_id
        self.event_type = event_type                       # "510k_cleared" / "pma_approved" / "recall_issued"
        self.event_date = event_date
        self.headline = headline                             # genere automatiquement pour affichage
        self.score_delta = score_delta                        # impact sur le TickerScore
        self.source_record = None                              # RawClearanceRecord d'origine


# ---------------------------------------------------------------------------
# 6. TickerScore - agregation, ce que voit le retail investor
# ---------------------------------------------------------------------------

class TickerScore:
    def __init__(self, company_id, ticker):
        self.company_id = company_id
        self.ticker = ticker
        self.contributing_devices = []      # liste de dicts: {"device_id", "weight", "device_score"}
        self.score_trend = []                 # liste de dicts: {"as_of", "composite_score"}
        self.top_catalysts = []                # liste de ClearanceEvent
        self.computed_at = datetime.now()

    def add_device_contribution(self, device_id, weight, device_score):
        self.contributing_devices.append({
            "device_id": device_id,
            "weight": weight,
            "device_score": device_score,
        })

    def composite_score(self):
        """Moyenne ponderee des scores dispositifs actifs contribuant au ticker."""
        if not self.contributing_devices:
            return 0.0
        total_weight = sum(c["weight"] for c in self.contributing_devices)
        if total_weight == 0:
            return 0.0
        weighted_sum = sum(
            c["device_score"].composite_score * c["weight"] for c in self.contributing_devices
        )
        return round(weighted_sum / total_weight, 2)


# ---------------------------------------------------------------------------
# Exemple d'utilisation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import date

    company = Company(
        canonical_name="Penumbra Inc",
        ticker="PEN",
        exchange="NYSE",
        market_cap_tier="mid",
    )
    company.known_aliases = ["Penumbra", "Penumbra Inc."]

    raw = RawClearanceRecord(
        k_number="K243051",
        device_name="Indigo Aspiration System",
        applicant_raw="Penumbra Inc.",
        decision_date=date(2025, 6, 12),
        decision_code="SESE",
        clearance_type="Traditional",
        product_code="DXX",
        advisory_committee="cv",
        source="openFDA_510k",
    )

    device = Device(
        canonical_name="Indigo Aspiration System",
        product_code="DXX",
        device_class="II",
        advisory_committee="cv",
        company_id=company.company_id,
    )
    device.clearance_history.append(raw)
    company.devices.append(device)

    components = {
        "clearance_pathway_score": 70.0,
        "speed_score": 85.0,
        "risk_class_score": 60.0,
        "recall_history_score": 90.0,
        "materiality_score": 95.0,   # produit phare de l'entreprise
    }
    device_score = DeviceScore(device_id=device.device_id, components=components)

    ticker_score = TickerScore(company_id=company.company_id, ticker=company.ticker)
    ticker_score.add_device_contribution(device.device_id, weight=1.0, device_score=device_score)

    print(f"Composite score dispositif : {device_score.composite_score}")
    print(f"Composite score ticker ({ticker_score.ticker}) : {ticker_score.composite_score()}")
