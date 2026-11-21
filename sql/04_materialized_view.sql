-- Vue matérialisée pour v_prix_m2_commune : optimisation des performances
-- Exécuté par immo_admin (propriétaire du schéma immo).
-- La vue originale v_prix_m2_commune reste disponible pour recalculs ponctuels.
--
-- Contexte : la vue v_prix_m2_commune prend 5-50 secondes car PostgreSQL doit scanner
-- les 3,8M lignes DVF et agréger 1,3M mutations avant de pouvoir appliquer les filtres
-- WHERE. Même une requête sur UNE commune prend 5+ secondes.
--
-- Solution : vue matérialisée pré-calculée avec index sur (code_commune, annee).
-- Requêtes filtrées : moins de 2 ms au lieu de 5-50 s.
-- Contrepartie : données figées jusqu'au prochain REFRESH MATERIALIZED VIEW.
--
-- Idempotent et SANS suppression : la vue est créée si elle n'existe pas, sinon rafraîchie à partir
-- des tables. Les tables dvf_mutations et insee_communes ne sont jamais modifiées.

SET search_path = immo;

-- La vue existe-t-elle déjà ? (rafraîchissement seulement dans ce cas : sinon la création suffit)
SELECT EXISTS (
    SELECT 1 FROM pg_matviews WHERE schemaname = 'immo' AND matviewname = 'v_prix_m2_commune_mat'
) AS vue_existante
\gset

CREATE MATERIALIZED VIEW IF NOT EXISTS immo.v_prix_m2_commune_mat AS
SELECT * FROM immo.v_prix_m2_commune
WITH DATA;

\if :vue_existante
  \echo 'Vue matérialisée déjà présente : rafraîchissement à partir des tables.'
  REFRESH MATERIALIZED VIEW immo.v_prix_m2_commune_mat;
\endif

-- Index sur les colonnes les plus filtrées
CREATE INDEX IF NOT EXISTS v_prix_m2_commune_mat_commune_annee_idx
    ON immo.v_prix_m2_commune_mat (code_commune, annee);

CREATE INDEX IF NOT EXISTS v_prix_m2_commune_mat_annee_idx
    ON immo.v_prix_m2_commune_mat (annee);

-- Index pour les tris sur prix_m2_moyen (requête "top 10")
CREATE INDEX IF NOT EXISTS v_prix_m2_commune_mat_prix_idx
    ON immo.v_prix_m2_commune_mat (annee, prix_m2_moyen DESC)
    WHERE nb_ventes >= 100;

-- analyst_ro reçoit SELECT par les droits par défaut (ALTER DEFAULT PRIVILEGES, cf. 01_roles.sql)
ANALYZE immo.v_prix_m2_commune_mat;

-- Comptage
SELECT count(*) AS lignes_vue_mat FROM immo.v_prix_m2_commune_mat;

COMMENT ON MATERIALIZED VIEW immo.v_prix_m2_commune_mat IS
    'Vue matérialisée de v_prix_m2_commune pour optimisation des performances. Requêtes filtrées : moins de 2 ms au lieu de 5-50 s. Rafraîchir avec REFRESH MATERIALIZED VIEW après chargement de nouvelles données DVF.';
