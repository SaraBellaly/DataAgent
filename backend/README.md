# AI Database Engineer - Backend API

Backend FastAPI pour l'agent IA d'analyse SQL sur le marché immobilier français.

## Architecture

```
backend/
├── app/
│   ├── main.py              # Point d'entrée FastAPI
│   ├── core/                # Configuration et sécurité
│   │   ├── config.py        # Variables d'environnement
│   │   └── security.py      # JWT, hashing (Phase 3.2+)
│   ├── api/
│   │   └── routes/          # Endpoints HTTP
│   │       ├── health.py    # Health checks
│   │       ├── auth.py      # Authentification (Phase 3.2+)
│   │       ├── users.py     # Gestion utilisateurs (Phase 3.2+)
│   │       ├── history.py   # Historique conversations (Phase 3.3+)
│   │       └── agent.py     # Agent Text-to-SQL (Phase 3.4+)
│   ├── db/
│   │   └── connection.py    # Connexions PostgreSQL
│   ├── models/              # Modèles SQLAlchemy
│   ├── schemas/             # Schémas Pydantic
│   ├── services/            # Logique métier
│   └── repositories/        # Accès données
├── tests/                   # Tests pytest
└── requirements.txt
```

## Phase 3.1 — Infrastructure de base

**Statut** : ✅ En cours

### Endpoints disponibles

- `GET /` — Vérifier que le backend fonctionne
- `GET /health` — État de l'application
- `GET /health/db` — Connexion PostgreSQL

### Connexions PostgreSQL

1. **Connexion lecture seule (analyst_ro)** : Pour lire les données DVF/INSEE
   - Utilisée par les futurs endpoints de consultation
   - Timeout 30s, read-only par défaut
   
2. **Connexion données applicatives (future)** : Pour utilisateurs, historique
   - À configurer en Phase 3.2+
   - Base/schéma séparés pour les données de l'application

## Installation locale

### Prérequis

- Python 3.11+
- PostgreSQL 16 (via docker-compose du projet parent)

### 1. Créer un environnement virtuel

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Configurer les variables d'environnement

```bash
cp .env.example .env
# Éditer .env avec les vrais mots de passe
```

### 4. Lancer le serveur de développement

```bash
# Depuis le dossier backend/
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API disponible sur : http://localhost:8000

Documentation interactive : http://localhost:8000/docs

## Lancement via Docker (Phase 3.1+)

```bash
# Depuis la racine du projet
docker compose up -d
```

Le backend sera accessible sur http://localhost:8000.

## Tests

```bash
# Lancer tous les tests
pytest

# Avec couverture
pytest --cov=app tests/

# Un fichier spécifique
pytest tests/test_health.py -v
```

## Phases de développement

- ✅ **Phase 3.1** : Infrastructure backend (endpoints de base, connexion DB)
- ⏳ **Phase 3.2** : Authentification et gestion utilisateurs
- ⏳ **Phase 3.3** : Historique des conversations
- ⏳ **Phase 3.4** : Agent Text-to-SQL et exécution sécurisée

## Sécurité

- ✅ Rôle `analyst_ro` en lecture seule pour données DVF/INSEE
- ✅ Mots de passe dans `.env` (non versionné)
- ✅ Timeout 30s sur connexions lecture seule
- ⏳ JWT pour authentification utilisateurs (Phase 3.2)
- ⏳ Validation et sanitisation des requêtes SQL (Phase 3.4)
