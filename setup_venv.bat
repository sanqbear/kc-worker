@echo off
REM Setup script for Windows
REM Creates a Python virtual environment and installs dependencies

echo Creating Python virtual environment...
python -m venv venv

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo Setup complete! To activate the virtual environment, run:
echo   venv\Scripts\activate.bat
echo.
echo To start the Celery worker, run:
echo   celery -A celery_app.celery worker --loglevel=info
echo.
pause
