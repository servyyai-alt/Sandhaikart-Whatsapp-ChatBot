@echo off
if exist venv\Scripts\activate call venv\Scripts\activate
if "%PORT%"=="" set PORT=8000
uvicorn app.main:app --host 0.0.0.0 --port %PORT%
