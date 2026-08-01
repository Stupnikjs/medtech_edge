  """
Parsing des publications PubMed.
Utilise Bio.Entrez (biopython) pour interroger l'API et récupérer le XML,
puis extrait le texte brut structuré.

Installation : pip install biopython --break-system-packages
"""

from dotenv import load_dotenv

import os
import time
import logging
from urllib.error import HTTPError, URLError
from http.client import IncompleteRead

from Bio import Entrez
from typing import List, Optional
from models.schemas import DocumentBrut, TypeSource
from datetime import date


load_dotenv()
logger = logging.getLogger(__name__)

# Entrez.email/api_key : globals biopython → injectées dans l'URL des requêtes
Entrez.email = "ton.email@example.com"
Entrez.api_key = os.environ.get("NCBI_API_KEY")

# Rate limit NCBI : 3 req/s sans clé, 10 req/s avec
DELAI_ENTRE_REQUETES = 0.11 if Entrez.api_key else 0.34

if not Entrez.api_key:
    logger.warning("NCBI_API_KEY absente — throttling à 3 req/s au lieu de 10.")


def _appel_entrez(fonction, **kwargs):
    """
    Wrapper générique — requête + parsing XML.
    fonction = Entrez.esearch ou Entrez.efetch.
    handle = requête HTTP (urllib) → flux brut.
    Entrez.read = parse XML → dict/list Python (DictionaryElement, ListElement).
    """
    time.sleep(DELAI_ENTRE_REQUETES)
    try:
        handle = fonction(**kwargs)      # requête HTTP
        data = Entrez.read(handle)        # parsing XML
        handle.close()
        return data
    except (HTTPError, URLError, IncompleteRead) as e:
        # erreurs réseau (urllib)
        logger.warning(f"Erreur réseau Entrez ({fonction.__name__}, args={kwargs}) : {e}")
        return None
    except RuntimeError as e:
        # XML malformé côté NCBI
        logger.warning(f"Erreur de parsing Entrez ({fonction.__name__}, args={kwargs}) : {e}")
        return None


def rechercher_pubmed(mot_cle: str, max_resultats: int = 20) -> List[str]:
    """esearch : liste d'IDs seulement, pas le contenu. Requête légère."""
    resultats = _appel_entrez(Entrez.esearch, db="pubmed", term=mot_cle, retmax=max_resultats)
    if resultats is None:
        return []
    return resultats["IdList"]


def _extraire_date_publication(article: dict) -> Optional[date]:
    """
    Journal.JournalIssue.PubDate — chemin XML → clés dict.
    Format NCBI irrégulier : Year seul, ou MedlineDate texte libre ("2023 Jan-Feb").
    """
    try:
        pubdate = article["Journal"]["JournalIssue"]["PubDate"]
        year = pubdate.get("Year")
        if not year:
            # fallback : MedlineDate texte libre
            medline_date = pubdate.get("MedlineDate", "")
            year = medline_date[:4] if medline_date[:4].isdigit() else None
        if not year:
            return None

        mois_map = {
            "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
            "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
        }
        mois_brut = pubdate.get("Month", "1")
        mois = mois_map.get(mois_brut, None) or (int(mois_brut) if str(mois_brut).isdigit() else 1)
        jour = int(pubdate.get("Day", 1))

        return date(int(year), mois, jour)
    except (KeyError, ValueError, TypeError):
        return None


def _extraire_abstract_structure(article: dict) -> str:
    """
    AbstractText Label="Results" → StringElement (str + .attributes).
    Concatène avec labels préservés pour l'agent en aval.
    """
    abstract_parts = article.get("Abstract", {}).get("AbstractText", [])
    sections = []
    for partie in abstract_parts:
        label = getattr(partie, "attributes", {}).get("Label") if hasattr(partie, "attributes") else None
        texte = str(partie)
        sections.append(f"{label}: {texte}" if label else texte)
    return "\n".join(sections)


def parser_article(pubmed_id: str) -> DocumentBrut | None:
    """
    efetch : contenu complet (vs esearch = IDs seulement).
    records["PubmedArticle"][0]["MedlineCitation"]["Article"] = hiérarchie XML.
    """
    records = _appel_entrez(Entrez.efetch, db="pubmed", id=pubmed_id, rettype="xml", retmode="xml")
    if records is None:
        return None  # échec réseau déjà loggé

    try:
        article = records["PubmedArticle"][0]["MedlineCitation"]["Article"]
        titre = article.get("ArticleTitle", "")

        texte_brut = _extraire_abstract_structure(article)

        if not texte_brut or len(texte_brut) < 50:
            return None  # contenu insuffisant

        return DocumentBrut(
            type_source=TypeSource.pubmed,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
            titre=str(titre),  # StringElement → str
            texte_brut=texte_brut,
            date_publication=_extraire_date_publication(article),
            payload_brut=records,  # dict complet conservé, pour re-traitement futur
        )
    except (KeyError, IndexError) as e:
        # structure inattendue (ex: pas d'Abstract)
        logger.warning(f"Structure inattendue pour l'article {pubmed_id} : {e}")
        return None


def pipeline_pubmed(mot_cle: str, max_resultats: int = 20) -> List[DocumentBrut]:
    """Recherche + parse."""
    ids = rechercher_pubmed(mot_cle, max_resultats)
    documents = []
    for pid in ids:
        doc = parser_article(pid)
        if doc:
            documents.append(doc)
    return documents


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    docs = pipeline_pubmed("GLP-1 receptor agonist diabetes phase 3", max_resultats=5)
    for d in docs:
        print(d.titre[:80], "-", len(d.texte_brut), "caractères", "-", d.date_publication)
