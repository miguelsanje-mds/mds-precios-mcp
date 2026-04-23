@echo off
chcp 65001 >nul
cd /d "%~dp0"
set LOG=%~dp0push_log.txt

echo ============================================================ > "%LOG%"
echo   PUSH A GITHUB - mds-precios-mcp >> "%LOG%"
echo   Fecha: %DATE% %TIME% >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo. >> "%LOG%"

echo Carpeta: %CD% >> "%LOG%"
echo. >> "%LOG%"

echo --- git --version --- >> "%LOG%"
git --version >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- Archivos en la carpeta --- >> "%LOG%"
dir /b >> "%LOG%"
echo. >> "%LOG%"

echo --- git init --- >> "%LOG%"
git init >> "%LOG%" 2>&1
git branch -M main >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git remote --- >> "%LOG%"
git remote remove origin >> "%LOG%" 2>&1
git remote add origin https://github.com/miguelsanje-mds/mds-precios-mcp.git >> "%LOG%" 2>&1
git remote -v >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git config --- >> "%LOG%"
git config user.email "miguelsanje@gmail.com" >> "%LOG%" 2>&1
git config user.name "Miguel Sanjenis" >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git add --- >> "%LOG%"
git add -A >> "%LOG%" 2>&1
git status >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git commit --- >> "%LOG%"
git commit -m "Initial deploy: MCP precios construccion" >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git pull rebase (por si el remoto ya tiene README) --- >> "%LOG%"
git pull --rebase origin main >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git push --- >> "%LOG%"
git push -u origin main >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo ============================================================ >> "%LOG%"
echo   FIN - consulta este archivo para ver todo lo que paso >> "%LOG%"
echo ============================================================ >> "%LOG%"

REM Mostrar el log en pantalla AL FINAL
type "%LOG%"
echo.
echo.
echo ============================================================
echo   Si ves "git: no se reconoce" instalar Git primero.
echo   Si pide login, abre el navegador y autoriza.
echo   Log guardado en: push_log.txt
echo ============================================================
echo.
pause
