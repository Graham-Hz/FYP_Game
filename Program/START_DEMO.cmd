@echo off
setlocal DisableDelayedExpansion
cd /d "%~dp0"
set "DEMO_CHECK_ONLY=0"
set "DEMO_PORT=8765"
set "DEMO_SKIP_PORT="
set "DEMO_UV="

:parse
if "%~1"=="" goto find_uv
if /i "%~1"=="--check" (
    set "DEMO_CHECK_ONLY=1"
    shift
    goto parse
)
if /i "%~1"=="--skip-port-check" (
    set "DEMO_SKIP_PORT=--skip-port-check"
    shift
    goto parse
)
if /i "%~1"=="--port" (
    if "%~2"=="" goto usage
    set "DEMO_PORT=%~2"
    shift
    shift
    goto parse
)
goto usage

:find_uv
for /f "delims=" %%U in ('where uv.exe 2^>nul') do if not defined DEMO_UV set "DEMO_UV=%%U"
if not defined DEMO_UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "DEMO_UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined DEMO_UV (
    echo [FAIL] uv was not found. Install uv using the official instructions linked in README.md.
    echo Then close and reopen this launcher. No administrator rights are required by this demo.
    goto failed
)
echo Preparing the locked Python environment. First use may require an internet connection.
"%DEMO_UV%" sync --locked
if errorlevel 1 (
    echo [FAIL] Python or dependency setup failed. Check the error above and README.md.
    goto failed
)
"%DEMO_UV%" run --locked --no-sync python src/demo/preflight.py --port "%DEMO_PORT%" %DEMO_SKIP_PORT%
if errorlevel 1 goto failed
if "%DEMO_CHECK_ONLY%"=="1" exit /b 0
echo Starting the local demo. Keep this window open; press Ctrl+C to stop.
"%DEMO_UV%" run --locked --no-sync python src/demo/server.py --port "%DEMO_PORT%" --open
if errorlevel 1 (
    echo [FAIL] The server stopped with an error. See the message above, README.md and DEMO_GUIDE.md.
    goto failed
)
exit /b 0

:usage
echo Usage: START_DEMO.cmd [--check] [--port 8765] [--skip-port-check]
echo CHECK_DEMO.cmd keeps results visible. Add --no-pause when running automated checks.
exit /b 2

:failed
if "%DEMO_CHECK_ONLY%"=="0" pause
exit /b 1
