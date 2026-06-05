@echo off
REM 双击：在新终端窗口运行每日流水线（窗口保持打开）
if /i not "%~1"=="_run" (
  start "CyberAdvisor Daily" cmd /k "%~f0" _run
  exit /b 0
)

chcp 65001 >nul
title CyberAdvisor Daily Pipeline
cd /d "%~dp0"

echo ============================================================
echo  CyberAdvisor 每日流水线
echo  根目录: %CD%
echo  开始: %DATE% %TIME%
echo ============================================================
echo.

echo [1/7] 从飞书云文档下载 持仓.xlsx ...
python "%~dp0scripts\feishu_download_portfolio.py"
if errorlevel 1 (
    echo [失败] 飞书持仓下载出错
    goto :end
)
echo.

echo [2/7] 从 持仓.xlsx 同步持仓...
python "%~dp0scripts\sync_portfolio_from_xlsx.py"
if errorlevel 1 (
    echo [失败] 持仓同步出错
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
echo [6/7] bilibili_fetch.py （视频字幕）...
python bilibili_fetch.py
if errorlevel 1 goto :fail

echo.
echo [7/7] bilibili_fetch.py --dry-run （预览）...
python bilibili_fetch.py --dry-run
if errorlevel 1 goto :fail

cd /d "%~dp0"
echo.
echo [可选] 推送到飞书...
python "%~dp0scripts\feishu_notify.py" --pipeline-done
echo.
echo ============================================================
echo  全部完成: %DATE% %TIME%
echo  下一步: 对 AI 说 sug {持有人} （如 sug Wilson，报告写入 SugVault\）
echo ============================================================
goto :end

:fail
cd /d "%~dp0"
echo.
echo [失败] 流水线中断，请查看上方报错。
goto :end

:end
echo.
