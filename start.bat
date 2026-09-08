@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ==================================================
echo  PDF Chatbot - Local PDF Folder + Ollama + Llama 3.2
echo ==================================================

echo.
echo -^> Checking Python 3.11...
py -3.11 --version >nul 2>&1
if errorlevel 1 goto :python_missing

echo -^> Checking Node.js...
where node >nul 2>&1
if errorlevel 1 goto :node_missing

echo -^> Checking npm...
where npm >nul 2>&1
if errorlevel 1 goto :npm_missing

echo -^> Checking Ollama...
where ollama >nul 2>&1
if errorlevel 1 goto :ollama_missing

if not exist "backend\.venv\Scripts\python.exe" goto :create_venv
backend\.venv\Scripts\python.exe -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,11) else 1)" >nul 2>&1
if errorlevel 1 goto :recreate_venv
goto :install_backend

:recreate_venv
if exist "backend\.venv" rmdir /s /q "backend\.venv"
:create_venv
echo -^> Creating Python 3.11 virtual environment...
py -3.11 -m venv backend\.venv
if errorlevel 1 goto :venv_failed

goto :install_backend

:install_backend
echo -^> Checking Python pip...
backend\.venv\Scripts\python.exe -m pip --version >nul 2>&1
if errorlevel 1 goto :repair_pip

echo -^> Installing backend dependencies...
backend\.venv\Scripts\python.exe -m pip install --quiet -r backend\requirements.txt
if errorlevel 1 goto :backend_failed

goto :env_setup

:repair_pip
echo -^> pip is missing; repairing it with ensurepip...
backend\.venv\Scripts\python.exe -m ensurepip --upgrade
if errorlevel 1 goto :pip_failed
backend\.venv\Scripts\python.exe -m pip install --quiet -r backend\requirements.txt
if errorlevel 1 goto :backend_failed

goto :env_setup

:env_setup
if not exist "backend\.env" (
  copy /Y backend\.env.example backend\.env >nul
  echo.
  echo !! Created backend\.env with local Ollama defaults.
  echo !! No cloud API key is required.
  echo.
)

if not exist "pdf" mkdir "pdf"

echo -^> Checking Ollama service...
ollama list >nul 2>&1
if errorlevel 1 goto :start_ollama
goto :check_model

:start_ollama
echo -^> Ollama is not responding. Starting Ollama service...
start "Ollama" /b ollama serve >nul 2>&1
timeout /t 3 /nobreak >nul
ollama list >nul 2>&1
if errorlevel 1 goto :ollama_not_running
goto :check_model

:check_model
echo -^> Checking for Llama 3.2...
ollama list | findstr /i /b "llama3.2" >nul 2>&1
if not errorlevel 1 goto :frontend

echo -^> Llama 3.2 is not downloaded. Pulling llama3.2...
ollama pull llama3.2
if errorlevel 1 goto :model_failed

goto :frontend

:frontend
if not exist "frontend\node_modules" goto :install_frontend
goto :build_frontend

:install_frontend
echo -^> Installing frontend dependencies...
pushd frontend
call npm.cmd install --silent
if errorlevel 1 (
  popd
  goto :frontend_failed
)
popd

goto :build_frontend

:build_frontend
echo -^> Building frontend...
pushd frontend
call npm.cmd run build --silent
if errorlevel 1 (
  popd
  goto :frontend_failed
)
popd

echo.
echo ==================================================
echo  Ready! Opening http://localhost:8000
echo  PDFs: project\pdf\ folder
echo  LLM: Ollama / llama3.2
echo ==================================================
echo.
cd backend
call .venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000
exit /b %errorlevel%

:python_missing
echo ERROR: Python 3.11 was not found through the Python launcher.
echo Install Python 3.11 and make sure "py -3.11 --version" works.
exit /b 1

:node_missing
echo ERROR: Node.js not found. Install Node.js 18+ first.
exit /b 1

:npm_missing
echo ERROR: npm not found. Reinstall Node.js 18+ with npm enabled.
exit /b 1

:ollama_missing
echo ERROR: Ollama not found. Install Ollama and make sure the ollama command is on PATH.
exit /b 1

:venv_failed
echo ERROR: Could not create the Python 3.11 virtual environment.
exit /b 1

:pip_failed
echo ERROR: Could not repair pip inside backend\.venv.
exit /b 1

:backend_failed
echo ERROR: Backend dependency installation failed.
exit /b 1

:ollama_not_running
echo ERROR: Ollama is installed but is not responding.
echo Start Ollama manually, then run start.bat again.
exit /b 1

:model_failed
echo ERROR: Could not download llama3.2.
echo Check your internet connection and run: ollama pull llama3.2
exit /b 1

:frontend_failed
echo ERROR: Frontend dependency installation or build failed.
exit /b 1
