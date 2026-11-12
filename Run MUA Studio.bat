@echo off
rem Abre o MUA Studio. Precisa de Python 3.10+ com tkinter (veja "Install dependencies.bat").
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw app.py & exit /b)
where pyw >nul 2>nul && (start "" pyw app.py & exit /b)
python app.py
if errorlevel 1 pause
