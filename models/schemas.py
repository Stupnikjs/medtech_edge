"""
Schémas Pydantic — validation des données AVANT insertion SQL.
Toute donnée parsée doit passer par un de ces modèles.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any
from datetime import date
from enum import Enum


class TypeSource(str, Enum):
    pubmed = "pubmed"
    clinicaltrials = "clinicaltrials"
    epar = "epar"
    fda = "fda"
    communique_presse = "communique_presse"
    sec_edgar = "sec_edgar"


class DocumentBrut(BaseModel):
    """Sortie du parsing — avant extraction IA."""
    model_config = ConfigDict(arbitrary_types_allowed=True)

    type_source: TypeSource
    url: Optional[str] = None
    titre: str
    texte_brut: str = Field(..., min_length=50)  # rejette les extractions vides/quasi-vides
    date_publication: Optional[date] = None
    # Any plutôt que dict : Entrez.read() renvoie des objets biopython custom
    # (DictionaryElement/ListElement), pas des dicts natifs. Gardé pour traçabilité/debug,
    # pas destiné à être requêté directement.
    payload_brut: Any


class TypeEtude(str, Enum):
    """
    Classification par design d'étude — orthogonale à la phase.
    Sert à filtrer par poids de preuve : un RCT phase 3 et un case report
    n'ont pas le même poids pour un investisseur, même sujet clinique.
    """
    rct = "rct"                        # essai randomisé contrôlé (le gold standard)
    observationnelle = "observationnelle"  # cohorte, cas-témoins, real-world evidence
    meta_analyse = "meta_analyse"      # inclut aussi revues systématiques
    preclinique = "preclinique"        # in vitro, animal, avant essais humains
    autre = "autre"                    # case report, éditorial, protocole seul, etc.


class EtudeExtraite(BaseModel):
    """Sortie de l'agent IA — ce qu'il doit produire pour une étude."""
    nct_id: Optional[str] = None
    type_etude: TypeEtude
    
    # --- Rattachement molécule (nouveau) ---
    molecule_nom: str
    molecule_nom_code: Optional[str] = None
    molecule_id_correspondance: Optional[int] = None   # ID trouvé si rattachement
    action_molecule: ActionMolecule
    candidats_evalues: Optional[List[int]] = None       # IDs proposés en pré-filtrage, pour audit
    
    cible_therapeutique: Optional[str] = None
    mecanisme_action: Optional[str] = None
    
    # --- Design de l'essai ---
    phase: Optional[str] = None
    statut: Optional[str] = None
    taille_echantillon: Optional[int] = None
    nb_bras: Optional[int] = None                        # nouveau : essai à 2, 3+ bras
    randomise: Optional[bool] = None
    double_aveugle: Optional[bool] = None
    comparateur_type: Optional[str] = None
    comparateur_nom: Optional[str] = None                # nouveau : nom précis du comparateur (ex: "sémaglutide" pas juste "autre_molecule")
    duree_semaines: Optional[int] = None                 # nouveau : durée de suivi, important pour comparer essais entre eux
    
    # --- Population ---
    population_cible: Optional[str] = None               # nouveau : ex: "adultes diabète type 2, IMC 27-40"
    ligne_traitement: Optional[str] = None                # nouveau : first-line, second-line, add-on
    
    # --- Résultats ---
    endpoint_primaire: Optional[str] = None
    endpoint_atteint: Optional[bool] = None
    p_value: Optional[float] = None
    ic95_min: Optional[float] = None                     # nouveau, manquant jusqu'ici dans ce schéma
    ic95_max: Optional[float] = None
    endpoints_secondaires: Optional[List[str]] = None    # nouveau : liste, même sans détail chiffré
    
    # --- Sécurité ---
    effets_indesirables_graves_pct: Optional[float] = None  # nouveau, manquait dans ce schéma
    arrets_pour_effets_indesirables_pct: Optional[float] = None  # nouveau : signal fort de tolérance
    
    # --- Statut réglementaire (utile pour la probabilité de succès) ---
    designation_speciale: Optional[str] = None            # nouveau : "fast_track", "breakthrough_therapy", etc. (FDA)
    
    # --- Méta / traçabilité ---
    confiance_extraction: float = Field(..., ge=0.0, le=1.0)
    raisonnement: str