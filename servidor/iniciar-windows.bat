@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>nul || (echo Instale o Python em https://www.python.org/downloads/ ^(marque "Add Python to PATH"^) e abra este arquivo de novo. & pause & exit /b)
if not exist .venv (
  echo Primeira vez: instalando o servidor ^(leva 1 a 3 minutos^)...
  python -m venv .venv || (pause & exit /b)
)
call .venv\Scripts\activate
python -m pip install -q --upgrade pip
python -m pip install -q -U -r requirements.txt || (echo Falhou a instalacao. & pause & exit /b)
python servidor.py
pause
