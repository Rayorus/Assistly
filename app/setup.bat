@echo off
echo ============================================
echo   OverlayOS — Desktop AI Assistant Setup
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

echo [1/3] Creating virtual environment...
python -m venv venv
call venv\Scripts\activate.bat

echo [2/3] Installing dependencies...
pip install -r requirements.txt

echo [3/3] Setup complete!
echo.
echo ============================================
echo   IMPORTANT: Edit .env and add your OpenAI API key
echo   Then run:  python main.py
echo   Hotkey:    Ctrl+Space to toggle overlay
echo ============================================
pause
