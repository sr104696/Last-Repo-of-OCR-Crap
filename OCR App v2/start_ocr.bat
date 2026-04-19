@echo off
echo Checking and installing requirements...
cd /d "%~dp0"
pip install -r requirements.txt -q
echo Starting OCR Application...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo The application encountered an error. 
    echo.
    pause
)
