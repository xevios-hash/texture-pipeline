@echo off
REM Windows launcher. OpenCode should call this, not invent steps.
REM
REM   set OPENROUTER_API_KEY=sk-or-v1-...
REM   set BLENDER_BIN=C:\Program Files\Blender Foundation\Blender 4.2\blender.exe
REM   run_pipeline.bat bush.glb "dense green bush, cutout foliage" --primitive plane
setlocal
cd /d "%~dp0"

if "%OPENROUTER_API_KEY%"=="" (
  echo OPENROUTER_API_KEY is not set
  exit /b 1
)

if "%BLENDER_BIN%"=="" set BLENDER_BIN=blender

set PY=python
if not "%PYTHON_BIN%"=="" set PY=%PYTHON_BIN%
%PY% ai_texture_agent.py %*
exit /b %ERRORLEVEL%
