"""
find_company_duplicates.py - Detection de doublons applicant_raw
==================================================================

Scanne raw_clearance_records.applicant_raw, normalise chaque valeur (casse,
"&"/"and", abreviations Corp/Inc/Ltd, espaces parasites), et sort deux
choses distinctes :

  1. GROUPES EXACTS (apres normalisation) : quasi-certain que c'est la
     meme entite (juste une variation de casse/ponctuation/abreviation).
     Candidats surs pour un merge dans company_aliases.

  2. GROUPES FLOUS (similarite textuelle, difflib.SequenceMatcher) : des
     noms proches mais pas identiques apres normalisation - A VALIDER A
     LA MAIN, car ca peut aussi bien etre "Depuy Orthopaedics" / "Depuy
     Spine" (meme groupe, a merger) que "Cook Incorporated" / "Cook
     Endoscopy" (filiales distinctes du meme groupe, a NE PAS merger en
     un seul company_id si le scoring par device doit rester precis).

Pas de dependance externe (rapidfuzz, fuzzywuzzy) : difflib est dans la
stdlib, largement suffisant pour un rapport ponctuel a valider a la main -
pas besoin d'un matching plus sophistique tant qu'il n'y a pas de
resolution 100% automatique en aval.

Usage :
    python scripts/find_company_duplicates.py --db medtech.db
    python scripts/find_company_duplicates.py --db medtech.db --threshold 0.85
    python scripts/find_company_duplicates.py --db medtech.db --min-count 2
"""

import argparse
import re
import sqlite3
from collections import defaultdict
from difflib import SequenceMatcher


def normalize_applicant_key(raw: str) -> str:
    s = raw.lower()
    s = s.replace("&", "and")
    s = re.sub(r"\s*,\s*", ", ", s)          # espace parasite avant/apres virgule
    s = re.sub(r"\bcorporation\b", "corp", s)
    s = re.sub(r"\bcorp\.?\b", "corp", s)
    s = re.sub(r"\bincorporated\b", "inc", s)
    s = re.sub(r"\binc\.?\b", "inc", s)
    s = re.sub(r"\bltd\.?\b", "ltd", s)
    s = re.sub(r"\bcompany\b", "co", s)
    s = re.sub(r"\bco\.?\b", "co", s)
    s = re.sub(r"[.,]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_applicants(db_path: str, min_count: int) -> dict[str, int]:
    """{applicant_raw: nb_occurrences} pour tout applicant_raw non vide."""
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """
        SELECT applicant_raw, COUNT(*) as n
        FROM raw_clearance_records
        WHERE applicant_raw IS NOT NULL AND TRIM(applicant_raw) != ''
        GROUP BY applicant_raw
        """
    )
    counts = {row[0]: row[1] for row in cur.fetchall()}
    conn.close()
    return {k: v for k, v in counts.items() if v >= min_count}


def find_exact_groups(applicants: dict[str, int]) -> dict[str, list[str]]:
    """Groupe les noms bruts par cle normalisee identique."""
    groups = defaultdict(list)
    for raw in applicants:
        groups[normalize_applicant_key(raw)].append(raw)
    return {k: v for k, v in groups.items() if len(v) > 1}


class UnionFind:
    def __init__(self, items):
        self.parent = {i: i for i in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def find_fuzzy_groups(keys: list[str], threshold: float) -> list[list[str]]:
    """Clustering naif par similarite de chaine sur des cles deja normalisees.

    O(n^2) avec un filtre "meme premiere lettre" pour eviter l'essentiel des
    comparaisons inutiles - largement suffisant pour un rapport ponctuel sur
    quelques centaines/milliers de cles distinctes, pas fait pour tourner en
    continu/en prod sur un dataset qui grossit sans fin.
    """
    uf = UnionFind(keys)
    n = len(keys)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = keys[i], keys[j]
            if a[:1] != b[:1]:
                continue
            if SequenceMatcher(None, a, b).ratio() >= threshold:
                uf.union(a, b)

    clusters = defaultdict(list)
    for key in keys:
        clusters[uf.find(key)].append(key)
    return [v for v in clusters.values() if len(v) > 1]


def main():
    parser = argparse.ArgumentParser(description="Detection de doublons sur applicant_raw")
    parser.add_argument("--db", required=True)
    parser.add_argument("--threshold", type=float, default=0.87,
                         help="Seuil de similarite difflib pour le matching flou (0-1, defaut 0.87)")
    parser.add_argument("--min-count", type=int, default=1,
                         help="Ignore les applicants vus moins de N fois (defaut 1 = tous)")
    args = parser.parse_args()

    applicants = load_applicants(args.db, args.min_count)
    print(f"{len(applicants)} applicant_raw distincts charges\n")

    # bruit evident : entrees trop courtes pour etre un vrai nom d'entreprise (ex: "Y")
    suspect = {k: v for k, v in applicants.items() if len(k.strip()) < 3}
    if suspect:
        print("=== SUSPECTS (probable bruit FDA, a filtrer plutot qu'a matcher) ===")
        for name, count in suspect.items():
            print(f"  {name!r} ({count} records)")
        print()
        applicants = {k: v for k, v in applicants.items() if k not in suspect}

    exact_groups = find_exact_groups(applicants)
    grouped_raw_names = {name for group in exact_groups.values() for name in group}

    print(f"=== GROUPES EXACTS (meme cle normalisee) : {len(exact_groups)} groupes ===")
    for key, names in sorted(exact_groups.items(), key=lambda kv: -sum(applicants[n] for n in kv[1])):
        total = sum(applicants[n] for n in names)
        print(f"\n  [{key}] ({total} records au total)")
        for name in sorted(names, key=lambda n: -applicants[n]):
            print(f"    - {name!r} ({applicants[name]} records)")

    # candidats flous : uniquement les noms sans match exact deja trouve
    remaining = [n for n in applicants if n not in grouped_raw_names]
    remaining_keys = sorted({normalize_applicant_key(n) for n in remaining})
    fuzzy_clusters = find_fuzzy_groups(remaining_keys, args.threshold)

    print(f"\n\n=== GROUPES FLOUS (similarite >= {args.threshold}, A VALIDER A LA MAIN) : {len(fuzzy_clusters)} groupes ===")
    print("(vraie variante du meme nom OU filiales distinctes a NE PAS merger - a toi de trancher)")
    for cluster in sorted(fuzzy_clusters, key=len, reverse=True):
        print(f"\n  Cluster ({len(cluster)} variantes) :")
        for key in cluster:
            originals = [n for n in remaining if normalize_applicant_key(n) == key]
            print(f"    - {key!r}  <- {originals}")


if __name__ == "__main__":
    main()