-- Chargement de immo.insee_communes : COG (COM + ARM) + populations de référence.
--
-- Transaction : ce fichier ne contient ni BEGIN ni COMMIT. L'appelant l'exécute en une
-- seule transaction (psql --single-transaction, cf. scripts/load.ps1), donc tout ou rien.
--
-- Garde-fou : refuse de s'exécuter si immo.insee_communes contient déjà des lignes
-- (aucune donnée existante n'est modifiée ; un rechargement exige un TRUNCATE manuel).
--
-- Fichiers (chemins dans le conteneur), surchargeables via psql -v :
--   cog_file : /data/raw/v_commune_2026.csv
--   pop_file : /data/raw/populations_reference_2023/donnees_communes.csv

\if :{?cog_file}
\else
  \set cog_file '/data/raw/v_commune_2026.csv'
\endif
\if :{?pop_file}
\else
  \set pop_file '/data/raw/populations_reference_2023/donnees_communes.csv'
\endif

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM immo.insee_communes) THEN
        RAISE EXCEPTION 'immo.insee_communes contient deja des donnees : chargement refuse (rien n''a ete modifie).';
    END IF;
END $$;

-- 1. Fichiers bruts -> staging (tables de transit, vidées à chaque chargement)
TRUNCATE immo_staging.cog_communes_raw, immo_staging.populations_communes_raw;

COPY immo_staging.cog_communes_raw
FROM :'cog_file'
WITH (FORMAT csv, HEADER MATCH, DELIMITER ',', ENCODING 'UTF8');

COPY immo_staging.populations_communes_raw
FROM :'pop_file'
WITH (FORMAT csv, HEADER MATCH, DELIMITER ';', ENCODING 'UTF8');

-- 2. Staging -> table typée
-- Le COG écrit les valeurs vides sous la forme "" (chaîne vide, pas NULL) : NULLIF.
INSERT INTO immo.insee_communes
    (code_insee, typecom, reg, dep, ctcd, arr, tncc, ncc, nccenr, libelle, can, comparent, pmun, ptot)
SELECT
    c."COM",
    c."TYPECOM",
    NULLIF(c."REG", ''),
    NULLIF(c."DEP", ''),
    NULLIF(c."CTCD", ''),
    NULLIF(c."ARR", ''),
    c."TNCC"::smallint,
    c."NCC",
    c."NCCENR",
    c."LIBELLE",
    NULLIF(c."CAN", ''),
    NULLIF(c."COMPARENT", ''),
    NULLIF(p."PMUN", '')::integer,
    NULLIF(p."PTOT", '')::integer
FROM immo_staging.cog_communes_raw c
LEFT JOIN immo_staging.populations_communes_raw p ON p."COM" = c."COM"
WHERE c."TYPECOM" IN ('COM', 'ARM');

ANALYZE immo.insee_communes;

-- Résumé
SELECT typecom, count(*) AS nb_lignes, count(pmun) AS avec_population
FROM immo.insee_communes
GROUP BY typecom
ORDER BY typecom;

TRUNCATE immo_staging.cog_communes_raw, immo_staging.populations_communes_raw;
