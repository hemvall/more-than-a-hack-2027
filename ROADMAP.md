# Roadmap de travail

Mise à jour : 26 octobre 2026. Ce document conserve l'ordre de travail décidé
avec le propriétaire du dépôt. Les issues restent les unités de livraison :
une branche et une PR vers main par issue, sans fusion non autorisée.

## Contraintes permanentes

- Aucun label ou correctif manuel sur le match fourni, même pour valider.
- Les cinq minutes publiques servent à vérifier la chaîne, jamais à entraîner,
  régler des paramètres ou sélectionner une méthode.
- Les labels manuels de validation doivent provenir d'autres matchs autorisés,
  accessibles aux organisateurs et compatibles avec la définition de possession.
- Les données, prédictions et rapports détaillés restent locaux et ignorés par Git.
- Préserver l'évaluateur officiel, les vérités terrain et les baselines fournis.
- Les améliorations se mesurent d'abord en spellF1, puis macroF1, sur un protocole
  de validation autorisé. Aucun gain public seul ne démontre une généralisation.

## Ordre et critères de sortie

| Étape | Issues | Travail et critère de sortie |
|---|---|---|
| Socle livré | #12, #1 | Workflow et diagnostics livrés par #13 et #14. Les vérifications structurelles ne prouvent pas la synchronisation visuelle. Vérifier séparément les protections effectives de main. |
| 1 — Exécution reproductible | #6, début de #7 | Un runner conserve configuration, seed, révision et état Git, versions, empreintes des entrées/sorties, split, scores et runtime. Il valide les CSV, isole chaque run, conserve les échecs et compare sous le même protocole. Référence stable : variantes officielles intactes. |
| 2 — Inspection et validation | #2, #15, #3 | Un petit viewer local affiche vidéo, tracking projeté, prédictions et transitions. Vérifier visuellement les deux mi-temps sans fabriquer de labels. Définir une validation autorisée sur d'autres matchs, avec développement et test séparés. |
| 3 — Premier système | #4, #5 | Une commande produit un CSV complet et valide. Traiter ensemble possession, contrôle, arrêts et reprises ; ballon manquant ne signifie pas ballon mort. Smart Tagging reste un indice bruité. Ajouter les composants séparément pour pouvoir les retirer et comparer. |
| 4 — Améliorations mesurées | #8, #9, #10 | Comparer passé seul et contexte futur ; figer un test externe avec cas normaux et difficiles ; mesurer la dégradation sous trous et bruit de tracking. Documenter les incertitudes et régressions. |
| 5 — Vidéo optionnelle | #11 | Uniquement pour une faiblesse identifiée, avec gain mesurable sur validation autorisée et coût acceptable. Tous les traitements de compétition restent locaux. |
| 6 — Livraison | fin de #7 | Installation propre, dépendances et paramètres figés, reproduction exacte du CSV, validation du fichier final, document technique et vérification de l'éligibilité. Échéance publiée : 17 novembre 2026. |

## Ajustements à reporter dans les issues

- #3 : remplacer l'annotation de clips du match fourni par la sélection de données
  autorisées d'autres matchs et un protocole de validation documenté.
- #9 : prolonger #3 avec un test figé externe ; aucune annotation du match fourni.
- #2 / #15 : partager un seul périmètre de viewer minimal, sans annotation/export
  de labels sur le match fourni. #15 doit partir de main depuis la fusion de #14 ;
  sa référence à la branche supprimée de #14 est obsolète.
- #6 : distinguer explicitement contrôle public du pipeline et comparaison de
  modèles sur validation externe ; commencer avant tout nouveau modèle.
- #7 : commencer la reproductibilité dès maintenant et finaliser le dossier ensuite.

Le broadcast reste facultatif tant que ses incohérences d'assets ne sont pas
résolues. Ne pas modifier les constantes officielles ni décaler ou compléter
les fichiers pour masquer un écart. Les constats détaillés restent dans runs/.

## Point de reprise

Travail courant : #6, runner d'expériences et journalisation reproductible.
Première livraison : exécuter les quatre baselines officielles sans données privées,
puis les régénérer localement et vérifier l'identité des prédictions, sans tuning.
Ensuite : viewer minimal (#2/#15) et protocole externe (#3), avant #4/#5.
Le statut d'implémentation et les commandes sont détaillés dans docs/experiments.md.
