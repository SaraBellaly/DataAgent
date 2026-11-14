# Vérifie la base : compteurs, valeurs nulles, codes orphelins, droits des rôles.
# S'exécute en tant que analyst_ro (lecture seule) : ne modifie aucune donnée.
# Code de sortie non nul si un contrôle bloquant échoue.
# Usage : .\scripts\verify.ps1

. (Join-Path $PSScriptRoot '_common.ps1')

Wait-Database
Invoke-SqlFile '/sql/verify.sql' -User 'analyst_ro'
Write-Host "Verification terminee : tous les controles bloquants sont OK." -ForegroundColor Green
