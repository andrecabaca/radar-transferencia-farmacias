@echo off
cd /d "%~dp0"
echo.
echo   Radar de Transferencia de Farmacias
echo   ----------------------------------
echo   A abrir no navegador: http://localhost:8777
echo   Feche esta janela quando terminar.
echo.
start "" http://localhost:8777
python -m http.server 8777 --bind 127.0.0.1
