# =====================================================================
# Visualizador Rápido da Interface Gráfica no Navegador
# =====================================================================

$indexPath = Join-Path $PSScriptRoot "..\ui\index.html"
Write-Host "Abrindo a interface do Gestão de Demandas no navegador padrão..." -ForegroundColor Cyan
Start-Process (Resolve-Path $indexPath)
