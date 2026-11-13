-- Rôles et schémas du projet.
-- Exécuté par le superutilisateur technique (POSTGRES_USER), avant 02_schema.sql.
-- Les mots de passe sont lus dans les variables d'environnement du conteneur
-- (IMMO_ADMIN_PASSWORD, ANALYST_RO_PASSWORD, issues de .env) : rien n'est écrit en dur.
-- Idempotent : peut être rejoué sans erreur.
--
--   immo_admin : propriétaire des schémas immo et immo_staging, crée les tables et charge
--                les données. NOSUPERUSER, membre de pg_read_server_files (COPY depuis un
--                fichier serveur ; droit sensible, cf. docs/securite.md).
--   analyst_ro : rôle de l'agent. Lecture seule sur immo, statement_timeout 30 s,
--                lecture de pg_stat_statements (pg_read_all_stats).

\getenv admin_password IMMO_ADMIN_PASSWORD
\getenv ro_password ANALYST_RO_PASSWORD
\if :{?admin_password}
\else
  \echo 'ERREUR : IMMO_ADMIN_PASSWORD absent de l environnement du conteneur.'
  \quit 1
\endif
\if :{?ro_password}
\else
  \echo 'ERREUR : ANALYST_RO_PASSWORD absent de l environnement du conteneur.'
  \quit 1
\endif

-- ---------------------------------------------------------------------------
-- immo_admin
-- ---------------------------------------------------------------------------
SELECT 'CREATE ROLE immo_admin'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'immo_admin')
\gexec
SELECT format('ALTER ROLE immo_admin WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
              :'admin_password')
\gexec

GRANT CONNECT ON DATABASE :"DBNAME" TO immo_admin;
GRANT pg_read_server_files TO immo_admin;

-- Schémas : créés ici (immo_admin n'a pas le droit CREATE sur la base), possédés par immo_admin
CREATE SCHEMA IF NOT EXISTS immo AUTHORIZATION immo_admin;
ALTER SCHEMA immo OWNER TO immo_admin;

CREATE SCHEMA IF NOT EXISTS immo_staging AUTHORIZATION immo_admin;
ALTER SCHEMA immo_staging OWNER TO immo_admin;
REVOKE ALL ON SCHEMA immo_staging FROM PUBLIC;

ALTER ROLE immo_admin SET search_path = immo, public;

-- ---------------------------------------------------------------------------
-- analyst_ro
-- ---------------------------------------------------------------------------
SELECT 'CREATE ROLE analyst_ro'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'analyst_ro')
\gexec
SELECT format('ALTER ROLE analyst_ro WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
              :'ro_password')
\gexec

-- Paramètres de session par défaut
ALTER ROLE analyst_ro SET statement_timeout = '30s';
ALTER ROLE analyst_ro SET idle_in_transaction_session_timeout = '60s';
ALTER ROLE analyst_ro SET default_transaction_read_only = on;
ALTER ROLE analyst_ro SET search_path = immo, public;

-- Droits : connexion + lecture sur le schéma immo uniquement (rien sur immo_staging)
GRANT CONNECT ON DATABASE :"DBNAME" TO analyst_ro;
GRANT USAGE ON SCHEMA immo TO analyst_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA immo TO analyst_ro;
-- Tables et vues créées plus tard par immo_admin dans immo
ALTER DEFAULT PRIVILEGES FOR ROLE immo_admin IN SCHEMA immo GRANT SELECT ON TABLES TO analyst_ro;

-- Lecture de pg_stat_statements pour toutes les requêtes (validé : projet local)
GRANT pg_read_all_stats TO analyst_ro;

-- ---------------------------------------------------------------------------
-- Schéma public : aucun droit de création (déjà le défaut en PG 15+, explicite ici)
-- ---------------------------------------------------------------------------
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
