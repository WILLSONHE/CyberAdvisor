@echo off
chcp 65001 >nul
REM CyberAdvisor Feishu Bot - keep window open; requires ngrok on port 8765
title CyberAdvisor Feishu Bot
cd /d "%~dp0scripts"
python feishu_bot.py
pause
