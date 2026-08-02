# [MedTech Edge] — Agrégateur de données MedTech pour investisseurs retail

## Pitch en une phrase

Un parser + agrégateur de données réglementaires et financières MedTech, qui transforme des sources publiques éparses et illisibles (FDA, brevets, filings SEC...) en signaux exploitables pour les investisseurs retail positionnés sur les small/mid cap US.

## Problème

Les investisseurs retail qui s'intéressent aux small/mid cap MedTech américaines n'ont pas accès aux outils qu'utilisent les fonds spécialisés (terminaux Bloomberg, bases propriétaires type GlobalData/Evaluate MedTech). Les données existent pourtant en accès public mais sont :
- dispersées sur plusieurs sources (FDA 510(k)/PMA, SEC EDGAR, USPTO, ClinicalTrials.gov, CMS...)
- non structurées ou mal indexées (PDF, formulaires FDA, filings bruts)
- publiées sans contexte financier (aucun lien direct entre un événement réglementaire et son impact sur le titre coté)

Résultat : un retail investor découvre une clairance FDA, un procès, ou un changement de remboursement CMS des jours ou semaines après le marché institutionnel, ou pas du tout.

## Solution

Une plateforme qui :
1. **Parse** les sources publiques pertinentes en continu
2. **Structure** les événements par entreprise/ticker (FDA clearance, PMA, warning letter, recall, brevet, filing SEC, essai clinique...)
3. **Agrège** ces événements dans un flux consultable, avec contexte (device class, indication, marché adressé)
4. **Priorise** les small/mid cap où un seul événement réglementaire peut avoir un impact disproportionné sur le cours (contrairement aux large caps diversifiées type Medtronic/J&J)

## Sources de données ciblées

| Source | Données | Statut |
|---|---|---|
| FDA 510(k) | Clairances, device class, predicate devices | 🟡 Ébauche de parser en cours |
| FDA PMA | Approbations pré-market, panels | À faire |
| FDA Warning Letters / Recalls | Signaux négatifs, risque réglementaire | À faire |
| SEC EDGAR (10-K, 10-Q, 8-K) | Filings financiers, guidance, litiges | À faire |
| ClinicalTrials.gov | Essais en cours, phases, endpoints | À faire |
| USPTO | Portefeuille brevets, expirations | À évaluer |
| CMS | Codes de remboursement, coverage decisions | À évaluer (fort impact sur small caps) |

## Cible utilisateur

Investisseurs retail actifs (auto-directed), déjà familiers avec le stock picking, positionnés ou intéressés par le secteur MedTech small/mid cap US — profil "je fais mes propres recherches mais je n'ai pas les outils des pros".

## Différenciation

- Focus **spécifiquement MedTech**, pas généraliste santé/biotech
- Focus **small/mid cap**, segment sous-couvert par les outils existants (contrairement aux large caps très suivies)
- Angle **réglementaire → marché**, pas juste agrégation de news
- Conçu par quelqu'un qui a l'expérience technique (bots temps réel, parsing on-chain) pour livrer un produit réactif, pas un dashboard statique mis à jour une fois par semaine

## Questions ouvertes à trancher

- Modèle de monétisation : abonnement SaaS, freemium, ou API ?
- Alertes temps réel vs digest périodique ?
- Scope MVP : FDA 510(k) seul suffit-il pour valider la valeur perçue avant d'ajouter SEC/CMS ?
- Comment scorer/prioriser les événements pour éviter le bruit (un 510(k) mineur vs un recall majeur n'ont pas le même poids) ?
- Couverture : univers de tickers fixe (liste MedTech small/mid cap US) ou découverte dynamique via mapping entreprise ↔ device manufacturer ?

## État actuel

- Ébauche de parser FDA 510(k) démarrée.
- Reste à définir : schéma de données commun pour agréger plusieurs sources hétérogènes, et le mapping entité réglementaire ↔ ticker coté.