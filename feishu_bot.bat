@echo off
setlocal
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
REM CyberAdvisor Feishu Bot + ngrok tunnel on port 8765
set "ROOT=%~dp0"
set "SCRIPTS=%ROOT%scripts"
set "NGROK=%SCRIPTS%\feishu_ngrok.ps1"

where wt >nul 2>&1
if errorlevel 1 goto no_wt

if defined WT_SESSION (
  wt -w 0 nt --title "ngrok 8765" -- powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%NGROK%"
  title CyberAdvisor Feishu Bot
  cd /d "%SCRIPTS%"
  python feishu_bot.py
  pause
  exit /b 0
)

REM Explorer double-click: one WT window (Bot tab + ngrok tab), exit this cmd immediately
start "" wt nt --title "Feishu Bot" -d "%SCRIPTS%" -- cmd /k feishu_bot_tab.cmd ; nt --title "ngrok 8765" -- powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%NGROK%"
exit /b 0

:no_wt
echo [INFO] Windows Terminal not found; starting ngrok in a separate PowerShell window.
start "ngrok 8765" powershell -NoProfile -ExecutionPolicy Bypass -NoExit -File "%NGROK%"
title CyberAdvisor Feishu Bot
cd /d "%SCRIPTS%"
python feishu_bot.py
pause
