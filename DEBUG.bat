@echo off
cd /d "%~dp0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":5000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)
timeout /t 1 /nobreak >nul
echo Servidor iniciando em http://localhost:5000
echo Deixe essa janela aberta para ver os erros.
echo.
python app.py
pause
