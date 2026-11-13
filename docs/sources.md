# Sources de données

Tous les fichiers sont à déposer dans `data/raw/` (non versionné).

## DVF géolocalisé (Etalab)

- Page : https://www.data.gouv.fr/fr/datasets/demandes-de-valeurs-foncieres-geolocalisees/
- Fichiers par année : https://files.data.gouv.fr/geo-dvf/latest/csv/
- Fichier attendu : `<annee>/full.csv.gz` (France entière), à décompresser.
- Périmètre retenu : **une seule année complète**, la plus récente (à vérifier sur la page :
  le dernier millésime contient en général une année en cours incomplète).
- Particularités : une mutation peut s'étendre sur plusieurs lignes (une par lot ou local),
  et la valeur foncière est répétée sur chacune de ces lignes.

## Référentiel des communes (INSEE, Code officiel géographique)

- Page : https://www.insee.fr/fr/information/2560452 (COG, millésime le plus récent)
- Fichier attendu : la liste des communes au format CSV.
- Point à vérifier à l'import : présence des **arrondissements municipaux** de Paris, Lyon et
  Marseille (codes 751xx, 6938x, 132xx), utilisés par DVF.

## Populations de référence (INSEE, ex-« populations légales »)

- Depuis le millésime 2022, l'INSEE parle de « populations de référence » et non plus de « populations légales ».
- Millésime utilisé : **2023**, fichier d'ensemble France hors Mayotte.
- Page : https://www.insee.fr/fr/statistiques/8680726?sommaire=8681011
- Fichier : `ensemble.zip`, conservé sous `data/raw/populations_reference_2023_ensemble.zip`
  et extrait dans `data/raw/populations_reference_2023/`. Seul `donnees_communes.csv` (séparateur `;`) est chargé.
- Colonnes reprises : `PMUN` (population municipale, indicateur principal) et `PTOT` (population totale).

## Référentiel des communes : fichier retenu

- COG millésime **2026**, `v_commune_2026.csv`, téléchargé depuis
  https://www.insee.fr/fr/statistiques/fichier/8740222/v_commune_2026.csv.
- Seules les lignes `TYPECOM` = `COM` (communes) et `ARM` (arrondissements municipaux) sont chargées.

## Codes DVF hors référentiel

Il n'y a pas de clé étrangère : ces codes sont chargés tels quels dans `dvf_mutations`, et le
script de vérification les liste avec leur nombre de lignes, sans les corriger.

| Code  | Territoire        | Lignes DVF 2025 | Raison |
|-------|-------------------|-----------------|--------|
| 97123 | Saint-Barthélemy  | 160 | Collectivité d'outre-mer. Elle figure dans le fichier COG des collectivités (`v_commune_comer`), qui n'est **volontairement pas chargé**. |
| 97127 | Saint-Martin      | 646 | Même cas. |
| 44219, 49069, 49144 | à identifier | 4, 2, 1 | Absents du COG 2026 (`COM`/`ARM`). Probablement d'anciennes communes fusionnées, à confirmer avec `v_mvt_commune_2026`. |

Conséquence : les jointures `dvf_mutations` ↔ `insee_communes` doivent être des `LEFT JOIN`
pour ne pas perdre ces lignes, ou des `INNER JOIN` assumés quand le référentiel est requis.

## Populations : codes sans valeur

`pmun` et `ptot` sont NULL pour 20 codes du COG :
- **75056, 69123, 13055** (Paris, Lyon, Marseille) : la population est publiée par arrondissement (ARM).
- **Les 17 communes de Mayotte (976xx)** : elles sont absentes du fichier d'ensemble « France hors Mayotte ».

## Densité

Optionnelle. À traiter plus tard.
