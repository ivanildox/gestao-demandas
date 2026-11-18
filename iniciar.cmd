@echo off
rem =====================================================================
rem  Gestao de Demandas - inicializador via terminal
rem
rem  Uso (a partir da raiz do projeto):
rem      .\iniciar.cmd
rem
rem  Os dados - banco, anexos, inbox e relatorios - ficam sempre em
rem  <projeto>\dados, mesmo executando de outro diretorio.
rem =====================================================================

setlocal
set "RAIZ=%~dp0"
cd /d "%RAIZ%"

set "GESTAO_DEMANDAS_DADOS=%RAIZ%dados"
set "PY=%RAIZ%.venv\Scripts\python.exe"
set "PYW=%RAIZ%.venv\Scripts\pythonw.exe"

if not exist "%PY%" goto :sem_ambiente
echo Iniciando Gestao de Demandas - ambiente de desenvolvimento...
if exist "%PYW%" (
    "%PYW%" -m gestao_demandas
) else (
    "%PY%" -m gestao_demandas
)
goto :fim

:sem_ambiente
echo.
echo [ERRO] Ambiente virtual nao encontrado: %PY%
echo        Crie e prepare o ambiente de desenvolvimento:
echo        python -m venv .venv
echo        .venv\Scripts\pip install -r requirements.txt
exit /b 1

:fim
endlocal
exit /b 0
