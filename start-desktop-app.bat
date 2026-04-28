@echo off
setlocal
cd /d "%~dp0"
py -3 webview_app.py
if errorlevel 1 python webview_app.py
