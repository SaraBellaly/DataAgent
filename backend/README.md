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

Les écrans et l'agent sont les étapes suivantes. La route `app/api/routes/agent.py` n'est pas encore branchée.

## Organisation

```
backend/
├── app/
│   ├── main.py                 # application, lifespan (pools), gestion d'erreurs
│   ├── core/config.py          # configuration (lit le .env racine)
│   ├── core/security.py        # argon2id, jetons de session
│   ├── db/connection.py        # pools psycopg : analyst_ro et app_agent
│   ├── repositories/           # SQL paramétré sur le schéma app
│   ├── services/               # inscription, connexion et blocage, déconnexion, suppression
│   ├── schemas/                # validation Pydantic
│   └── api/
│       ├── deps.py             # cookie et utilisateur courant
│       └── routes/             # health, auth, users, history (agent : à venir)
└── tests/                      # pytest sur la base réelle (31 tests)
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
.\.venv\Scripts\python -m pytest                            # 31 tests
```

Avec Docker : `docker compose up -d --build backend` publie l'application sur
`127.0.0.1:${APP_PORT}` (8000 par défaut).

La configuration est lue dans le `.env` racine, le même que celui de Docker Compose. Un
`backend/.env` optionnel peut en surcharger des valeurs. Passez `COOKIE_SECURE=true` dès que
l'application est servie en HTTPS.
