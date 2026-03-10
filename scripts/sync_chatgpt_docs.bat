@echo off
powershell -ExecutionPolicy Bypass -File scripts\sync_chatgpt_docs.ps1
exit /b %ERRORLEVEL%
