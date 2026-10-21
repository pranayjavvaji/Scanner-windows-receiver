@echo off
REM Builds a single-file BarScanReceiver.exe you can hand to other people.
pip install -r requirements.txt pyinstaller
pyinstaller --onefile --name BarScanReceiver receiver.py
echo.
echo Done: dist\BarScanReceiver.exe
pause
