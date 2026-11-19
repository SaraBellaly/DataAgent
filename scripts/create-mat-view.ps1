# Crée la vue matérialisée v_prix_m2_commune_mat pour optimisation des performances
# Usage : .\scripts\create-mat-view.ps1

. (Join-Path $PSScriptRoot '_common.ps1')

Wait-Database
Invoke-SqlFile '/sql/04_materialized_view.sql' -User 'immo_admin'
Write-Host "Vue materialisee creee avec succes." -ForegroundColor Green
