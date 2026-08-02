import json
from pathlib import Path

# Import depuis le sous-dossier db/ (db/db.py)
from storage.db import init_db, insert_raw_records


def charger_json(chemin_fichier: Path) -> list[dict]:
    """Lit un fichier JSON et extrait la liste de données."""
    with open(chemin_fichier, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "results" in data:
        return data["results"]
    elif isinstance(data, list):
        return data
    return []


def main():
    # Création du fichier medtech.db à la racine (ou là où tu le souhaites)
    db_path = Path("medtech.db")
    print(f"⚙️ Initialisation de la base SQLite : {db_path}...")
    conn = init_db(db_path)

    fichiers_a_charger = [
        {
            "fichier": Path("output/fda_pma_export.json"),
            "source": "openFDA_pma",
            "record_number_field": "k_number",
        },
        
    ]

    for item in fichiers_a_charger:
        fichier = item["fichier"]
        if not fichier.exists():
            print(f"⚠️ Fichier ignoré (introuvable) : {fichier}")
            continue

        print(f"📥 Lecture de {fichier}...")
        records = charger_json(fichier)

        if not records:
            print(f"⚠️ Aucun enregistrement trouvé dans {fichier}")
            continue

        count = insert_raw_records(
            conn=conn,
            records=records,
            source=item["source"],
            record_number_field=item["record_number_field"],
        )
        print(f"✅ {count} lignes insérées/mises à jour depuis {fichier.name}")

    conn.close()
    print("🎉 Ingestion terminée avec succès !")


if __name__ == "__main__":
    main()