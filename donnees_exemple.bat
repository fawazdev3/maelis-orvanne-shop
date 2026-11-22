@echo off
chcp 65001 >nul
title Maélis Orvanne Shop - Données d'exemple
cd /d "%~dp0"
call venv\Scripts\activate.bat
python manage.py donnees_exemple
pause
