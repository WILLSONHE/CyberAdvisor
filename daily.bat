@echo off
REM UTF-8 first (before any non-ASCII echo); then launcher vs main body.
chcp 65001 >nul 2>nul
if /i "%~1"=="_run" goto :main
start "" /D "%~dp0" cmd /k "%~f0" _run %*
exit /b 0

:main
title CyberAdvisor Daily Pipeline
cd /d "%~dp0"

echo ============================================================
echo  CyberAdvisor Daily Pipeline
echo  Root: %CD%
echo  Start: %DATE% %TIME%
echo ============================================================
echo.

echo [1/12] mootdx_bestip.py (行情服务器测速) ...
python "%~dp0scripts\mootdx_bestip.py"
echo.

echo [2/12] feishu_download_portfolio.py ...
python "%~dp0scripts\feishu_download_portfolio.py"
if errorlevel 1 (
    echo [FAIL] Feishu portfolio download
    goto :end
)
echo.

echo [3/12] sync_portfolio_from_xlsx.py ...
python "%~dp0scripts\sync_portfolio_from_xlsx.py"
if errorlevel 1 (
    echo [FAIL] Portfolio sync
    goto :end
)
echo.

echo [4/12] coarse_screen.py ...
cd /d "%~dp0scripts"
python coarse_screen.py
if errorlevel 1 goto :fail

echo.
echo [5/12] fine_screen.py ...
python fine_screen.py
if errorlevel 1 goto :fail

echo.
echo [6/12] daily_report.py ...
python daily_report.py
if errorlevel 1 goto :fail

echo.
echo [6b/12] minute_data_audit.py ...
python minute_data_audit.py --write
echo.

echo [7/12] outlook_tracker.py batch --universe track ...
python outlook_tracker.py batch --universe track
if errorlevel 1 goto :fail

echo.
echo [8/12] bilibili_fetch.py ...
python bilibili_fetch.py
if errorlevel 1 goto :fail

echo.
echo [9/12] douyin_fetch.py (fetch tiktok / 钱加贝) ...
python douyin_fetch.py
if errorlevel 1 goto :fail

echo.
echo [10/12] rw_video.py --pending-only ...
python rw_video.py --pending-only
if errorlevel 1 goto :fail

echo.
echo [11/12] bilibili_fetch.py --dry-run ...
python bilibili_fetch.py --dry-run
if errorlevel 1 goto :fail

echo.
echo [12/12] douyin_fetch.py --dry-run ...
python douyin_fetch.py --dry-run
if errorlevel 1 goto :fail

cd /d "%~dp0"
echo.
echo [optional] sim_portfolio.py sync ...
python "%~dp0scripts\sim_portfolio.py" sync
echo.
echo [optional] feishu_notify.py --pipeline-done ...
python "%~dp0scripts\feishu_notify.py" --pipeline-done
echo.
echo [optional] feishu_auto_sug.py --after-daily ...
python "%~dp0scripts\feishu_auto_sug.py" --after-daily
echo.
echo ============================================================
echo  Done: %DATE% %TIME%
echo  Next: ~15:50 run vipdoc, then sug/agent sug all holders pm session
echo ============================================================
goto :end

:fail
cd /d "%~dp0"
echo.
echo [FAIL] Pipeline stopped. See errors above.

:end
if /i not "%~2"=="_nopause" (
    echo.
    pause
)
