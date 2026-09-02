@echo off
setlocal

set "PROJECT_DIR=%~dp0"
set "PYTHON_EXE=%PROJECT_DIR%venv\Scripts\python.exe"
set "PORT=8000"
set "RUN_MIGRATE=1"

if /I "%~1"=="--no-migrate" set "RUN_MIGRATE=0"
if not "%~1"=="" if /I not "%~1"=="--no-migrate" set "PORT=%~1"
if /I "%~2"=="--no-migrate" set "RUN_MIGRATE=0"
if not "%~2"=="" if /I not "%~2"=="--no-migrate" set "PORT=%~2"

if not exist "%PYTHON_EXE%" (
  echo [ERRO] Ambiente virtual nao encontrado em "%PROJECT_DIR%venv".
  echo.
  echo Rode estes comandos na pasta do projeto:
  echo   python -m venv venv
  echo   .\venv\Scripts\python.exe -m pip install django
  exit /b 1
)

echo ======================================
echo Iniciando sistema de estoque (Django)
echo Pasta: %PROJECT_DIR%
echo Porta: %PORT%
echo ======================================

cd /d "%PROJECT_DIR%"

if "%RUN_MIGRATE%"=="1" (
  echo.
  echo [1/2] Aplicando migracoes...
  "%PYTHON_EXE%" manage.py migrate
  if errorlevel 1 (
    echo [ERRO] Falha ao aplicar migracoes.
    exit /b 1
  )
) else (
  echo.
  echo [1/2] Migracoes ignoradas com --no-migrate.
)

echo.
echo [2/2] Subindo servidor...
echo Acesse: http://127.0.0.1:%PORT%/
echo Admin:  http://127.0.0.1:%PORT%/admin/
echo Para parar, pressione CTRL + C.
echo.

"%PYTHON_EXE%" manage.py runserver 127.0.0.1:%PORT%

endlocal
