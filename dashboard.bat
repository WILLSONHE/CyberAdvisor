@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

python -c "import streamlit" 2>nul || (
  echo Installing dashboard deps...
  pip install -r requirements-dashboard.txt
)

python -m streamlit run scripts\dashboard\app.py --server.headless true --browser.gatherUsageStats false
