@echo off
setlocal
cd /d "%~dp0.."
where python >nul 2>nul || (echo Python 3 is required.& pause & exit /b 1)
python -c "import sys; assert sys.version_info >= (3, 10)" || (echo Python 3.10 or newer is required.& pause & exit /b 1)
python -m admin.server
if errorlevel 1 pause
