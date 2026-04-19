@echo off
cd /d "%~dp0"
:: Ensure pip requirements are met without excessive wait time
python -c "import fitz, PIL, pytesseract" >nul 2>&1
if errorlevel 1 (
    echo Installing minimal dependencies...
    pip install -r requirements.txt -q
)
:: Run the app without a persistent console window
start pythonw app.py
