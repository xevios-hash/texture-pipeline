@echo off
setlocal
cd /d "%~dp0"
if "%BLENDER_BIN%"=="" set BLENDER_BIN=blender
python oneshot.py %*
exit /b %ERRORLEVEL%
