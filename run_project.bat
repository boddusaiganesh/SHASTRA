@echo off
title SHASTRA Launch Control
color 0B
cls
echo ======================================================================
echo          SHASTRA - Crime Intelligence & Analytical Platform
echo                     Karnataka State Police (KSP)
echo ======================================================================
echo.

set ROOT_DIR=%~dp0
set PYTHON_CMD=

echo [1/3] Detecting Python installation...
echo --------------------------------------------------

:: 1. Check if 'python' works
python --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    echo - Found 'python' command in PATH.
    goto python_found
)

:: 2. Check if 'py' launcher works
py --version >nul 2>nul
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    echo - Found 'py' launcher in PATH.
    goto python_found
)

:: 3. Check common AppData installation paths
echo - Searching in AppData Local Programs...
for /d %%d in ("%LocalAppData%\Programs\Python\Python*") do (
    if exist "%%d\python.exe" (
        set PYTHON_CMD="%%d\python.exe"
        echo - Found Python at: %%d\python.exe
        goto python_found
    )
)

:: 4. Check common Program Files paths
echo - Searching in Program Files...
for /d %%d in ("%ProgramFiles%\Python*") do (
    if exist "%%d\python.exe" (
        set PYTHON_CMD="%%d\python.exe"
        echo - Found Python at: %%d\python.exe
        goto python_found
    )
)

:: 5. Check common Program Files (x86) paths
for /d %%d in ("%ProgramFiles(x86)%\Python*") do (
    if exist "%%d\python.exe" (
        set PYTHON_CMD="%%d\python.exe"
        echo - Found Python at: %%d\python.exe
        goto python_found
    )
)

:python_found
if "%PYTHON_CMD%"=="" (
    color 0C
    echo [ERROR] Python was not found on your system!
    echo.
    echo Please install Python 3.10+ from python.org and make sure to check the
    echo "Add python.exe to PATH" box during installation, or install it from
    echo the Microsoft Store.
    echo.
    pause
    exit /b 1
)

echo - Python configured: %PYTHON_CMD%
echo.

echo [2/3] Setting up Backend API (FastAPI)...
echo --------------------------------------------------
cd /d "%ROOT_DIR%crime_backend\MODULE_2_BACKEND"
if not exist "venv" (
    echo - Creating virtual environment 'venv'...
    %PYTHON_CMD% -m venv venv
    if %errorlevel% neq 0 (
        color 0C
        echo [ERROR] Failed to create Python virtual environment.
        echo.
        pause
        exit /b 1
    )
)
echo - Activating virtual environment...
call venv\Scripts\activate
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to activate virtual environment.
    echo.
    pause
    exit /b 1
)

echo - Installing/verifying backend dependencies...
echo   (This might take a moment if running for the first time...)
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Some dependencies failed to install.
    echo We will still try to start the backend.
    echo.
)
echo - Backend environment prepared!
echo.

echo [3/3] Setting up Frontend Dashboard (React + Vite)...
echo --------------------------------------------------
cd /d "%ROOT_DIR%crime_frontend"
echo - Installing/verifying frontend node modules...
call npm install
if %errorlevel% neq 0 (
    echo [WARNING] npm install reported errors. Attempting to proceed anyway.
)
echo - Frontend environment prepared!
echo.

echo Launching servers...
echo --------------------------------------------------
echo Launching Backend API in a new terminal window...
start "SHASTRA Backend API" cmd /k "title SHASTRA Backend API && cd /d \"%ROOT_DIR%crime_backend\MODULE_2_BACKEND\" && call venv\Scripts\activate && echo [SHASTRA] Starting FastAPI server... && python main.py"

echo Launching Frontend Dashboard in a new terminal window...
start "SHASTRA Frontend Dashboard" cmd /k "title SHASTRA Frontend Dashboard && cd /d \"%ROOT_DIR%crime_frontend\" && echo [SHASTRA] Starting Vite development server... && npm run dev"

echo.
echo ======================================================================
echo SUCCESS: SHASTRA startup initiated successfully!
echo ======================================================================
echo.
echo - Backend API will be available at:      http://localhost:8000
echo - API Documentation (Swagger) at:        http://localhost:8000/docs
echo - Frontend Dashboard will be available at: http://localhost:5173
echo.
echo (Keep the two new terminal windows open while running the application)
echo.
pause
