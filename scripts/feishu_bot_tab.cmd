@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
title CyberAdvisor Feishu Bot
python feishu_bot.py
echo.
pause
