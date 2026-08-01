# Sources de données indispensables -- API d'études cliniques (Dépression)

## 1. Registres d'essais (priorité maximale)

-   ClinicalTrials.gov : NCT ID, phase, statut, sponsor, critères,
    dates.
-   CTIS (Europe).
-   ISRCTN.
-   Registres nationaux (Japon, Chine, Australie...).

## 2. Publications scientifiques

-   PubMed.
-   Crossref (DOI).
-   Métadonnées : PMID, DOI, revue, auteurs, date.

## 3. Congrès

-   APA.
-   ECNP.
-   ASCP.
-   Abstracts, posters, présentations.

## 4. Communiqués des sociétés

-   Résultats topline.
-   Fin de recrutement.
-   Analyses intermédiaires.
-   Arrêt d'essai.
-   Partenariats.
-   Fast Track / Breakthrough.

## 5. Autorités réglementaires

-   FDA.
-   EMA.
-   Approbations, NDA/BLA, Advisory Committee, désignations.

## 6. Données financières

-   Ticker.
-   Capitalisation.
-   Cash runway.
-   Dilution.
-   Pipeline.
-   Levées de fonds.

## 7. Brevets

-   Google Patents.
-   Office européen des brevets.
-   Expiration et protection.

## 8. Molécules

-   Mécanisme d'action.
-   Cible.
-   Classe.
-   Voie d'administration.
-   Dosage.

## 9. Maladies

-   MDD.
-   TRD.
-   Dépression post-partum.
-   Dépression bipolaire.
-   Populations spécifiques.

## 10. Résultats cliniques

-   MADRS.
-   HAM-D.
-   CGI.
-   PHQ-9.
-   Réponse.
-   Rémission.
-   Taille d'effet.
-   p-value.
-   IC.

# Valeur ajoutée de l'API

-   Historique complet des molécules.
-   Calendrier des catalyseurs.
-   Historique des échecs.
-   Liens Entreprise ↔ Molécule ↔ Essai ↔ Publication.
-   Normalisation des endpoints.
-   Scores propriétaires (succès, risque, potentiel commercial).

# Modèle de données

Entreprise └── Molécule └── Essai clinique ├── Résultats ├── Publication
├── Réglementaire └── Finance
