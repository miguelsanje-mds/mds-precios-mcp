@echo off
chcp 65001 >nul
cd /d "%~dp0"
set LOG=%~dp0push_log.txt

echo ============================================================ > "%LOG%"
echo   PUSH A GITHUB - mds-precios-mcp (FORCE) >> "%LOG%"
echo   Fecha: %DATE% %TIME% >> "%LOG%"
echo ============================================================ >> "%LOG%"
echo. >> "%LOG%"

echo --- Archivos en la carpeta --- >> "%LOG%"
dir /b >> "%LOG%"
echo. >> "%LOG%"

echo --- git config --- >> "%LOG%"
git config user.email "miguelsanje@gmail.com" >> "%LOG%" 2>&1
git config user.name "Miguel Sanjenis" >> "%LOG%" 2>&1

echo --- borrar log del indice si estuviera --- >> "%LOG%"
git rm --cached push_log.txt >> "%LOG%" 2>&1

echo --- anadir TODOS los archivos except log --- >> "%LOG%"
git add server.py requirements.txt Procfile runtime.txt .gitignore README.md PUSH_TO_GITHUB.bat >> "%LOG%" 2>&1

echo --- git status --- >> "%LOG%"
git status >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git commit --- >> "%LOG%"
git commit -m "Deploy MCP precios - todos los archivos" >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git log --oneline -5 --- >> "%LOG%"
git log --oneline -5 >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo --- git push --force-with-lease (sobrescribe remoto) --- >> "%LOG%"
git push -u origin main --force >> "%LOG%" 2>&1
echo. >> "%LOG%"

echo ============================================================ >> "%LOG%"
echo   FIN >> "%LOG%"
echo ============================================================ >> "%LOG%"

type "%LOG%"
echo.
echo ============================================================
echo   Listo. Revisa el log y el repo en GitHub.
echo ============================================================
pause
