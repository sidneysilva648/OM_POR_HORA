@echo off
chcp 65001 >nul
title OM_por_HORA - Instalador de dependencias

echo ============================================================
echo OM_por_HORA - Instalando bibliotecas Python necessarias
echo ============================================================
echo.

REM Usa o Python que vimos no terminal (Python 3.12)
set PYTHON_EXE="C:\Program Files\Python312\python.exe"

if not exist %PYTHON_EXE% (
    echo [AVISO] Nao encontrei Python em %PYTHON_EXE%.
    echo Usando o "python" do PATH do sistema...
    set PYTHON_EXE=python
)

echo [INFO] Atualizando pip...
%PYTHON_EXE% -m pip install --upgrade pip
echo.

echo [INFO] Instalando pacotes...
%PYTHON_EXE% -m pip install pywin32 psutil openpyxl Pillow selenium webdriver-manager

echo.
echo ============================================================
echo Verificando instalacao...
echo ============================================================
%PYTHON_EXE% -c "import win32com.client; print('  [OK] pywin32         (SAP GUI Scripting)')"
%PYTHON_EXE% -c "import psutil;            print('  [OK] psutil          (verifica processos)')"
%PYTHON_EXE% -c "import openpyxl;          print('  [OK] openpyxl        (grava planilha Excel)')"
%PYTHON_EXE% -c "from PIL import Image;    print('  [OK] Pillow          (gera card visual)')"
%PYTHON_EXE% -c "import selenium;          print('  [OK] selenium        (WhatsApp Web)')"
%PYTHON_EXE% -c "import webdriver_manager; print('  [OK] webdriver-manager (ChromeDriver auto)')"

echo.
echo ============================================================
echo Instalacao concluida! Pode fechar esta janela.
echo ============================================================
echo.
pause
