-- Tables de l'application : comptes, sessions, historique.
-- Exécuté par immo_admin (propriétaire du schéma app, créé dans 01_roles.sql).
-- Idempotent : peut être rejoué sans erreur et sans perte de données.
--
-- Cloisonnement (fiche de cadrage, section 6.2) :
--   - app_agent lit et écrit ces trois tables, avec des requêtes paramétrées écrites par nous ;
--   - analyst_ro (SQL généré par le modèle) n'a aucun droit sur le schéma app.
-- Suppression du compte : ON DELETE CASCADE supprime ses sessions et son historique.

-- ---------------------------------------------------------------------------
-- Comptes : email et mot de passe haché (argon2id), rien d'autre (minimisation)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.users (
    id            bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email         text        NOT NULL,
    password_hash text        NOT NULL,
    -- Blocage après 5 échecs consécutifs, pendant 15 minutes
    failed_logins integer     NOT NULL DEFAULT 0,
    locked_until  timestamptz,
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT users_email_normalisee CHECK (email = lower(btrim(email)) AND length(email) BETWEEN 3 AND 254),
    CONSTRAINT users_hash_argon2      CHECK (password_hash LIKE '$argon2%'),
    CONSTRAINT users_failed_logins    CHECK (failed_logins >= 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS users_email_key ON app.users (email);

COMMENT ON TABLE  app.users               IS 'Comptes utilisateurs : email et mot de passe haché uniquement';
COMMENT ON COLUMN app.users.email         IS 'Adresse email, en minuscules (unique)';
COMMENT ON COLUMN app.users.password_hash IS 'Haché argon2id (avec sel), jamais le mot de passe en clair';
COMMENT ON COLUMN app.users.failed_logins IS 'Échecs de connexion consécutifs depuis le dernier succès ou blocage';
COMMENT ON COLUMN app.users.locked_until  IS 'Connexion refusée jusqu''à cette date (5 échecs => 15 minutes)';

-- ---------------------------------------------------------------------------
-- Sessions côté serveur (cookie HttpOnly + SameSite, 8 heures)
-- Seule l'empreinte SHA-256 du jeton est stockée : une fuite de la table ne donne
-- pas de jeton utilisable.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.sessions (
    id         bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id    bigint      NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    token_hash bytea       NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CONSTRAINT sessions_token_hash_sha256 CHECK (octet_length(token_hash) = 32),
    CONSTRAINT sessions_expiration        CHECK (expires_at > created_at)
);
CREATE UNIQUE INDEX IF NOT EXISTS sessions_token_hash_key ON app.sessions (token_hash);
CREATE INDEX IF NOT EXISTS sessions_user_id_idx ON app.sessions (user_id);

COMMENT ON TABLE  app.sessions            IS 'Sessions ouvertes ; invalidées à la déconnexion (revoked_at) ou supprimées avec le compte';
COMMENT ON COLUMN app.sessions.token_hash IS 'SHA-256 du jeton aléatoire posé dans le cookie';

-- ---------------------------------------------------------------------------
-- Historique personnel : questions et réponses de l'agent
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS app.historique (
    id          bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id     bigint      NOT NULL REFERENCES app.users (id) ON DELETE CASCADE,
    question    text        NOT NULL,
    sql_propose text,
    explication text,
    recommandations text[] NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT historique_question_non_vide CHECK (length(btrim(question)) > 0)
);
CREATE INDEX IF NOT EXISTS historique_user_date_idx ON app.historique (user_id, created_at DESC);
-- Base créée avant l'ajout de la colonne (19/11/2026)
ALTER TABLE app.historique ADD COLUMN IF NOT EXISTS recommandations text[] NOT NULL DEFAULT '{}';

COMMENT ON TABLE  app.historique             IS 'Échanges de chaque utilisateur ; lus toujours filtrés sur l''utilisateur de la session';
COMMENT ON COLUMN app.historique.sql_propose IS 'SQL proposé par l''agent (une seule instruction SELECT), exécuté seulement après validation';
COMMENT ON COLUMN app.historique.recommandations IS 'Index ou réécritures suggérés par l''agent, jamais appliqués automatiquement';

-- ---------------------------------------------------------------------------
-- Droits : app_agent lit et écrit les lignes, sans TRUNCATE ni droit sur la structure
-- ---------------------------------------------------------------------------
REVOKE ALL ON ALL TABLES IN SCHEMA app FROM PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.users, app.sessions, app.historique TO app_agent;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO app_agent;
