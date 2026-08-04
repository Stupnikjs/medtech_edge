"""
Parsing de PDF (rapports EPAR/EMA, labels FDA, etc.)
Installation : pip install pymupdf --break-system-packages
"""

import fitz  # pymupdf
from models.schemas import DocumentBrut, TypeSource
from pathlib import Path


def parser_pdf(chemin_fichier: str, type_source: TypeSource, url: str = None) -> DocumentBrut | None:
    """Extrait le texte d'un PDF local et retourne un DocumentBrut validé."""
    chemin = Path(chemin_fichier)
    if not chemin.exists():
        return None

    doc = fitz.open(chemin_fichier)
    texte_pages = [page.get_text() for page in doc]
    texte_brut = "\n".join(texte_pages).strip()
    titre = doc.metadata.get("title") or chemin.stem
    doc.close()

    if len(texte_brut) < 50:
        return None

    return DocumentBrut(
        type_source=type_source,
        url=url,
        titre=titre,
        texte_brut=texte_brut,
        date_publication=None,
        payload_brut={"chemin_local": chemin_fichier, "nb_pages": len(texte_pages)},
    )


if __name__ == "__main__":
    # Exemple : un EPAR téléchargé localement
    doc = parser_pdf("exemple_epar.pdf", TypeSource.epar)
    if doc:
        print(doc.titre, "-", len(doc.texte_brut), "caractères")