# Backend FastAPI

Application web du projet 11 : authentification, historique personnel, puis agent d'analyse SQL.
Elle suit la fiche de cadrage (`Bellaly-Atata_Projet11.md`, sections 3, 5 et 6).

## Ce qui est en place

| Fonction (fiche) | Mise en œuvre |
|---|---|
| Inscription : email + mot de passe seulement | `POST /api/auth/register`. Haché **argon2id** avec sel. Email unique et en minuscules. Tout autre champ est refusé (minimisation) |
| Connexion, session de 8 h | `POST /api/auth/login`. Pose le cookie `session` avec `HttpOnly`, `SameSite=Strict` et `Max-Age` de 8 h. La session est stockée **côté serveur** dans `app.sessions`, qui ne garde que l'empreinte SHA-256 du jeton |
| Message d'erreur unique | « Email ou mot de passe incorrect. », que l'email existe ou non. La vérification argon2 prend la même durée dans les deux cas |
| Blocage de 15 min après 5 échecs | Compteur `failed_logins` et date `locked_until` dans `app.users`. Réponse 429 avec le délai restant et l'en-tête `Retry-After` |
| Déconnexion qui invalide la session | `POST /api/auth/logout`. Renseigne `revoked_at` en base : l'ancien cookie, même copié, ne vaut plus rien |
| Historique visible de son seul auteur | `GET /api/history` et `GET /api/history/{id}`. L'identifiant de l'utilisateur vient de la session, jamais du navigateur. L'échange d'un autre utilisateur renvoie « Introuvable. » |
| Suppression du compte avec confirmation | `DELETE /api/users/me` avec `{"confirmation": true}`. `ON DELETE CASCADE` supprime ses sessions et tout son historique |
| Deux rôles cloisonnés | `analyst_ro` (outils de l'agent) n'a aucun accès au schéma `app`. `app_agent` (application) n'a aucun accès à `immo` et ne peut pas modifier la structure |
| Requêtes paramétrées | psycopg 3 (`%s`), aucune concaténation de valeurs dans le SQL (`app/repositories/__init__.py`) |

## Agent (Bloc 3)

Le modèle est appelé par une API compatible OpenAI, choisie dans `.env` : Groq
`openai/gpt-oss-120b` par défaut, ou Ollama en local (`LLM_BASE_URL=http://localhost:11434/v1`).
Aucun framework d'agent n'est utilisé : la boucle d'appel d'outils est dans `app/agent/orchestrator.py`.

| Route | Rôle |
|---|---|
| `POST /api/agent/questions` | L'agent propose un SQL, une explication et des recommandations. **Rien n'est exécuté** ; l'échange est enregistré dans l'historique |
| `POST /api/agent/questions/{id}/execution` | Validation par l'utilisateur : exécution sous `analyst_ro`, 200 lignes au plus |
| `GET /api/agent/questions/{id}/plan?analyze=false` | Plan `EXPLAIN`. `analyze=true` exécute la requête : seulement sur demande de l'utilisateur |

**Outils du modèle**, tous en lecture seule sous `analyst_ro` :
- `lire_schema` : tables, vues (y compris matérialisées), colonnes et index existants ;
- `chercher_commune` : nom vers code INSEE, pour ne pas inventer de code ;
- `requetes_couteuses` : `pg_stat_statements` ;
- `expliquer_requete` : `EXPLAIN` sans exécution ;
- `repondre` : réponse finale.

Le modèle **n'a pas d'outil d'exécution** : seule la route de validation exécute une requête.

**Garde-fous** :
- **Vérification du SQL proposé** (`app/agent/sql_guard.py`) : une seule instruction `SELECT`, analysée par `sqlglot` et non par des expressions régulières. Elle refuse les écritures, les CTE qui modifient des données, `SELECT INTO`, `FOR UPDATE`, les fonctions `pg_*`, `dblink` ou `set_config`, et toute relation hors du schéma `immo`. Le SQL est ensuite testé par `EXPLAIN`, sans être exécuté : une colonne inventée est renvoyée au modèle pour correction.
- **Nouvelle vérification avant chaque exécution**, dans une transaction `READ ONLY`, avec une limite de 30 s.
- **Réponses en texte** : quand le modèle répond en Markdown au lieu d'appeler `repondre` (fréquent avec gpt-oss, et refusé par Groq sous le code `tool_use_failed`), le bloc ```` ```sql ```` est extrait puis soumis aux mêmes vérifications.
- **Contexte** : seuls les 4 derniers échanges de l'utilisateur sont envoyés, rejoués comme des appels à `repondre`.
- **Limites** : 6 appels au modèle par question, résultats d'outils tronqués à 3 500 caractères.
- **Indisponibilité du modèle** (429, clé refusée, réseau) : réponse 503 avec un message clair, et rien n'est enregistré dans l'historique.

**Coût en tokens** (plan gratuit Groq : 8 000 tokens par minute et 1 000 requêtes par jour) : de 3 000 à
6 000 tokens par question. Sur une erreur 429, le client attend le délai annoncé par Groq,
jusqu'à 2 fois.

Tests : `pytest` en lance 130 sans appel au modèle (faux client). Le parcours réel s'obtient avec
`RUN_LLM_TESTS=1 pytest -m llm` : 11 questions de référence (3 types de la fiche, suivi, Lyon et ses arrondissements, diagnostic, hors périmètre, suppression, injection) ; environ 5 min 30 s sur le plan gratuit Groq (attentes de limite de débit comprises).

**Modèle de secours** : `LLM_FALLBACK_MODELS` (par défaut `gpt-oss-20b`). Quand le quota du
modèle principal est épuisé (429 avec un long délai), l'agent bascule aussitôt sur le secours et
met le principal de côté jusqu'à son rétablissement ; une limite courte est simplement attendue
(jusqu'à une minute pour le dernier modèle disponible). La réponse indique quel modèle a répondu.

**Communes à arrondissements** : pour Paris, Lyon et Marseille, `chercher_commune` renvoie un
`filtre_sql` qui inclut tous les arrondissements. Il a été ajouté après qu'un modèle a oublié le
3ᵉ arrondissement de Lyon en recopiant les codes à la main.

## Autres routes (interface)

| Route | Rôle |
|---|---|
| `GET /api/conversations`, `GET`/`PATCH`/`DELETE /api/conversations/{id}` | Conversations de l'utilisateur : liste, détail avec les résultats déjà obtenus, renommage, suppression (avec leurs échanges) |
| `DELETE /api/history/{id}` | Supprimer un échange |
| `GET /api/dashboard` | Statistiques de l'utilisateur et requêtes les plus coûteuses (`pg_stat_statements`, sans les requêtes du schéma `app`) |
| `POST /api/voice/transcribe` | Voix vers texte (Whisper sur Groq, formats webm/ogg/mp4/wav, 10 Mo au plus). Le texte est rendu pour correction, jamais envoyé seul à l'agent |
| `GET /api` | Version de l'API ; `/` sert l'interface React compilée (`FRONTEND_DIST`) |

## Organisation

```
backend/
├── app/
│   ├── main.py                 # application, lifespan (pools), gestion d'erreurs
│   ├── core/config.py          # configuration (lit le .env racine)
│   ├── core/security.py        # argon2id, jetons de session
│   ├── db/connection.py        # pools psycopg : analyst_ro et app_agent
│   ├── repositories/           # SQL paramétré sur le schéma app
│   ├── agent/                  # vérification du SQL, outils, client du modèle, boucle de l'agent
│   ├── services/               # inscription, connexion et blocage, déconnexion, suppression
│   ├── schemas/                # validation Pydantic
│   └── api/
│       ├── deps.py             # cookie et utilisateur courant
│       └── routes/             # health, auth, users, history, agent
└── tests/                      # pytest : 130 tests sans modèle, 11 tests réels (-m llm)
```

Côté base, le schéma `app` est créé par `sql/01_roles.sql` (rôle `app_agent`) et par
`sql/06_app_schema.sql` (tables `users`, `sessions` et `historique`, avec les droits). Les deux
sont lancés par `scripts/init-db.ps1`, et `scripts/verify.ps1` contrôle le cloisonnement.

## Lancer en local

Prérequis : la base est démarrée et initialisée (`scripts/init-db.ps1`), et le `.env` racine
contient `APP_AGENT_PASSWORD`.

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m uvicorn app.main:app --reload     # http://127.0.0.1:8000/docs
.\.venv\Scripts\python -m pytest                            # 130 tests (sans appel au modèle)
```

Avec Docker : `docker compose up -d --build backend` (image en deux étapes : compilation de
l'interface React, puis application Python) publie l'interface et l'API sur
`127.0.0.1:${APP_PORT}` (8000 par défaut).

La configuration est lue dans le `.env` racine, le même que celui de Docker Compose. Un
`backend/.env` optionnel peut en surcharger des valeurs. Passez `COOKIE_SECURE=true` dès que
l'application est servie en HTTPS.
