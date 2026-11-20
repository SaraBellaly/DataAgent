-- Vérification de la base : compteurs, valeurs nulles, codes orphelins, rôles.
--
-- Exécuté par analyst_ro (scripts/verify.ps1). Le rôle de l'agent n'a aucun droit d'écriture,
-- donc la vérification ne peut rien modifier. Les tentatives d'écriture (section 4c) tournent
-- dans une transaction terminée par ROLLBACK : même si un droit était ouvert par erreur, rien
-- ne serait persisté.
--
-- Résultat : code 0 si tous les contrôles bloquants passent. Sinon, une erreur est levée et
-- psql s'arrête (ON_ERROR_STOP). Les lignes ATTENTION sont signalées sans faire échouer le script.

\pset footer off
\set QUIET on

-- ---------------------------------------------------------------------------
\echo
\echo '=== 1. Compteurs'
-- ---------------------------------------------------------------------------
SELECT 'immo.insee_communes' AS table_, count(*) AS lignes FROM immo.insee_communes
UNION ALL
SELECT 'immo.dvf_mutations', count(*) FROM immo.dvf_mutations;

SELECT typecom, count(*) AS lignes, count(pmun) AS avec_population
FROM immo.insee_communes GROUP BY typecom ORDER BY typecom;

-- Pas de count(DISTINCT id_mutation) : le tri de 3,8 M de lignes dépasse le statement_timeout
-- de 30 s d'analyst_ro.
SELECT extract(year FROM date_mutation)::int AS annee, count(*) AS lignes,
       min(date_mutation) AS du, max(date_mutation) AS au
FROM immo.dvf_mutations GROUP BY 1 ORDER BY 1;

-- ---------------------------------------------------------------------------
\echo
\echo '=== 2. Valeurs nulles sur les colonnes clés de immo.dvf_mutations'
-- ---------------------------------------------------------------------------
WITH n AS (
    SELECT count(*)                                            AS total,
           count(*) FILTER (WHERE code_commune IS NULL)        AS code_commune,
           count(*) FILTER (WHERE date_mutation IS NULL)       AS date_mutation,
           count(*) FILTER (WHERE valeur_fonciere IS NULL)     AS valeur_fonciere,
           count(*) FILTER (WHERE surface_reelle_bati IS NULL) AS surface_reelle_bati,
           count(*) FILTER (WHERE type_local IS NULL)          AS type_local
    FROM immo.dvf_mutations
)
SELECT v.colonne, v.nulls, round(100.0 * v.nulls / nullif(n.total, 0), 2) AS pct_lignes
FROM n, LATERAL (VALUES
    ('code_commune',        n.code_commune),
    ('date_mutation',       n.date_mutation),
    ('valeur_fonciere',     n.valeur_fonciere),
    ('surface_reelle_bati', n.surface_reelle_bati),
    ('type_local',          n.type_local)
) AS v(colonne, nulls);

-- ---------------------------------------------------------------------------
\echo
\echo '=== 3. Codes DVF absents de immo.insee_communes (liste seule, aucune correction)'
-- ---------------------------------------------------------------------------
-- statut : « documenté » = déjà décrit dans docs/sources.md ; « NOUVEAU » = à analyser.
WITH documentes(code, explication) AS (VALUES
    ('97127', 'Saint-Martin : COG des collectivités non chargé'),
    ('97123', 'Saint-Barthélemy : COG des collectivités non chargé'),
    ('44219', 'Vritz : fusionnée en 2018 dans 44180'),
    ('49069', 'Orée d''Anjou : code 49126 depuis 2025'),
    ('49144', 'Freigné : 44225 en 2018, fusionnée dans 44180')
)
SELECT d.code_commune, min(d.nom_commune) AS nom_dans_dvf, count(*) AS lignes,
       CASE WHEN doc.code IS NULL THEN 'NOUVEAU' ELSE 'documenté' END AS statut,
       doc.explication
