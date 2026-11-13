-- Tables de transit pour le chargement (schéma immo_staging).
-- Exécuté par immo_admin. Le schéma immo_staging est créé par 01_roles.sql
-- (propriétaire immo_admin, aucun droit pour PUBLIC ni analyst_ro).
-- - UNLOGGED : non journalisées (rapides, vidées en cas de crash : sans importance ici).
-- - Toutes les colonnes en text, noms identiques aux en-têtes des fichiers :
--   COPY ... HEADER MATCH refuse un fichier dont l'en-tête aurait changé.
-- Idempotent.

-- data/raw/dvf_2025.csv (séparateur ',')
CREATE UNLOGGED TABLE IF NOT EXISTS immo_staging.dvf_raw (
    id_mutation                  text,
    date_mutation                text,
    numero_disposition           text,
    nature_mutation              text,
    valeur_fonciere              text,
    adresse_numero               text,
    adresse_suffixe              text,
    adresse_nom_voie             text,
    adresse_code_voie            text,
    code_postal                  text,
    code_commune                 text,
    nom_commune                  text,
    code_departement             text,
    ancien_code_commune          text,
    ancien_nom_commune           text,
    id_parcelle                  text,
    ancien_id_parcelle           text,
    numero_volume                text,
    lot1_numero                  text,
    lot1_surface_carrez          text,
    lot2_numero                  text,
    lot2_surface_carrez          text,
    lot3_numero                  text,
    lot3_surface_carrez          text,
    lot4_numero                  text,
    lot4_surface_carrez          text,
    lot5_numero                  text,
    lot5_surface_carrez          text,
    nombre_lots                  text,
    code_type_local              text,
    type_local                   text,
    surface_reelle_bati          text,
    nombre_pieces_principales    text,
    code_nature_culture          text,
    nature_culture               text,
    code_nature_culture_speciale text,
    nature_culture_speciale      text,
    surface_terrain              text,
    longitude                    text,
    latitude                     text
);

-- data/raw/v_commune_2026.csv (séparateur ',', valeurs entre guillemets)
CREATE UNLOGGED TABLE IF NOT EXISTS immo_staging.cog_communes_raw (
    "TYPECOM"   text,
    "COM"       text,
    "REG"       text,
    "DEP"       text,
    "CTCD"      text,
    "ARR"       text,
    "TNCC"      text,
    "NCC"       text,
    "NCCENR"    text,
    "LIBELLE"   text,
    "CAN"       text,
    "COMPARENT" text
);

-- data/raw/populations_reference_2023/donnees_communes.csv (séparateur ';')
CREATE UNLOGGED TABLE IF NOT EXISTS immo_staging.populations_communes_raw (
    "REG"     text,
    "Région"  text,
    "DEP"     text,
    "CODARR"  text,
    "CODCAN"  text,
    "CODCOM"  text,
    "COM"     text,
    "Commune" text,
    "PMUN"    text,
    "PCAP"    text,
    "PTOT"    text
);
