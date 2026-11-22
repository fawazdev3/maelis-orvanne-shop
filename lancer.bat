@echo off
chcp 65001 >nul
title Maélis Orvanne Shop - Serveur
cd /d "%~dp0"
if not exist venv (
  echo L'installation n'a pas encore été faite : lance d'abord "installer.bat".
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python manage.py migrate --noinput >nul
echo ============================================
echo   Maélis Orvanne Shop
echo   Back-office : http://127.0.0.1:8000/gestion/
echo   Ferme cette fenêtre pour arrêter le serveur.
echo ============================================
start "" http://127.0.0.1:8000/gestion/
python manage.py runserver
pause
