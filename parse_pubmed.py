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

# --- SOUS LE CAPOT : Entrez.email / Entrez.api_key ---
# Ce sont juste des variables globales du module Bio.Entrez. Quand tu appelles
# Entrez.esearch(...) ou Entrez.efetch(...) plus bas, biopython les relit
# automatiquement et les injecte comme paramètres `email=` et `api_key=`
# dans l'URL de requête HTTP qu'il construit en interne, du type :
#   https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&email=...
# Rien de magique : c'est équivalent à passer ces valeurs toi-même dans un
# dict de params `requests.get(url, params={"email": ..., "api_key": ...})`.

Entrez.email = "ton.email@example.com"
Entrez.api_key = os.environ.get("NCBI_API_KEY")

# 3 req/s sans clé API, 10 req/s avec — limite imposée par NCBI, pas par biopython.
DELAI_ENTRE_REQUETES = 0.11 if Entrez.api_key else 0.34

if not Entrez.api_key:
    logger.warning("NCBI_API_KEY absente — throttling à 3 req/s au lieu de 10.")


def _appel_entrez(fonction, **kwargs):
    """
    Wrapper générique pour tout appel réseau Entrez.

    --- SOUS LE CAPOT ---
    `fonction` est soit Entrez.esearch, soit Entrez.efetch. Quand on l'appelle
    avec **kwargs, biopython fait concrètement ceci en interne :
      1. Construit une URL GET vers eutils.ncbi.nlm.nih.gov avec tes kwargs
         comme query params (ex: db=pubmed, term=..., retmax=...)
      2. Ouvre une connexion HTTP (via urllib, la lib standard Python —
         pas de lib tierce cachée) et retourne un objet "handle" — l'équivalent
         d'un `response.raw` de la lib requests, un flux de bytes pas encore lu

    `Entrez.read(handle)` fait ensuite :
      3. Lit le flux XML (ou JSON selon retmode) renvoyé par NCBI
      4. Le PARSE en objets Python : des dicts/listes "enrichis" par biopython
         (types DictionaryElement, ListElement — qui se comportent comme des
         dict/list normaux mais peuvent porter des métadonnées XML en plus,
         comme les attributs Label qu'on lit plus bas avec `.attributes`)

    Donc concrètement : cette fonction fait exactement ce qu'on ferait avec
    `requests.get(url, params=...)` suivi d'un `xml.etree.parse(response.content)`
    — biopython empile juste ces deux étapes derrière un seul appel.
    """
    time.sleep(DELAI_ENTRE_REQUETES)
    try:
        handle = fonction(**kwargs)          # étape 1-2 : requête HTTP, renvoie un flux
        data = Entrez.read(handle)            # étape 3-4 : lecture + parsing XML→objets Python
        handle.close()                        # ferme la connexion réseau, comme response.close()
        return data
    except (HTTPError, URLError, IncompleteRead) as e:
        # HTTPError/URLError viennent d'urllib (lib standard) — erreurs réseau classiques
        # (timeout, DNS, 4xx/5xx du serveur NCBI)
        logger.warning(f"Erreur réseau Entrez ({fonction.__name__}, args={kwargs}) : {e}")
        return None
    except RuntimeError as e:
        # Levée par le parseur XML interne de biopython quand NCBI renvoie
        # un XML tronqué ou mal formé (arrive occasionnellement sous charge)
        logger.warning(f"Erreur de parsing Entrez ({fonction.__name__}, args={kwargs}) : {e}")
        return None


def rechercher_pubmed(mot_cle: str, max_resultats: int = 20) -> List[str]:
    """
    Retourne une liste d'IDs PubMed correspondant à la recherche.

    --- SOUS LE CAPOT ---
    Entrez.esearch appelle concrètement l'endpoint esearch.fcgi de NCBI,
    qui NE renvoie PAS les articles eux-mêmes — juste une liste d'IDs qui
    matchent la recherche. C'est une requête légère et rapide.
    Le JSON/XML renvoyé a la forme : {"esearchresult": {"idlist": [...]}}
    — après parsing par Entrez.read(), on obtient un dict Python avec
    une clé "IdList" (biopython normalise le nommage).
    """
    resultats = _appel_entrez(Entrez.esearch, db="pubmed", term=mot_cle, retmax=max_resultats)
    if resultats is None:
        return []
    return resultats["IdList"]


