-- Extensions nécessaires à l'analyse des requêtes.
-- Exécuté par le superutilisateur technique (POSTGRES_USER) : pg_stat_statements
-- n'est pas une extension « trusted », un rôle ordinaire ne peut pas la créer.
-- pg_stat_statements doit aussi être préchargée (shared_preload_libraries, cf. docker-compose.yml).
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
