# Sources de données

Tous les fichiers sont à déposer dans `data/raw/` (non versionné).

## DVF géolocalisé (Etalab)

- Page du jeu de données (adresse fournie par l'API, vérifiée) :
  https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees
- Méthode de récupération utilisée : l'**API data.gouv.fr**, car l'adresse du fichier change à
  chaque publication.
  - Jeu de données : identifiant `5cc1b94a634f4165e96436c1`, interrogé à l'adresse
    https://www.data.gouv.fr/api/1/datasets/5cc1b94a634f4165e96436c1/
  - Ressource retenue : celle intitulée **« DVF 2025 »**, au format `csv.gz` (fichier
    `full-2025.csv.gz`, 116 267 867 octets).
  - Publication utilisée : **20 octobre 2026** (`created_at` = 2026-10-20 dans l'API). Adresse
    du fichier à cette date :
    https://static.data.gouv.fr/resources/demandes-de-valeurs-foncieres-geolocalisees/20261020-114721/full-2025.csv.gz
- Fichiers dans `data/raw/` :
  - `dvf_2025.csv.gz` : l'archive téléchargée, conservée ;
  - **`dvf_2025.csv`** : le fichier décompressé (731 194 611 octets), **seul fichier lu par le
    chargement** (nom attendu par défaut par `scripts/load.ps1`).
- Contenu : 3 793 113 lignes, toutes datées de 2025 (du 2025-01-01 au 2025-12-31) ; séparateur
  `,`, décimales avec un point, dates `AAAA-MM-JJ`, codes commune sur 5 caractères.
- Périmètre retenu : **une seule année complète**, la plus récente au moment du chargement.
- Particularités : une mutation peut s'étendre sur plusieurs lignes (une par lot ou local),
  et la valeur foncière est répétée sur chacune de ces lignes.
- Procédure pas à pas (téléchargement par l'API, décompression) : voir `INSTALL.md`, étape 5.1.

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
| 44219 | Vritz | 4 | **Fusionné le 01/01/2018** dans Vallons-de-l'Erdre (44180). Les transactions DVF 2025 avec ce code utilisent l'ancien code communal. Source : `v_mvt_commune_2026.csv`, MOD=32. |
| 49069 | Orée d'Anjou | 2 | Commune fusionnée créée le 15/12/2015 par fusion de 9 communes. **Code changé le 01/01/2025** en 49126. Les 2 transactions DVF avec l'ancien code 49069 datent pourtant du 18/06 et du 01/07/2025, après le changement. Source : `v_mvt_commune_2026.csv`, MOD=50. |
| 49144 | Freigné | 1 | **Changement de département le 01/01/2018** : passage du département 49 (Maine-et-Loire) au 44 (Loire-Atlantique) sous le code 44225, puis, le même jour, fusion dans Vallons-de-l'Erdre (**44180**), dont Freigné est désormais commune déléguée. Le code 44225 n'existe donc plus dans le COG 2026. Source : `v_mvt_commune_2026.csv`, MOD=41 puis MOD=32. |

Ces 7 ventes ont toutes été signées en 2025 (du 31/03 au 01/07/2025), donc **après** les changements de code : DVF conserve ici des codes communaux périmés. Commune actuelle : 44180 pour 44219 et 49144, 49126 pour 49069. Aucune correction n'est appliquée aux données.

Conséquence : les jointures `dvf_mutations` ↔ `insee_communes` doivent être des `LEFT JOIN`
pour ne pas perdre ces lignes, ou des `INNER JOIN` assumés quand le référentiel est requis.

## Populations : codes sans valeur

`pmun` et `ptot` sont NULL pour 20 codes du COG :
- **75056, 69123, 13055** (Paris, Lyon, Marseille) : la population est publiée par arrondissement (ARM).
- **Les 17 communes de Mayotte (976xx)** : elles sont absentes du fichier d'ensemble « France hors Mayotte ».

## Densité

Optionnelle. À traiter plus tard.
