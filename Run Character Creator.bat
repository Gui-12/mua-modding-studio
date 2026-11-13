@echo off
rem Abre só o Criador de Personagem (módulo creator\), sem o MUA Studio.
cd /d "%~dp0"
where pythonw >nul 2>nul && (start "" pythonw -m creator & exit /b)
where pyw >nul 2>nul && (start "" pyw -m creator & exit /b)
python -m creator
if errorlevel 1 pause
