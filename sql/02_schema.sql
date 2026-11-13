-- Schéma des tables du projet (schéma immo).
-- Exécuté par immo_admin (propriétaire du schéma immo, créé par 01_roles.sql) :
-- les tables lui appartiennent et analyst_ro reçoit SELECT par les droits par défaut.
-- Colonnes établies à partir des en-têtes réels :
--   - data/raw/dvf_2025.csv                                       (DVF géolocalisé Etalab)
--   - data/raw/v_commune_2026.csv                                 (COG 2026, communes)
--   - data/raw/populations_reference_2023/donnees_communes.csv    (populations de référence 2023)
--
-- Décisions validées :
--   - immo.dvf_mutations  : clé technique bigserial (id_mutation n'est pas unique).
--   - immo.insee_communes : clé primaire code_insee, uniquement TYPECOM 'COM' et 'ARM'.
--   - Tous les codes commune en text (zéros en tête, Corse 2A/2B).
--   - Pas de clé étrangère : les codes orphelins sont listés par le script de vérification.
--   - Un seul index B-tree (non UNIQUE) sur dvf_mutations(code_commune).
--   - NOT NULL uniquement sur les colonnes sans valeur vide dans le fichier 2025.
--
-- Idempotent : CREATE ... IF NOT EXISTS (ne modifie pas une table existante).

SET search_path = immo;

-- ---------------------------------------------------------------------------
-- Référentiel des communes : COG 2026 (COM + ARM) + populations de référence 2023
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS immo.insee_communes (
    code_insee   text     PRIMARY KEY,
    typecom      text     NOT NULL CHECK (typecom IN ('COM', 'ARM')),
    reg          text,
    dep          text,
    ctcd         text,
    arr          text,
    tncc         smallint NOT NULL,
    ncc          text     NOT NULL,
    nccenr       text     NOT NULL,
    libelle      text     NOT NULL,
    can          text,
    comparent    text,
    pmun         integer,
    ptot         integer
);

COMMENT ON TABLE  immo.insee_communes            IS 'Communes (COM) et arrondissements municipaux (ARM) du COG INSEE 2026, avec populations de référence 2023. Saint-Barthélemy (97123) et Saint-Martin (97127) sont hors référentiel.';
COMMENT ON COLUMN immo.insee_communes.code_insee IS 'Code commune INSEE (COG.COM), 5 caractères, zéros en tête, 2A/2B pour la Corse';
COMMENT ON COLUMN immo.insee_communes.typecom    IS 'COM = commune, ARM = arrondissement municipal (Paris, Lyon, Marseille)';
COMMENT ON COLUMN immo.insee_communes.reg        IS 'Code région';
COMMENT ON COLUMN immo.insee_communes.dep        IS 'Code département';
COMMENT ON COLUMN immo.insee_communes.ctcd       IS 'Code de la collectivité territoriale ayant les compétences départementales';
COMMENT ON COLUMN immo.insee_communes.arr        IS 'Code arrondissement départemental';
COMMENT ON COLUMN immo.insee_communes.tncc       IS 'Type de nom en clair (article), 0 à 8';
COMMENT ON COLUMN immo.insee_communes.ncc        IS 'Nom en clair, majuscules';
COMMENT ON COLUMN immo.insee_communes.nccenr     IS 'Nom en clair, typographie riche';
COMMENT ON COLUMN immo.insee_communes.libelle    IS 'Nom en clair, typographie riche, avec article';
COMMENT ON COLUMN immo.insee_communes.can        IS 'Code canton';
COMMENT ON COLUMN immo.insee_communes.comparent  IS 'Code de la commune parente (renseigné pour les ARM)';
COMMENT ON COLUMN immo.insee_communes.pmun       IS 'Population municipale 2023 (indicateur principal). NULL pour 75056, 69123, 13055 (comptés par arrondissement) et Mayotte';
COMMENT ON COLUMN immo.insee_communes.ptot       IS 'Population totale 2023';

-- ---------------------------------------------------------------------------
-- Transactions DVF géolocalisées (une ligne par ligne du fichier Etalab)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS immo.dvf_mutations (
    id                           bigserial PRIMARY KEY,
    id_mutation                  text          NOT NULL,
    date_mutation                date          NOT NULL,
    numero_disposition           smallint      NOT NULL,
    nature_mutation              text          NOT NULL,
    valeur_fonciere              numeric(15,2),
    adresse_numero               integer,
    adresse_suffixe              text,
    adresse_nom_voie             text,
    adresse_code_voie            text,
    code_postal                  text,
    code_commune                 text          NOT NULL,
    nom_commune                  text          NOT NULL,
    code_departement             text          NOT NULL,
    ancien_code_commune          text,
    ancien_nom_commune           text,
    id_parcelle                  text          NOT NULL,
    ancien_id_parcelle           text,
    numero_volume                text,
    lot1_numero                  text,
    lot1_surface_carrez          numeric(10,2),
    lot2_numero                  text,
    lot2_surface_carrez          numeric(10,2),
    lot3_numero                  text,
    lot3_surface_carrez          numeric(10,2),
    lot4_numero                  text,
    lot4_surface_carrez          numeric(10,2),
    lot5_numero                  text,
    lot5_surface_carrez          numeric(10,2),
    nombre_lots                  smallint      NOT NULL,
    code_type_local              smallint,
    type_local                   text,
    surface_reelle_bati          integer,
    nombre_pieces_principales    smallint,
    code_nature_culture          text,
    nature_culture               text,
    code_nature_culture_speciale text,
    nature_culture_speciale      text,
    surface_terrain              integer,
    longitude                    double precision,
    latitude                     double precision
);

COMMENT ON TABLE  immo.dvf_mutations                    IS 'Demandes de valeurs foncières géolocalisées (Etalab). Une mutation peut couvrir plusieurs lignes ; valeur_fonciere est alors répétée sur chacune.';
COMMENT ON COLUMN immo.dvf_mutations.id                 IS 'Clé technique (id_mutation n''est pas unique)';
COMMENT ON COLUMN immo.dvf_mutations.numero_disposition IS 'Numéro de disposition ; fourni sur 6 caractères dans le fichier (lpad(numero_disposition::text, 6, ''0''))';
COMMENT ON COLUMN immo.dvf_mutations.valeur_fonciere    IS 'Prix de la mutation en euros, répété sur toutes les lignes de la mutation';
COMMENT ON COLUMN immo.dvf_mutations.code_commune       IS 'Code commune INSEE (clé de jointure vers insee_communes.code_insee). Arrondissements pour Paris, Lyon, Marseille';
COMMENT ON COLUMN immo.dvf_mutations.surface_reelle_bati IS 'Surface réelle bâtie en m² (peut valoir 0)';
COMMENT ON COLUMN immo.dvf_mutations.surface_terrain    IS 'Surface de terrain en m²';

CREATE INDEX IF NOT EXISTS dvf_mutations_code_commune_idx
    ON immo.dvf_mutations (code_commune);
