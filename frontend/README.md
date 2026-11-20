# Interface web (React)

Interface de l'agent de gestion de base de données : React 19, TypeScript et Vite. En production,
elle est compilée dans l'image Docker et servie par FastAPI, sur la même origine que l'API. Le
cookie de session `HttpOnly` + `SameSite=Strict` fonctionne donc sans CORS.

## Écrans

| Écran | Adresse | Contenu |
|---|---|---|
| Inscription, connexion | `/inscription`, `/connexion` | Email et mot de passe seulement. Le message d'erreur est unique. Après 5 échecs, la connexion est bloquée 15 min (délai affiché) |
| Conversation | `/`, `/conversations/:id` | Question écrite ou dictée, avec une requête SQL jointe en option. La réponse arrive en cartes : explication, SQL proposé, **« Valider et exécuter »**, résultats (tableau, graphique ou chiffres clés), plan `EXPLAIN` estimé ou mesuré, suggestions d'optimisation |
| Tableau de bord | `/tableau-de-bord` | Statistiques réelles de l'utilisateur et requêtes les plus coûteuses (`pg_stat_statements`), avec un bouton « Analyser » |
| SQL Optimizer | `/optimiseur` | Une requête collée, et un but : lenteur, optimisation ou explication. L'analyse s'ouvre dans une conversation |
| Historique | `/historique` | Recherche, ouverture, renommage et suppression des conversations ; suppression du compte avec confirmation |
| Paramètres | `/parametres` | Voix (lecture automatique, voix, vitesse, hauteur), mascotte 3D, animations, compte |

## Mascotte et voix

- **Lumi**, la mascotte 3D (`src/components/mascot/Mascot3D.tsx`), est construite en code avec
  React Three Fiber, sans modèle externe.
  - **États** : accueil, réflexion, préparation, succès, erreur, parole.
  - **Comportement** : elle suit la souris et cligne des yeux.
  - **Repli** : une pastille animée remplace la 3D si WebGL est absent, ou si la mascotte est désactivée dans les Paramètres.
- **Voix** (`src/voice/`), découplée de l'interface :
  - **Dictée** : `useDictation` enregistre le micro, détecte la fin de la parole (1,4 s de silence) et fait transcrire l'audio par Whisper, via le backend. Le texte reste modifiable avant l'envoi.
  - **Synthèse vocale** : `VoiceContext` utilise les voix françaises du navigateur.
  - **Lecture automatique** : seulement pour une question dictée. Le micro coupe la parole de l'assistante.

## Développement

Le backend doit tourner sur `127.0.0.1:8000`. Vite relaie `/api` vers lui.

```powershell
cd frontend
npm install
npm run dev -- --port 5180     # http://127.0.0.1:5180  (5173 par défaut s'il est libre)
npm run build                  # vérification TypeScript + compilation dans dist/
```

La page `/labo-mascotte` montre les états de la mascotte. Elle n'existe qu'en développement.

## Organisation

```
src/
├── api/          # client HTTP (cookie de session), routes du backend, types
├── auth/         # état de connexion
├── chat/         # état d'une conversation (envoi, validation, plan, reprise)
├── components/   # interface : chat, mascotte, compte, éléments de base
├── layout/       # cadre (barre latérale réductible, tiroir sur mobile)
├── pages/        # écrans
├── settings/     # réglages d'interface mémorisés dans le navigateur
├── voice/        # dictée et synthèse vocale
└── styles/       # palette (blanc, rose pastel, lavande) et styles globaux
```
