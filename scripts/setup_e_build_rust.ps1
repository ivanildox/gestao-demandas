# =====================================================================
# Script de Compilação e Testes do Sistema Gestão de Demandas (Rust + Tauri v2)
# =====================================================================

$raiz = Split-Path -Parent $PSScriptRoot
Set-Location $raiz

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " Gestão de Demandas - Build & Setup Rust + Tauri" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# Configura o PATH com o compilador Rust e ferramentas binutils
$env:PATH = "$env:USERPROFILE\w64devkit\bin;$env:USERPROFILE\.cargo\bin;$env:PATH"

# Confirma ferramentas
$rustVersion = rustc --version
Write-Host "[✓] $rustVersion detectado." -ForegroundColor Green

# 1. Executa testes unitários do Rust
Write-Host ""
Write-Host "Executando testes unitários do núcleo em Rust..." -ForegroundColor Cyan
cargo test --manifest-path src-tauri/Cargo.toml --verbose

if ($LASTEXITCODE -ne 0) {
    Write-Host "[X] Falha nos testes unitários em Rust!" -ForegroundColor Red
    Exit 1
}

Write-Host "[✓] Todos os testes unitários passaram com sucesso!" -ForegroundColor Green

# 2. Compilação da Aplicação
Write-Host ""
Write-Host "Compilando executável de produção (Release)..." -ForegroundColor Cyan
cargo build --manifest-path src-tauri/Cargo.toml --release

if (Test-Path "$raiz\src-tauri\target\release\gestao_demandas.exe") {
    Copy-Item "$raiz\src-tauri\target\release\gestao_demandas.exe" "$raiz\gestao_demandas.exe" -Force
    Write-Host "[✓] Executável gestao_demandas.exe atualizado na raiz do projeto!" -ForegroundColor Green
    
    # Atualiza atalho na área de trabalho
    & "$PSScriptRoot\criar_atalho_desktop.ps1"
} else {
    Write-Host "[X] Falha na compilação do executável." -ForegroundColor Red
    Exit 1
}
