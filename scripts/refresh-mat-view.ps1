# Rafraîchit la vue matérialisée v_prix_m2_commune_mat après chargement de nouvelles données
# Usage : .\scripts\refresh-mat-view.ps1
#
# À exécuter après :
#   - Chargement d'une nouvelle année DVF : .\scripts\load.ps1 -Only dvf -DvfFile dvf_2026.csv
#   - Toute modification des données de immo.dvf_mutations ou immo.insee_communes
#
# Durée attendue : ~5-6 secondes (identique au calcul initial de la vue)

. (Join-Path $PSScriptRoot '_common.ps1')

Wait-Database

$start = Get-Date
Write-Host "Rafraichissement de la vue materialisee v_prix_m2_commune_mat..." -ForegroundColor Cyan

Invoke-Psql -User 'immo_admin' -PsqlArgs @('-c', 'REFRESH MATERIALIZED VIEW immo.v_prix_m2_commune_mat;')
if ($LASTEXITCODE -ne 0) { throw "Echec du rafraichissement (code $LASTEXITCODE)" }

$duration = ((Get-Date) - $start).TotalSeconds
Write-Host ("Rafraichissement termine en {0:N1} s." -f $duration) -ForegroundColor Green

# Vérification
Write-Host "`nVerification..." -ForegroundColor Cyan
Invoke-Psql -User 'analyst_ro' -PsqlArgs @('-c', 'SELECT count(*) AS lignes FROM immo.v_prix_m2_commune_mat;')
