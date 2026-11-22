@echo off
chcp 65001 >nul
title Maélis Orvanne Shop - Tests
cd /d "%~dp0"
call venv\Scripts\activate.bat
python manage.py test
pause