FROM immo.dvf_mutations d
LEFT JOIN immo.insee_communes c ON c.code_insee = d.code_commune
LEFT JOIN documentes doc ON doc.code = d.code_commune
WHERE c.code_insee IS NULL
GROUP BY d.code_commune, doc.code, doc.explication
ORDER BY lignes DESC, d.code_commune;

-- ---------------------------------------------------------------------------
\echo
\echo '=== 4a. Rôles : contrôles du catalogue'
-- ---------------------------------------------------------------------------
SELECT json_agg(json_build_object(
           'controle', controle, 'attendu', attendu::text, 'obtenu', coalesce(obtenu::text, 'NULL'),
           'statut', CASE WHEN obtenu IS NOT DISTINCT FROM attendu THEN 'OK' ELSE 'ECHEC' END)) AS cat_json
FROM (VALUES
    ('immo_admin : superutilisateur',                     false,
        (SELECT rolsuper FROM pg_roles WHERE rolname = 'immo_admin')),
    ('immo_admin : CREATEROLE',                           false,
        (SELECT rolcreaterole FROM pg_roles WHERE rolname = 'immo_admin')),
    ('immo_admin : CREATEDB',                             false,
        (SELECT rolcreatedb FROM pg_roles WHERE rolname = 'immo_admin')),
    ('analyst_ro : superutilisateur',                     false,
        (SELECT rolsuper FROM pg_roles WHERE rolname = 'analyst_ro')),
    ('analyst_ro : membre de pg_read_server_files',       false,
        pg_has_role('analyst_ro', 'pg_read_server_files', 'MEMBER')),
    ('analyst_ro : CREATE sur la base',                   false,
        has_database_privilege('analyst_ro', current_database(), 'CREATE')),
    ('analyst_ro : TEMP sur la base',                     false,
        has_database_privilege('analyst_ro', current_database(), 'TEMP')),
    ('analyst_ro : CREATE sur le schéma immo',            false,
        has_schema_privilege('analyst_ro', 'immo', 'CREATE')),
    ('analyst_ro : CREATE sur le schéma public',          false,
        has_schema_privilege('analyst_ro', 'public', 'CREATE')),
    ('analyst_ro : accès au schéma immo_staging',         false,
        has_schema_privilege('analyst_ro', 'immo_staging', 'USAGE')),
    ('analyst_ro : une table de immo modifiable',         false,
        EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'immo' AND c.relkind IN ('r', 'v', 'm', 'p')
                  AND has_table_privilege('analyst_ro', c.oid, 'INSERT, UPDATE, DELETE, TRUNCATE'))),
    ('analyst_ro : SELECT sur tous les objets de immo',   true,
        NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'immo' AND c.relkind IN ('r', 'v', 'm', 'p')
                      AND NOT has_table_privilege('analyst_ro', c.oid, 'SELECT'))),
    ('analyst_ro : statement_timeout = 30s',              true,
        (SELECT 'statement_timeout=30s' = ANY (s.setconfig) FROM pg_db_role_setting s
         WHERE s.setrole = 'analyst_ro'::regrole AND s.setdatabase = 0)),
    ('analyst_ro : lecture seule par défaut',             true,
        (SELECT 'default_transaction_read_only=on' = ANY (s.setconfig) FROM pg_db_role_setting s
         WHERE s.setrole = 'analyst_ro'::regrole AND s.setdatabase = 0)),
    -- Cloisonnement application / agent (fiche de cadrage, section 6.2)
    ('analyst_ro : accès au schéma app',                  false,
        has_schema_privilege('analyst_ro', 'app', 'USAGE')),
    ('analyst_ro : un droit sur une table de app',        false,
        EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app' AND c.relkind IN ('r', 'v', 'm', 'p')
                  AND has_table_privilege('analyst_ro', c.oid, 'SELECT, INSERT, UPDATE, DELETE'))),
    ('app_agent : superutilisateur',                      false,
        (SELECT rolsuper FROM pg_roles WHERE rolname = 'app_agent')),
    ('app_agent : accès au schéma immo',                  false,
        has_schema_privilege('app_agent', 'immo', 'USAGE')),
    ('app_agent : CREATE sur le schéma app',              false,
        has_schema_privilege('app_agent', 'app', 'CREATE')),
    ('app_agent : TRUNCATE sur une table de app',         false,
        EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'app' AND c.relkind = 'r'
                  AND has_table_privilege('app_agent', c.oid, 'TRUNCATE'))),
    ('app_agent : écriture sur les 4 tables de app',      true,
        (SELECT count(*) = 4 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = 'app' AND c.relname IN ('users', 'sessions', 'historique', 'conversations')
           AND has_table_privilege('app_agent', c.oid, 'SELECT, INSERT, UPDATE, DELETE')))
) AS c(controle, attendu, obtenu)
\gset

