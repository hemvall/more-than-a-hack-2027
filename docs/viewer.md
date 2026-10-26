# Inspecter localement les prédictions

Le viewer de l'issue #2 couvre le besoin d'inspection partagé avec #15. Il sert au
débogage du pipeline et à l'inspection visuelle, sans annotation ni export de labels.
Il fonctionne indépendamment du runner de #6 et ne nécessite aucun package frontend.

Depuis la racine du dépôt, avec Python 3.11 :

```bash
python -m viewer
```

Ouvrir `http://127.0.0.1:8765` dans un navigateur récent. `--port 8766` permet de
choisir un autre port. Ctrl+C arrête le serveur. La démo utilise uniquement des
positions et des labels synthétiques et fonctionne sans assets de compétition.

## Charger une session

Les sources peuvent être chargées dans n'importe quel ordre. Le premier import
valide quitte la démo ; aucune position simulée n'est superposée à une vraie vidéo.

1. Choisir la **vidéo tactique complète**. Sa durée doit correspondre à 199 319
   frames à 25 fps, avec une tolérance d'une frame sur les métadonnées de durée.
   Les noms numérotés du bundle sont acceptés puisque le fichier est choisi directement.
   Les clips et la vidéo broadcast ont une autre timeline et sont refusés.
2. Choisir un CSV de prédictions complet `frame,label`, frames `0..199318` en ordre,
   labels `H/A/D/X`. Les fichiers fournis dans `evaluation/results/` ou les sorties
   locales du runner conviennent. Le viewer ne remplace pas le validateur officiel.
3. Pour les positions, sélectionner **ensemble** le XML et le TXT ATD tactiques.
   Les IDs sont convertis avec `video_frame = frame_id - 1`, sans offset privé ni
   correction manuelle. Les numéros affichés sont des slots, pas des identités.
4. Choisir le CSV d'homographie tactique pour projeter ces positions sur la vidéo.
   Sans vidéo, le tracking est visible sur un terrain normalisé. Une homographie
   invalide, singulière ou dont l'erreur de reprojection est négative est refusée ;
   une frame explicitement marquée invalide n'est jamais projetée.
5. Le bouton de référence charge uniquement le CSV public fourni avec le dépôt.
   Les frames hors de la fenêtre publiée doivent être `X`. Il n'existe aucun
   import de vérité terrain arbitraire ou de labels manuels.

Les parseurs vérifient l'indexation et le nombre de lignes avant de remplacer une
source. Un fichier invalide conserve la source précédente. Le parsing s'exécute
dans des workers et lit les fichiers par morceaux. Le retour à la démo annule les
imports actifs et libère les workers et l'ancienne vidéo.

## Naviguer

- Lecture/pause, vitesse, slider, saisie d'une frame et pas de ±1 frame.
- Flèches gauche/droite et Espace lorsque le focus n'est pas dans un contrôle.
- Sauts vers les transitions précédentes/suivantes et liste des transitions proches.
- Avec prédictions et référence publique : navigation entre plages d'écart,
  uniquement là où la référence est renseignée. Aucun score ou classement de modèles.
- La timeline supérieure montre les prédictions, l'inférieure la référence publique.
  `X` dans une prédiction est une abstention ; hors fenêtre publique, la référence
  affiche « Hors fenêtre », et ces frames ne deviennent pas des erreurs.

## Limites et données

Le seeking HTML vidéo reste approximatif : `requestVideoFrameCallback` suit les
timestamps des images rendues quand il est disponible, mais ce viewer n'est pas une
preuve d'alignement frame-exact. Le contrôle de durée n'établit ni le FPS réel, ni
l'identité du match, ni le nombre d'images décodées. Effectuer aussi l'audit local :

```bash
python -m diagnostics --check-video
```

Inspecter visuellement les superpositions aux deux mi-temps et sur des passages
représentatifs. Le viewer n'aligne pas le broadcast et ne propose aucun offset pour
masquer une divergence. Le codec vidéo doit être pris en charge par le navigateur.
Le tracking complet nécessite de la mémoire disponible ; les limites d'import sont
512 Mio pour le TXT, 128 Mio pour l'homographie et 16 Mio pour les prédictions.

Les fichiers choisis restent en mémoire dans le navigateur et ne sont ni envoyés
au serveur, ni conservés en localStorage. Recharger impose de les resélectionner.
Le serveur écoute seulement sur 127.0.0.1 et n'expose que les fichiers du viewer,
sa configuration et la référence publique officielle, sans navigation dans le dépôt
et sans route d'upload. Aucun asset privé n'est servi automatiquement depuis data/.

La fenêtre publique sert au contrôle du pipeline, jamais au tuning, à la sélection
de méthode ou à l'entraînement. Ne pas transformer l'inspection en annotations,
corrections ou constantes attachées à des frames particulières de ce match.
La validation annotée appartient à d'autres matchs autorisés, suivant #3 et #9.

## Vérification

```bash
node --test tests/test-viewer.mjs
python -m unittest discover -s tests -v
```

Les tests couvrent les index, NaN, géométries invalides, frontières de navigation,
fenêtre publique et routes HTTP autorisées. Les essais navigateur utilisent une
vidéo, un tracking, une homographie et des prédictions entièrement synthétiques ;
aucune image du match restreint n'est envoyée à un outil hébergé.
