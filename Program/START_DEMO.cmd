@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
    echo uv was not found. See DEMO_GUIDE.md for setup instructions.
    pause
    exit /b 1
)
uv run --locked python.exe src/demo/server.py --open
if errorlevel 1 pause
endlocal