SELECT * FROM json_to_recordset(:'cat_json') AS (controle text, attendu text, obtenu text, statut text);

-- ---------------------------------------------------------------------------
\echo
\echo '=== 4b. analyst_ro : tentatives d''écriture en mode par défaut (lecture seule)'
-- ---------------------------------------------------------------------------
-- Code attendu 25006 = read_only_sql_transaction.
DO $$
DECLARE
    t   record;
    res jsonb := '[]'::jsonb;
    st  text;
    msg text;
BEGIN
    FOR t IN SELECT * FROM (VALUES
        ('DELETE sur immo.insee_communes', $s$DELETE FROM immo.insee_communes WHERE false$s$, '25006', 'bloquant'),
        ('CREATE TEMP TABLE',             $s$CREATE TEMP TABLE t_verif (x int)$s$,        '25006', 'bloquant')
    ) AS v(test, stmt, attendu, gravite)
    LOOP
        BEGIN
            EXECUTE t.stmt;
            msg := 'accepté';
            st  := CASE t.gravite WHEN 'bloquant' THEN 'ECHEC' ELSE 'ATTENTION' END;
        EXCEPTION WHEN others THEN
            msg := SQLSTATE || ' ' || SQLERRM;
            st  := CASE WHEN SQLSTATE = t.attendu THEN 'OK' ELSE 'ECHEC' END;
        END;
        res := res || jsonb_build_object('test', t.test, 'attendu', 'refus ' || t.attendu,
                                         'obtenu', msg, 'statut', st);
    END LOOP;
    PERFORM set_config('verify.ro_json', res::text, false);
END $$;

SELECT current_setting('verify.ro_json') AS ro_json \gset
SELECT * FROM json_to_recordset(:'ro_json') AS (test text, attendu text, obtenu text, statut text);

-- ---------------------------------------------------------------------------
\echo
\echo '=== 4c. analyst_ro : tentatives d''écriture et de création, lecture seule désactivée'
-- ---------------------------------------------------------------------------
-- BEGIN READ WRITE contourne default_transaction_read_only : seuls les droits protègent.
-- Code attendu 42501 = insufficient_privilege. Tout est annulé par le ROLLBACK final.
BEGIN READ WRITE;

DO $$
DECLARE
    t   record;
    res jsonb := '[]'::jsonb;
    st  text;
    msg text;
