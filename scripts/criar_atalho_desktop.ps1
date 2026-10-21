# =====================================================================
# Cria o atalho na Área de Trabalho para o Gestão de Demandas (Rust)
# =====================================================================

$raiz = Split-Path -Parent $PSScriptRoot
$exePath = Join-Path $raiz "gestao_demandas.exe"
$iconPath = Join-Path $raiz "src-tauri\icons\icon.ico"

if (-not (Test-Path $exePath)) {
    $releaseExe = Join-Path $raiz "src-tauri\target\release\gestao_demandas.exe"
    if (Test-Path $releaseExe) {
        Copy-Item $releaseExe $exePath -Force
    } else {
        Write-Error "Executável gestao_demandas.exe não encontrado. Compile o projeto primeiro."
        Exit 1
    }
}

$desktop = [Environment]::GetFolderPath("Desktop")
$atalhoPath = Join-Path $desktop "Gestão de Demandas.lnk"

$shell = New-Object -ComObject WScript.Shell
$atalho = $shell.CreateShortcut($atalhoPath)
$atalho.TargetPath = $exePath
$atalho.WorkingDirectory = $raiz
if (Test-Path $iconPath) {
    $atalho.IconLocation = "$iconPath,0"
}
$atalho.Description = "Sistema Desktop de Gestão de Demandas em Rust"
$atalho.Save()

Write-Host "Atalho criado com sucesso na Área de Trabalho: $atalhoPath" -ForegroundColor Green
