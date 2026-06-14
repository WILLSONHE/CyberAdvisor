@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

if "%~1"=="" goto usage

python scripts\graph\runner.py %*
exit /b %ERRORLEVEL%

:usage
echo CyberAdvisor Graph CLI (orchestrator, not LangGraph; default dry-run)
echo.
echo   graph.bat status
echo   graph.bat sug HOLDER
echo   graph.bat sug HOLDER SESSION
echo   graph.bat sug HOLDER --dry-run
echo   graph.bat sug HOLDER SESSION --live
echo   graph.bat qry "your question"
echo.
echo Live: GRAPH_PIPELINE_ENABLED=1 and CURSOR_API_KEY in .env
echo UI: dashboard.bat then open Graph progress page
echo.
python scripts\graph\runner.py status
exit /b 0
