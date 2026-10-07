@echo off
REM ================================================================
REM Build script – builds frontend then starts backend
REM ================================================================

REM Set the frontend directory (update this path)
set FRONTEND_DIR=C:\Users\MhmmdAli\Desktop\MyClinicFrontend

echo.
echo ========================================
echo  Building Frontend...
echo ========================================
cd /d "%FRONTEND_DIR%"
call npm install
call npm run build
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Frontend build failed!
    pause
    exit /b 1
)
echo [OK] Frontend built successfully.
echo.

echo ========================================
echo  Starting Backend...
echo ========================================
cd /d "%~dp0"
python run.py
pause