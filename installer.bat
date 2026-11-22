@echo off
chcp 65001 >nul
title Maélis Orvanne Shop - Installation
cd /d "%~dp0"
echo ============================================
echo   Maélis Orvanne Shop - Installation
echo ============================================
echo.
where python >nul 2>nul
if errorlevel 1 (
  echo [ERREUR] Python n'est pas installé ou pas dans le PATH.
  echo Installe Python depuis https://www.python.org/downloads/ en cochant "Add Python to PATH".
  pause
  exit /b 1
)
if not exist venv (
  echo [1/4] Création de l'environnement virtuel...
  python -m venv venv
) else (
  echo [1/4] Environnement virtuel déjà présent.
)
call venv\Scripts\activate.bat
echo [2/4] Installation des dépendances...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 (
  echo [ERREUR] L'installation des dépendances a échoué.
  pause
  exit /b 1
)
if not exist .env (
  echo Création du fichier .env à partir de .env.exemple...
  copy .env.exemple .env >nul
)
echo [3/4] Création de la base de données...
python manage.py migrate
echo.
echo [4/4] Création de ton compte gestionnaire (pour te connecter au back-office)
python manage.py createsuperuser
echo.
echo Installation terminée. Lance maintenant "lancer.bat".
pause
