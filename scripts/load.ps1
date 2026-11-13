# Charge les fichiers de data/raw dans PostgreSQL (staging puis INSERT typé).
# Pré-requis : .\scripts\init-db.ps1 exécuté (tables créées).
#
# Garde-fous (dans le SQL) :
#   - insee_communes : refus si la table contient déjà des lignes.
#   - dvf_mutations  : refus si la période du fichier est déjà chargée.
# Aucune donnée existante n'est modifiée ; seules les tables de transit (immo_staging) sont vidées.
#
# Usage :
#   .\scripts\load.ps1                          # communes + DVF 2025
#   .\scripts\load.ps1 -DryRun                  # même chargement dans BEGIN ... ROLLBACK (rien n'est persisté)
#   .\scripts\load.ps1 -Only dvf -DvfFile dvf_2024.csv
#   .\scripts\load.ps1 -Only insee

param(
    [ValidateSet('all', 'insee', 'dvf')][string]$Only = 'all',
    [string]$DvfFile = 'dvf_2025.csv',
    [string]$CogFile = 'v_commune_2026.csv',
    [string]$PopFile = 'populations_reference_2023/donnees_communes.csv',
    [switch]$DryRun
)

. (Join-Path $PSScriptRoot '_common.ps1')

foreach ($f in @($DvfFile, $CogFile, $PopFile)) {
    if (-not (Test-Path (Join-Path $ProjectRoot "data/raw/$f"))) { throw "Fichier introuvable : data/raw/$f" }
}

Wait-Database
$start = Get-Date

# Fichiers à exécuter, dans l'ordre (tout en tant que immo_admin : non superutilisateur, pg_read_server_files)
$steps = @('/sql/load/00_staging.sql')
if ($Only -in 'all', 'insee') { $steps += '/sql/load/10_load_insee.sql' }
if ($Only -in 'all', 'dvf')   { $steps += '/sql/load/20_load_dvf.sql' }

$vars = @{
    cog_file = "/data/raw/$CogFile"
    pop_file = "/data/raw/$PopFile"
    dvf_file = "/data/raw/$DvfFile"
}

if ($DryRun) {
    # Une seule session, une seule transaction annulée à la fin : rien n'est persisté.
    Write-Host "MODE TEST : BEGIN ... ROLLBACK (aucune donnee persistee)" -ForegroundColor Yellow
    $script = @('BEGIN;') + ($steps | ForEach-Object { "\i $_" }) + @('ROLLBACK;')
    $a = @('-v', 'ON_ERROR_STOP=1')
    foreach ($k in $vars.Keys) { $a += @('-v', "$k=$($vars[$k])") }
    $code = Invoke-Psql -User 'immo_admin' -PsqlArgs $a -InputText ($script -join "`n")
    if ($code -ne 0) { throw "Echec du test (code $code) : transaction annulee." }
}
else {
    Invoke-SqlFile '/sql/load/00_staging.sql' -User 'immo_admin'
    if ($Only -in 'all', 'insee') {
        Invoke-SqlFile '/sql/load/10_load_insee.sql' -User 'immo_admin' -SingleTransaction -Vars @{
            cog_file = $vars.cog_file; pop_file = $vars.pop_file }
    }
    if ($Only -in 'all', 'dvf') {
        Invoke-SqlFile '/sql/load/20_load_dvf.sql' -User 'immo_admin' -SingleTransaction -Vars @{
            dvf_file = $vars.dvf_file }
    }
}

Write-Host ("{0} en {1:N0} s." -f $(if ($DryRun) { 'Test termine' } else { 'Chargement termine' }), ((Get-Date) - $start).TotalSeconds) -ForegroundColor Green
