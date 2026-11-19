@echo off
setlocal DisableDelayedExpansion
set "CHECK_PAUSE=1"
set "CHECK_PORT=8765"
set "CHECK_SKIP_PORT="

:parse
if "%~1"=="" goto check
if /i "%~1"=="--no-pause" (
    set "CHECK_PAUSE=0"
    shift
    goto parse
)
if /i "%~1"=="--skip-port-check" (
    set "CHECK_SKIP_PORT=--skip-port-check"
    shift
    goto parse
)
if /i "%~1"=="--port" (
    if "%~2"=="" goto usage
    set "CHECK_PORT=%~2"
    shift
    shift
    goto parse
)
goto usage

:check
call "%~dp0START_DEMO.cmd" --check --port "%CHECK_PORT%" %CHECK_SKIP_PORT%
set "CHECK_RESULT=%errorlevel%"
if "%CHECK_PAUSE%"=="1" pause
exit /b %CHECK_RESULT%

:usage
echo Usage: CHECK_DEMO.cmd [--no-pause] [--port 8765] [--skip-port-check]
exit /b 2