def _extraire_date_publication(article: dict) -> Optional[date]:
    """
    Extrait la date de publication depuis Journal.JournalIssue.PubDate.

    --- SOUS LE CAPOT ---
    `article` ici est le dict Python déjà parsé par Entrez.read() — pas du
    XML brut. Naviguer `article["Journal"]["JournalIssue"]["PubDate"]`
    revient à suivre le chemin XML <Journal><JournalIssue><PubDate> dans
    le document original, mais biopython l'a déjà transformé en dict imbriqué,
    donc on utilise des clés Python classiques plutôt que du XPath.

    Le format NCBI est irrégulier (parfois juste Year, parfois Year+Month+Day,
    parfois Month en texte "Jan" au lieu de "01"), donc on reste tolérant.
    """
    try:
        pubdate = article["Journal"]["JournalIssue"]["PubDate"]
        year = pubdate.get("Year")
        if not year:
            # Certains articles n'ont qu'un "MedlineDate" en texte libre (ex: "2023 Jan-Feb")
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
    Reconstruit l'abstract en gardant les labels de section (Background,
    Methods, Results, Conclusions...) quand ils existent.

    --- SOUS LE CAPOT ---
    Dans le XML original, chaque section d'abstract ressemble à :
        <AbstractText Label="Results">Le texte ici...</AbstractText>
    Biopython parse ça en un objet "StringElement" — une string Python
    normale (c'est pour ça que `str(partie)` marche), mais À LAQUELLE
    biopython accroche en plus un attribut `.attributes` (un dict) qui
    contient les attributs XML d'origine, comme {"Label": "Results"}.
    C'est le seul endroit du fichier où cette "magie" (un objet qui EST
    une string mais qui PORTE aussi des métadonnées) intervient — d'où le
    `hasattr(partie, "attributes")` défensif, car un `str` Python normal
    n'a pas cet attribut.
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
    Récupère et parse un article PubMed en DocumentBrut validé.

    --- SOUS LE CAPOT ---
    Entrez.efetch (contrairement à esearch) récupère le CONTENU complet
    de l'article — le vrai XML PubMed avec titre, auteurs, abstract, dates,
    etc. C'est une requête plus lourde qu'esearch, d'où l'intérêt d'avoir
    filtré les IDs pertinents en amont plutôt que tout efetch en masse.

    `records` est un dict Python avec la structure :
        records["PubmedArticle"][0]["MedlineCitation"]["Article"]
    Ce chemin correspond exactement à la hiérarchie XML :
        <PubmedArticleSet><PubmedArticle><MedlineCitation><Article>
    (le [0] existe car efetch peut en théorie renvoyer plusieurs articles
    si on lui passe plusieurs IDs séparés par une virgule — ici on en
    demande un seul à la fois donc toujours [0])
    """
    records = _appel_entrez(Entrez.efetch, db="pubmed", id=pubmed_id, rettype="xml", retmode="xml")
    if records is None:
        return None  # échec réseau déjà loggé dans _appel_entrez

    try:
        article = records["PubmedArticle"][0]["MedlineCitation"]["Article"]
        titre = article.get("ArticleTitle", "")

        texte_brut = _extraire_abstract_structure(article)

        if not texte_brut or len(texte_brut) < 50:
            return None  # rejeté : pas assez de contenu exploitable

        return DocumentBrut(
            type_source=TypeSource.pubmed,
            url=f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
            titre=str(titre),  # str() car ArticleTitle est un StringElement biopython, pas un str pur
            texte_brut=texte_brut,
            date_publication=_extraire_date_publication(article),
            payload_brut=records,  # on garde tout le dict parsé, pour re-traiter plus tard sans réappeler l'API
        )
    except (KeyError, IndexError) as e:
        # Un article peut manquer une clé attendue (ex: pas d'Abstract du tout,
        # cas des lettres/éditoriaux) — on log et on skip plutôt que de crasher
        logger.warning(f"Structure inattendue pour l'article {pubmed_id} : {e}")
        return None


def pipeline_pubmed(mot_cle: str, max_resultats: int = 20) -> List[DocumentBrut]:
    """Point d'entrée : recherche + parse une liste d'articles."""
    ids = rechercher_pubmed(mot_cle, max_resultats)
    documents = []
    for pid in ids:
        doc = parser_article(pid)
        if doc:
            documents.append(doc)
    return documents


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test rapide sur le diabète
    docs = pipeline_pubmed("GLP-1 receptor agonist diabetes phase 3", max_resultats=5)
    for d in docs:
        print(d.titre[:80], "-", len(d.texte_brut), "caractères", "-", d.date_publication)
