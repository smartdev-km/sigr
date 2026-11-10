@echo off
setlocal EnableExtensions
chcp 65001 >nul
title SIGR-COMORES - serveur local
cd /d "%~dp0"

set "PORT=5001"
set "FLASK_DEBUG=0"
set "FLASK_APP=run.py"

echo ==============================================
echo    SIGR-COMORES - Serveur local
echo ==============================================
echo.

rem ---------- 1. Python ----------
set "PY="
where py >nul 2>&1
if not errorlevel 1 py -3 --version >nul 2>&1
if not errorlevel 1 set "PY=py -3"
if defined PY goto :python_ok
where python >nul 2>&1
if errorlevel 1 goto :nopython
python --version >nul 2>&1
if errorlevel 1 goto :nopython
set "PY=python"
:python_ok

rem ---------- 2. Environnement virtuel et dépendances ----------
if exist ".venv\Scripts\python.exe" goto :venv_ok
echo Première installation : création de l'environnement Python...
%PY% -m venv .venv
if errorlevel 1 goto :erreur
:venv_ok
set "VPY=.venv\Scripts\python.exe"

echo Vérification des dépendances (la première fois, cela peut prendre une minute)...
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto :erreur

rem ---------- 3. Base de données ----------
set "FIRST_RUN=0"
if not exist "instance\sigr.db" set "FIRST_RUN=1"
"%VPY%" -m flask init-db
if errorlevel 1 goto :erreur
if "%FIRST_RUN%"=="1" call :premiere_fois
if errorlevel 1 goto :erreur

rem ---------- 4. Lancement ----------
echo.
echo ==============================================
echo    Le serveur démarre sur http://127.0.0.1:%PORT%
echo    Pour l'ARRÊTER : fermez cette fenêtre
echo    (ou appuyez sur Ctrl+C)
echo ==============================================
echo.
start "" /b cmd /c "ping -n 4 127.0.0.1 >nul & start http://127.0.0.1:%PORT%"
"%VPY%" run.py
goto :fin

:premiere_fois
echo.
echo --- Création du compte administrateur ---
"%VPY%" -m flask create-admin
if errorlevel 1 exit /b 1
echo.
set "REP="
set /p "REP=Ajouter des données de démonstration fictives ? [O/N] : "
if /i "%REP%"=="O" "%VPY%" -m flask seed-demo
exit /b 0

:nopython
echo.
echo ERREUR : Python n'est pas installé (ou pas dans le PATH).
echo.
echo   1. Téléchargez Python 3.12 sur https://www.python.org/downloads/
echo   2. À l'installation, COCHEZ "Add python.exe to PATH"
echo   3. Relancez ce fichier.
echo.
pause
exit /b 1

:erreur
echo.
echo Une erreur est survenue (voir les messages ci-dessus).
pause
exit /b 1

:fin
echo.
echo Le serveur est arrêté.
pause
