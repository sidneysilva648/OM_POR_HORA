@echo off
title OM_por_HORA - Remover Tarefas

echo ============================================================
echo  OM_por_HORA - Removendo as 8 tarefas do Agendador
echo ============================================================
echo.

set /p CONFIRMA="Tem certeza que quer REMOVER todas as 8 tarefas? (S/N): "
if /I not "%CONFIRMA%"=="S" (
    echo Operacao cancelada.
    pause
    exit /b 0
)

echo.
for %%N in (1 2 3 4 5 6 7 8) do (
    schtasks /Delete /F /TN "OM_por_HORA_Parcial_%%N" >nul 2>&1
    if errorlevel 1 (
        echo   [--] OM_por_HORA_Parcial_%%N nao existia
    ) else (
        echo   [OK] OM_por_HORA_Parcial_%%N removida
    )
)

echo.
echo ============================================================
echo  Pronto. Execute agendar_tarefas.bat para reagendar.
echo ============================================================
echo.
pause
