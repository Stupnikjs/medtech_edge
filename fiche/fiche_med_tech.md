# Fiche de référence — Classification et voies réglementaires FDA (devices)

## 1. Le point de départ : la classe de risque

Tout commence par la classe de risque du device — c'est elle qui détermine ensuite quelle voie réglementaire s'applique.

| Classe | Niveau de risque | Contrôles requis | Exemples |
|---|---|---|---|
| **Classe I** | Faible | General controls (souvent exempté de soumission premarket) | Gants chirurgicaux, fauteuils roulants |
| **Classe II** | Modéré | General + Special controls | Pompes à perfusion, la plupart des devices orthopédiques/cardio non implantables |
| **Classe III** | Élevé | Le plus strict — souvent PMA | Pacemakers, valves cardiaques implantables |

La classe se déduit du `product_code` (via la Product Classification Database FDA), pas du texte libre de `device_name`.

## 2. Les trois voies de mise sur le marché

| Voie | Pour quels devices | Logique | Timeline/coût indicatif |
|---|---|---|---|
| **510(k)** | Classe II principalement, une partie de la Classe I | Démontrer une **équivalence substantielle** à un predicate déjà commercialisé — pas de preuve d'efficacité clinique supérieure requise | 6-12 mois, ~100k-500k$ (estimations industrie, pas des chiffres FDA officiels) |
| **PMA** (Premarket Approval) | Classe III (implants, life-sustaining/life-supporting) | Le plus strict : <cite index="21-1">requiert des preuves d'essais cliniques conduits sous IDE (Investigational Device Exemption)</cite>, plus historique de conception complet, validation biocompatibilité/stérilisation, revue par panel consultatif | Nettement plus long et coûteux que le 510(k) |
| **De Novo** | Devices nouveaux, risque faible/modéré, **sans predicate existant** | <cite index="27-1">Deux cas d'usage : après un rejet NSE (Not Substantially Equivalent) sur un 510(k), ou directement si aucun predicate n'existe</cite> — la FDA classe alors le device en Classe I ou II | <cite index="21-1">Nécessite une évaluation de risque complète, tests cliniques/non cliniques, justification bénéfice-risque et contrôles spéciaux proposés</cite> |

**Point stratégique important** : <cite index="27-1">un device classé via De Novo peut ensuite servir de predicate pour de futures soumissions 510(k)</cite>. Concrètement, le premier acteur à ouvrir une catégorie via De Novo obtient un avantage compétitif — les concurrents suivants devront souvent référencer SON device. C'est un signal intéressant à tracker : une clearance De Novo dans un `product_code` neuf peut annoncer une vague de 510(k) suiveurs dans les mois/années qui suivent.

## 3. Vocabulaire à ne jamais confondre

| Terme correct | À ne pas dire |
|---|---|
| 510(k) **cleared** | 510(k) approved |
| PMA **approved** | PMA cleared |
| **Substantially equivalent** (510(k)) | "Prouvé efficace" |
| **De Novo granted/classified** | De Novo approved |

Le vocabulaire est légalement significatif, pas juste stylistique — l'utiliser correctement dans ton app renforce la crédibilité auprès d'un public qui connaît le sujet.

## 4. Après la mise sur le marché : les signaux de risque

### MAUDE (Manufacturer and User Facility Device Experience)
Base de signalement des incidents/événements indésirables une fois le device commercialisé. Ne remplace pas le 510(k)/PMA — elle donne le risque réel post-market. Un pic de signalements MAUDE sur un device peut précéder un recall.

### Recalls — 3 classes de gravité
| Classe | Gravité |
|---|---|
| **Class I** | Le plus grave — risque de blessure sérieuse ou de décès |
| **Class II** | Risque de conséquence médicale réversible ou temporaire |
| **Class III** | Peu probable de causer un problème de santé (souvent administratif/étiquetage) |

Ces trois classes de recall n'ont **aucun rapport** avec les classes de risque des devices (Classe I/II/III vues en section 1) — deux échelles distinctes qui portent malheureusement le même nom. Piège classique à documenter clairement dans ton app pour ne pas induire l'utilisateur en erreur.

## 5. Pourquoi c'est pertinent pour ta stratégie d'investissement

- **Un rejet NSE ou un recall Class I sur une petite cap** a un impact disproportionné sur le cours comparé à une large cap diversifiée — c'est exactement le type de signal que ton produit doit capter en premier.
- **Une clearance De Novo** est un signal positif de differentiation/premier entrant, potentiellement plus significatif qu'un simple 510(k) suiveur.
- **Un dossier redirigé de 510(k) vers PMA** (`decision_code = FB`, vu dans ta fiche précédente) signale une charge réglementaire soudainement plus lourde — impact potentiel sur le timeline et le cash burn d'une small cap.
- **MAUDE en complément du 510(k)/PMA** te donnerait une couche de surveillance post-market — à envisager pour une V2 de ton pipeline, au-delà de la seule ingestion FDA 510(k).

## 6. Prochaine étape suggérée

Pour ton MVP, tu peux rester concentré sur 510(k) seul (comme prévu), mais je recommande de prévoir dès la conception du schéma de données un champ générique type `submission_pathway` (510k / PMA / De Novo) et `outcome_signal` (positif/neutre/négatif), même si seul 510(k) est peuplé au départ — ça t'évite une migration de schéma douloureuse quand tu ajouteras PMA et MAUDE plus tard.