BEGIN
    FOR t IN SELECT * FROM (VALUES
        ('INSERT dans immo.insee_communes',
            $s$INSERT INTO immo.insee_communes (code_insee, typecom, tncc, ncc, nccenr, libelle)
               VALUES ('00000', 'COM', 0, 'X', 'X', 'X')$s$,                            '42501', 'bloquant'),
        ('UPDATE de immo.dvf_mutations',
            $s$UPDATE immo.dvf_mutations SET valeur_fonciere = valeur_fonciere WHERE false$s$, '42501', 'bloquant'),
        ('DELETE dans immo.insee_communes',
            $s$DELETE FROM immo.insee_communes WHERE false$s$,                           '42501', 'bloquant'),
        ('TRUNCATE de immo.insee_communes',
            $s$TRUNCATE immo.insee_communes$s$,                                          '42501', 'bloquant'),
        ('COPY depuis un fichier serveur',
            $s$COPY immo.insee_communes FROM '/data/raw/v_commune_2026.csv' (FORMAT csv)$s$, '42501', 'bloquant'),
        ('ALTER TABLE immo.insee_communes',
            $s$ALTER TABLE immo.insee_communes ADD COLUMN x_verif int$s$,                '42501', 'bloquant'),
        ('CREATE INDEX sur immo.dvf_mutations',
            $s$CREATE INDEX i_verif ON immo.dvf_mutations (date_mutation)$s$,            '42501', 'bloquant'),
        ('DROP TABLE immo.insee_communes',
            $s$DROP TABLE immo.insee_communes$s$,                                        '42501', 'bloquant'),
        ('CREATE TABLE dans immo',
            $s$CREATE TABLE immo.t_verif (x int)$s$,                                     '42501', 'bloquant'),
        ('CREATE VIEW dans immo',
            $s$CREATE VIEW immo.v_verif AS SELECT 1 AS x$s$,                              '42501', 'bloquant'),
        ('CREATE TABLE dans public',
            $s$CREATE TABLE public.t_verif (x int)$s$,                                   '42501', 'bloquant'),
        ('CREATE SCHEMA',
            $s$CREATE SCHEMA s_verif$s$,                                                 '42501', 'bloquant'),
        ('Lecture de immo_staging',
            $s$SELECT count(*) FROM immo_staging.dvf_raw$s$,                             '42501', 'bloquant'),
        ('pg_read_file() sur un fichier serveur',
            $s$SELECT pg_read_file('/data/raw/v_commune_2026.csv', 0, 10)$s$,             '42501', 'bloquant'),
        -- Droit TEMP retiré à PUBLIC le 2026-11-14 (01_roles.sql) : contrôle désormais bloquant
        ('CREATE TEMP TABLE (table de session)',
            $s$CREATE TEMP TABLE t_verif (x int)$s$,                                     '42501', 'bloquant')
    ) AS v(test, stmt, attendu, gravite)
    LOOP
        BEGIN
            EXECUTE t.stmt;
            msg := 'accepté';
            st  := CASE t.gravite WHEN 'bloquant' THEN 'ECHEC' ELSE 'ATTENTION' END;
        EXCEPTION WHEN others THEN
            msg := SQLSTATE || ' ' || SQLERRM;
            st  := CASE WHEN SQLSTATE = t.attendu THEN 'OK' ELSE 'ECHEC' END;
        END;
        res := res || jsonb_build_object('test', t.test, 'attendu', 'refus ' || t.attendu,
                                         'obtenu', msg, 'statut', st);
    END LOOP;
    PERFORM set_config('verify.rw_json', res::text, false);
END $$;

-- Lecture du résultat AVANT le ROLLBACK (qui annulerait aussi set_config)
SELECT current_setting('verify.rw_json') AS rw_json \gset
ROLLBACK;

SELECT * FROM json_to_recordset(:'rw_json') AS (test text, attendu text, obtenu text, statut text);

-- ---------------------------------------------------------------------------
\echo
\echo '=== 5. Synthèse'
-- ---------------------------------------------------------------------------
WITH r AS (
    SELECT statut FROM json_to_recordset(:'cat_json') AS (statut text)
    UNION ALL SELECT statut FROM json_to_recordset(:'ro_json') AS (statut text)
    UNION ALL SELECT statut FROM json_to_recordset(:'rw_json') AS (statut text)
)
SELECT count(*) FILTER (WHERE statut = 'OK')        AS ok,
       count(*) FILTER (WHERE statut = 'ECHEC')     AS echecs,
       count(*) FILTER (WHERE statut = 'ATTENTION') AS attention
FROM r
\gset synth_
SELECT :synth_ok AS ok, :synth_echecs AS echecs, :synth_attention AS attention;

-- Échec du script s'il reste au moins un contrôle bloquant en ECHEC
SELECT format('DO $x$ BEGIN RAISE EXCEPTION %L; END $x$',
              'Verification : ' || :synth_echecs || ' controle(s) bloquant(s) en ECHEC')
WHERE :synth_echecs > 0
\gexec
