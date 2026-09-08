@echo off
title Satr Edu Project Launcher
echo.
echo ===================================================
echo     Satr Edu - Master Project Launcher (All-in-One)
echo ===================================================
echo.
echo This script will start all project layers in separate windows:
echo 1. FastAPI AI Agent Backend (Port 8001)
echo 2. Django Main Backend (Port 8000)
echo 3. React Frontend (Port 5173)
echo Starting services in 3 seconds...
ping -n 4 127.0.0.1 >nul

:: 1. Start FastAPI AI Agent Backend
echo [1/3] Starting FastAPI Backend (with Docker and Celery)...
start "Satr Edu - FastAPI AI Backend (8001)" cmd /k "cd /d d:\Satr_Edu_Ai && run.bat"

:: Wait 3 seconds for docker services to spin up
ping -n 4 127.0.0.1 >nul

:: 2. Start Django Main Backend
echo [2/3] Starting Django Main Backend (8000)...
start "Satr Edu - Django Backend (8000)" cmd /k "cd /d c:\Users\Dell\Downloads\backend-grad && env\Scripts\python.exe manage.py runserver 127.0.0.1:8000"

:: Wait 2 seconds
ping -n 3 127.0.0.1 >nul

:: 3. Start React Frontend
echo [3/3] Starting React Vite Frontend (5173)...
start "Satr Edu - React Frontend (5173)" cmd /k "cd /d c:\Users\Dell\Downloads\satr-edu && npm run dev"

:: Wait 2 seconds
ping -n 3 127.0.0.1 >nul

echo.
echo ===================================================
echo ✅ All services launched! Opening web app...
echo ===================================================
echo.

explorer "http://localhost:5173"

exit
