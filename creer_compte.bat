@echo off
chcp 65001 >nul
title Maélis Orvanne Shop - Nouveau compte
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo Création d'un compte gestionnaire (par exemple pour ton collègue)
python manage.py createsuperuser
pause
