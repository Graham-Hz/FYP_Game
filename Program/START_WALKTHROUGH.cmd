@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>nul
if errorlevel 1 (
  echo uv was not found. Ask for help setting up the existing FYP Python environment.
  pause
  exit /b 1
)
echo Opening the FYP learning notebook. Keep this window open while using Jupyter.
echo First launch may download the isolated notebook dependencies.
uv run --project experiments/walkthrough_v1 --locked jupyter lab notebooks/01_understand_your_fyp.ipynb --ServerApp.root_dir="%CD%"
if errorlevel 1 pause
endlocal
