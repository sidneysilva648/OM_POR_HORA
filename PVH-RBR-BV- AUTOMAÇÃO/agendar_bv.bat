@echo off
title BV (Centro 0077) - Agendador de Tarefas

echo ============================================================
echo  PVH-RBR-BV (Centro 0077) - Configurando 8 tarefas
echo  Roda 5 minutos antes de cada parcial (Seg-Sex)
echo ============================================================
echo.

set "PY=C:\Program Files\Python312\python.exe"

REM %~dp0 = pasta onde este .bat esta. Funciona mesmo com cedilha
REM no nome da pasta porque o Windows resolve isso automaticamente.
set "SCRIPT=%~dp0BV.PY"

if not exist "%PY%" (
    echo [ERRO] Python nao encontrado em:
    echo        %PY%
    echo.
    pause
    exit /b 1
)

if not exist "%SCRIPT%" (
    echo [ERRO] BV.PY nao encontrado em:
    echo        %SCRIPT%
    echo.
    pause
    exit /b 1
)

echo [INFO] Python: %PY%
echo [INFO] Script: %SCRIPT%
echo.
echo Criando tarefas (Seg-Sex, 5min antes de cada parcial)...
echo.

REM Horario REAL da parcial -> hora de execucao no agendador (5 min antes)
REM Parcial 1 (09:30) -> roda 09:25
REM Parcial 2 (10:30) -> roda 10:25
REM Parcial 3 (11:30) -> roda 11:25
REM Parcial 4 (13:30) -> roda 13:25
REM Parcial 5 (14:30) -> roda 14:25
REM Parcial 6 (15:30) -> roda 15:25
REM Parcial 7 (16:30) -> roda 16:25
REM Parcial 8 (17:30) -> roda 17:25

call :criar 1 09:25
call :criar 2 10:25
call :criar 3 11:25
call :criar 4 13:25
call :criar 5 14:25
call :criar 6 15:25
call :criar 7 16:25
call :criar 8 17:25

echo.
echo ============================================================
echo  Conferindo tarefas criadas...
echo ============================================================
echo.

schtasks /Query /TN "BV_Parcial_1" 2>nul
schtasks /Query /TN "BV_Parcial_2" 2>nul
schtasks /Query /TN "BV_Parcial_3" 2>nul
schtasks /Query /TN "BV_Parcial_4" 2>nul
schtasks /Query /TN "BV_Parcial_5" 2>nul
schtasks /Query /TN "BV_Parcial_6" 2>nul
schtasks /Query /TN "BV_Parcial_7" 2>nul
schtasks /Query /TN "BV_Parcial_8" 2>nul

echo.
echo ============================================================
echo  PRONTO. Para conferir visual, abra: taskschd.msc
echo  Procure tarefas com nome "BV_Parcial_X" (1 a 8)
echo ============================================================
echo.
pause
exit /b 0


:criar
set "NUM=%~1"
set "HORA=%~2"
set "TASK_NAME=BV_Parcial_%NUM%"
set "CMD=\"%PY%\" \"%SCRIPT%\" --parcial %NUM%"

echo --- Tarefa BV %NUM% (%HORA%) ---
schtasks /Create /F /SC WEEKLY /D MON,TUE,WED,THU,FRI,SAT /TN "%TASK_NAME%" /TR "%CMD%" /ST %HORA% /RL LIMITED
echo.
goto :eof
