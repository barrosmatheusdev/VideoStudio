@echo off
chcp 65001 >nul
title VideoStudio Local v2
echo.
echo ==========================================
echo     VideoStudio Local v2 - Setup
echo ==========================================
echo.

echo [1/5] Verificando FFmpeg...
where ffmpeg >nul 2>&1
if %errorlevel% neq 0 (
    echo   ERRO: FFmpeg nao encontrado!
    echo   Instale em: https://www.gyan.dev/ffmpeg/builds/
    echo   Adicione a pasta bin ao PATH do Windows.
    pause
    exit /b 1
)
echo   FFmpeg OK
echo.

echo [2/5] Configurando ambiente virtual...
if not exist "venv" (
    echo   Criando venv...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo   ERRO: Falha ao criar venv. Python instalado?
        pause
        exit /b 1
    )
)
call venv\Scripts\activate.bat
echo   Venv OK
echo.

echo [3/5] Atualizando pip...
python -m pip install --upgrade pip --quiet
echo   Pip OK
echo.

echo [4/5] Instalando dependencias...
echo   Instalando Flask...
python -m pip install flask werkzeug --quiet

echo   Instalando PyTorch (CPU)...
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu --quiet

echo   Instalando Whisper...
python -m pip install openai-whisper --quiet

echo   Instalando numpy (compativel)...
python -m pip install numpy==1.26.4 


echo   Dependencias OK
echo.

echo [5/5] Verificando instalacao...
python -c "import whisper; print('  Whisper OK')"
if %errorlevel% neq 0 (
    echo   ERRO: Whisper nao carregou corretamente.
    echo   Tente rodar manualmente: pip install openai-whisper torch
    pause
    exit /b 1
)
python -c "import flask; print('  Flask OK')"
echo   Tudo pronto!
echo.

echo ==========================================
echo   Abrindo Programa...
echo   Para parar: Ctrl + C
echo ==========================================
echo.
python app.py

echo.
echo Servidor encerrado.
pause
