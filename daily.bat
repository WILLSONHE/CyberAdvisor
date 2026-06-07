@echo off
REM Double-click: open a new terminal and keep it open (cmd /k)
if /i not "%~1"=="_run" (
  start "CyberAdvisor Daily" cmd /k call "%~f0" _run
  exit /b 0
)

chcp 65001 >nul
title CyberAdvisor Daily Pipeline
cd /d "%~dp0"

echo ============================================================
echo  CyberAdvisor Daily Pipeline
echo  Root: %CD%
echo  Start: %DATE% %TIME%
echo ============================================================
echo.

echo [1/7] feishu_download_portfolio.py ...
python "%~dp0scripts\feishu_download_portfolio.py"
if errorlevel 1 (
    echo [FAIL] Feishu portfolio download
    goto :end
)
echo.

echo [2/7] sync_portfolio_from_xlsx.py ...
python "%~dp0scripts\sync_portfolio_from_xlsx.py"
if errorlevel 1 (
    echo [FAIL] Portfolio sync
    goto :end
)
echo.

echo [3/7] coarse_screen.py ...
cd /d "%~dp0scripts"
python coarse_screen.py
if errorlevel 1 goto :fail

echo.
echo [4/7] fine_screen.py ...
python fine_screen.py
if errorlevel 1 goto :fail

echo.
echo [5/7] daily_report.py ...
python daily_report.py
if errorlevel 1 goto :fail

echo.
echo [6/8] bilibili_fetch.py ...
python bilibili_fetch.py
if errorlevel 1 goto :fail

echo.
echo [7/8] rw_video.py --pending-only ...
python rw_video.py --pending-only
if errorlevel 1 goto :fail

echo.
echo [8/8] bilibili_fetch.py --dry-run ...
python bilibili_fetch.py --dry-run
if errorlevel 1 goto :fail

cd /d "%~dp0"
echo.
echo [optional] feishu_notify.py --pipeline-done ...
python "%~dp0scripts\feishu_notify.py" --pipeline-done
echo.
echo ============================================================
echo  Done: %DATE% %TIME%
echo  Next: say "sug Wilson" in Cursor - report in SugVault\
echo ============================================================
goto :end

:fail
cd /d "%~dp0"
echo.
echo [FAIL] Pipeline stopped. See errors above.

:end
echo.
pause
