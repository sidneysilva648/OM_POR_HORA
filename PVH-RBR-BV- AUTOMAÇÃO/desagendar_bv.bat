@echo off
title BV - Remover Tarefas

echo ============================================================
echo  BV (Centro 0077) - Removendo as 8 tarefas do Agendador
echo ============================================================
echo.

set /p CONFIRMA="Tem certeza que quer REMOVER todas as 8 tarefas BV? (S/N): "
if /I not "%CONFIRMA%"=="S" (
    echo Operacao cancelada.
    pause
    exit /b 0
)

echo.
for %%N in (1 2 3 4 5 6 7 8) do (
    schtasks /Delete /F /TN "BV_Parcial_%%N" >nul 2>&1
    if errorlevel 1 (
        echo   [--] BV_Parcial_%%N nao existia
    ) else (
        echo   [OK] BV_Parcial_%%N removida
    )
)

echo.
echo ============================================================
echo  Pronto. Execute agendar_bv.bat para reagendar.
echo ============================================================
echo.
pause
