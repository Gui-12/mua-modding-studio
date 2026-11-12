@echo off
rem Verifica (e se precisar instala) o que o MUA Studio exige: Python 3.10+ com tkinter.
rem O app nao usa nenhum pacote pip; so a biblioteca padrao do Python.
setlocal
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY where py >nul 2>nul && set "PY=py"

if not defined PY goto :install

%PY% -c "import sys,tkinter; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>nul
if errorlevel 1 goto :install

for /f "delims=" %%v in ('%PY% --version') do echo OK: %%v com tkinter encontrado.
echo Nada para instalar. Abra o MUA Studio com "Run MUA Studio.bat".
pause
exit /b 0

:install
echo Python 3.10+ com tkinter nao encontrado.
where winget >nul 2>nul
if errorlevel 1 (
  echo.
  echo Instale manualmente: https://www.python.org/downloads/
  echo Na instalacao deixe marcado "tcl/tk and IDLE" e "Add python.exe to PATH".
  pause
  exit /b 1
)
echo Instalando Python 3.13 pelo winget (inclui tkinter)...
winget install --id Python.Python.3.13 -e --source winget
echo.
echo Terminou. Feche esta janela e abra uma NOVA antes de rodar o MUA Studio (para o PATH atualizar).
pause
