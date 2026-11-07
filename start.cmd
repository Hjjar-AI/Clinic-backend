@echo off
setlocal
pushd "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" launch.py %*
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" launch.py %*
) else (
    where py >nul 2>nul
    if errorlevel 1 (
        python launch.py %*
    ) else (
        py -3 launch.py %*
    )
)
set "clinic_exit=%errorlevel%"
popd
if not "%clinic_exit%"=="0" if "%~1"=="" pause
exit /b %clinic_exit%
