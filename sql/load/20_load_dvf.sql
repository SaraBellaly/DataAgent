-- Chargement de immo.dvf_mutations depuis un fichier DVF géolocalisé (Etalab).
--
-- Transaction : ce fichier ne contient ni BEGIN ni COMMIT. L'appelant l'exécute en une
-- seule transaction (psql --single-transaction, cf. scripts/load.ps1), donc tout ou rien.
--
-- Garde-fou : après lecture du fichier en staging, refuse l'insertion si
-- immo.dvf_mutations contient déjà des mutations sur la période couverte par le fichier
-- (aucune donnée existante n'est modifiée ; d'autres années pourront être ajoutées).
--
-- Fichier (chemin dans le conteneur), surchargeable via psql -v :
--   dvf_file : /data/raw/dvf_2025.csv

\if :{?dvf_file}
\else
  \set dvf_file '/data/raw/dvf_2025.csv'
\endif

-- 1. Fichier brut -> staging
TRUNCATE immo_staging.dvf_raw;

COPY immo_staging.dvf_raw
FROM :'dvf_file'
WITH (FORMAT csv, HEADER MATCH, DELIMITER ',', ENCODING 'UTF8');

SELECT count(*) AS lignes_staging,
       min(date_mutation) AS date_min,
       max(date_mutation) AS date_max
FROM immo_staging.dvf_raw;

-- 2. Garde-fou de période, puis staging -> table typée
DO $$
DECLARE
    d_min date;
    d_max date;
BEGIN
    SELECT min(date_mutation::date), max(date_mutation::date) INTO d_min, d_max
    FROM immo_staging.dvf_raw;

    IF EXISTS (SELECT 1 FROM immo.dvf_mutations
               WHERE date_mutation BETWEEN d_min AND d_max) THEN
        RAISE EXCEPTION 'immo.dvf_mutations contient deja des mutations entre % et % : chargement refuse (rien n''a ete modifie).', d_min, d_max;
    END IF;
END $$;

INSERT INTO immo.dvf_mutations (
    id_mutation, date_mutation, numero_disposition, nature_mutation, valeur_fonciere,
    adresse_numero, adresse_suffixe, adresse_nom_voie, adresse_code_voie, code_postal,
    code_commune, nom_commune, code_departement, ancien_code_commune, ancien_nom_commune,
    id_parcelle, ancien_id_parcelle, numero_volume,
    lot1_numero, lot1_surface_carrez, lot2_numero, lot2_surface_carrez,
    lot3_numero, lot3_surface_carrez, lot4_numero, lot4_surface_carrez,
    lot5_numero, lot5_surface_carrez, nombre_lots,
    code_type_local, type_local, surface_reelle_bati, nombre_pieces_principales,
    code_nature_culture, nature_culture, code_nature_culture_speciale, nature_culture_speciale,
    surface_terrain, longitude, latitude
)
SELECT
    id_mutation,
    date_mutation::date,
    numero_disposition::smallint,
    nature_mutation,
    NULLIF(valeur_fonciere, '')::numeric(15,2),
    NULLIF(adresse_numero, '')::integer,
    NULLIF(adresse_suffixe, ''),
    NULLIF(adresse_nom_voie, ''),
    NULLIF(adresse_code_voie, ''),
    NULLIF(code_postal, ''),
    code_commune,
    nom_commune,
    code_departement,
    NULLIF(ancien_code_commune, ''),
    NULLIF(ancien_nom_commune, ''),
    id_parcelle,
    NULLIF(ancien_id_parcelle, ''),
    NULLIF(numero_volume, ''),
    NULLIF(lot1_numero, ''),
    NULLIF(lot1_surface_carrez, '')::numeric(10,2),
    NULLIF(lot2_numero, ''),
    NULLIF(lot2_surface_carrez, '')::numeric(10,2),
    NULLIF(lot3_numero, ''),
    NULLIF(lot3_surface_carrez, '')::numeric(10,2),
    NULLIF(lot4_numero, ''),
    NULLIF(lot4_surface_carrez, '')::numeric(10,2),
    NULLIF(lot5_numero, ''),
    NULLIF(lot5_surface_carrez, '')::numeric(10,2),
    nombre_lots::smallint,
    NULLIF(code_type_local, '')::smallint,
    NULLIF(type_local, ''),
    NULLIF(surface_reelle_bati, '')::integer,
    NULLIF(nombre_pieces_principales, '')::smallint,
    NULLIF(code_nature_culture, ''),
    NULLIF(nature_culture, ''),
    NULLIF(code_nature_culture_speciale, ''),
    NULLIF(nature_culture_speciale, ''),
    NULLIF(surface_terrain, '')::integer,
    NULLIF(longitude, '')::double precision,
    NULLIF(latitude, '')::double precision
FROM immo_staging.dvf_raw;

ANALYZE immo.dvf_mutations;

SELECT extract(year FROM date_mutation)::int AS annee, count(*) AS nb_lignes
FROM immo.dvf_mutations
GROUP BY 1
ORDER BY 1;

-- Libère l'espace de transit (~700 Mo)
TRUNCATE immo_staging.dvf_raw;
