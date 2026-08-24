@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"

rem Force the official PyPI index. This avoids incomplete/cached mirrors that may
rem report "from versions: none" for packages such as huggingface-hub.
set "PIP_CONFIG_FILE=NUL"
set "PIP_INDEX_URL=https://pypi.org/simple"
set "PIP_EXTRA_INDEX_URL="
set "PIP_NO_INDEX="
set "PIP_DEFAULT_TIMEOUT=180"
set "PIP_RETRIES=10"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"

 echo ===============================================
 echo BM Voice Studio v5.6.4 PERSONAL - Windows build FINAL FIX
 echo Soniox + ElevenLabs v3 + KZ/RU/EN OmniVoice clone
 echo ===============================================
 echo PyPI: %PIP_INDEX_URL%

set "PYEXE="
where py >nul 2>nul
if not errorlevel 1 (
  py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYEXE=py -3.12"
)
if not defined PYEXE (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Python табылмады. Python 3.12 x64 орнатыңыз.
    pause
    exit /b 1
  )
  for /f "delims=" %%V in ('python -c "import sys; print(sys.version_info.major,sys.version_info.minor,sep=chr(46))"') do set "PYVER=%%V"
  if not "!PYVER!"=="3.12" (
    echo Бұл build үшін Python 3.12 x64 керек. Табылған нұсқа: !PYVER!
    pause
    exit /b 1
  )
  set "PYEXE=python"
)

for /f "delims=" %%B in ('%PYEXE% -c "import struct; print(struct.calcsize(chr(80))*8)"') do set "PYBITS=%%B"
if not "!PYBITS!"=="64" (
  echo 64-bit Python керек. Табылғаны: !PYBITS!-bit
  pause
  exit /b 1
)

if exist .venv_windows\Scripts\python.exe (
  for /f "delims=" %%V in ('.venv_windows\Scripts\python.exe -c "import sys; print(sys.version_info.major,sys.version_info.minor,sep=chr(46))"') do set "VENVVER=%%V"
  if not "!VENVVER!"=="3.12" (
    echo Ескі virtual environment тазаланады: !VENVVER!
    rmdir /s /q .venv_windows
  )
)

if not exist .venv_windows (
  %PYEXE% -m venv .venv_windows
  if errorlevel 1 goto :fail
)

call .venv_windows\Scripts\activate.bat

 echo.
 echo [0/4] pip және build tools...
python -m pip install --index-url "%PIP_INDEX_URL%" --upgrade "pip<26" wheel setuptools
if errorlevel 1 goto :fail

 echo.
 echo [1/4] Hugging Face / OmniVoice үйлесімді нұсқалары және қалған тәуелділіктер...
python -m pip install --index-url "%PIP_INDEX_URL%" --retries 10 --timeout 180 -r requirements-desktop.txt
if errorlevel 1 goto :fail

 echo.
 echo [2/4] Tests...
python -m pip install --index-url "%PIP_INDEX_URL%" --retries 10 --timeout 180 "pytest>=8,<9"
if errorlevel 1 goto :fail
set "PYTHONPATH=%CD%"
python -m pytest -q
if errorlevel 1 goto :fail

 echo.
 echo [3/4] Import smoke test...
python -c "import huggingface_hub, transformers, torch, torchaudio, omnivoice; print('HF', huggingface_hub.__version__); print('Transformers', transformers.__version__); print('Torch', torch.__version__); print('TorchAudio', torchaudio.__version__); print('OmniVoice import OK')"
if errorlevel 1 goto :fail

 echo.
 echo [4/4] EXE build...
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_windows.ps1 -ProjectRoot "%CD%"
if errorlevel 1 goto :fail

 echo.
 echo ДАЙЫН. EXE Downloads\BM_Voice_Studio_Windows_v5.6.4_PERSONAL ішінде болады.
pause
exit /b 0

:fail
 echo.
 echo BUILD ҚАТЕСІ. Осы терезедегі ең соңғы 30-40 жолды ChatGPT-ке жіберіңіз.
pause
exit /b 1
