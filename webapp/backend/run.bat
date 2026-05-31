@echo off
cd /d "%~dp0"
echo Starting Mnemo backend at http://127.0.0.1:8000
echo.
uvicorn app.main:app --reload
