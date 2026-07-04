@echo off
title OM_por_HORA - Agendador

echo ============================================================
echo  OM_por_HORA - Configurando 8 tarefas no Agendador
echo ============================================================
echo.

set "PY=C:\Program Files\Python312\python.exe"
set "SCRIPT=C:\Users\21039\OneDrive - BEMOL S A\automacao\OM POR HORA\main.py"

if not exist "%PY%" (
    echo [ERRO] Python nao encontrado em:
    echo        %PY%
    echo.
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo [ERRO] main.py nao encontrado em:
    echo        %SCRIPT%
    pause
    exit /b 1
)

echo [INFO] Python: %PY%
echo [INFO] Script: %SCRIPT%
echo.
echo Criando tarefas (Seg-Sex)...
echo.

call :criar 1 09:30
call :criar 2 10:30
call :criar 3 11:30
call :criar 4 13:30
call :criar 5 14:30
call :criar 6 15:30
call :criar 7 16:30
call :criar 8 17:30

echo.
echo ============================================================
echo  Conferindo tarefas criadas...
echo ============================================================
echo.

schtasks /Query /TN "OM_por_HORA_Parcial_1" 2>nul
schtasks /Query /TN "OM_por_HORA_Parcial_2" 2>nul
schtasks /Query /TN "OM_por_HORA_Parcial_3" 2>nul
schtasks /Query /TN "OM_por_HORA_Parcial_4" 2>nul
schtasks /Query /TN "OM_por_HORA_Parcial_5" 2>nul
schtasks /Query /TN "OM_por_HORA_Parcial_6" 2>nul
schtasks /Query /TN "OM_por_HORA_Parcial_7" 2>nul
schtasks /Query /TN "OM_por_HORA_Parcial_8" 2>nul

echo.
echo ============================================================
echo  PRONTO. Para conferir visual, abra: taskschd.msc
echo ============================================================
echo.
pause
exit /b 0


:criar
set "NUM=%~1"
set "HORA=%~2"
set "TASK_NAME=OM_por_HORA_Parcial_%NUM%"
set "CMD=\"%PY%\" \"%SCRIPT%\" --parcial %NUM%"

echo --- Tarefa %NUM% (%HORA%) ---
schtasks /Create /F /SC WEEKLY /D MON,TUE,WED,THU,FRI,SAT /TN "%TASK_NAME%" /TR "%CMD%" /ST %HORA% /RL LIMITED
echo.
goto :eof
