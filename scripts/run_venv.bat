@echo off

set "REPOSITORY_ROOT=%~dp0.."

REM Activate the virtual environment
call "%REPOSITORY_ROOT%\venv\Scripts\activate.bat"

REM Run the Python script
python "%REPOSITORY_ROOT%\src\main.py"
