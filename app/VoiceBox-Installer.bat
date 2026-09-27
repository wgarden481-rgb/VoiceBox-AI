@echo off
title VoiceBox AI Installer
color 0B
echo ===========================================
echo  VoiceBox AI - Installer
echo  Claude Sonnet 4.6 + GPT-5.2 High Build
echo ===========================================
echo.
echo This installer will:
echo  1. Check Python is installed
echo  2. Install required libraries
echo  3. Register background startup
echo  4. Launch Intro wizard
echo.
echo Requesting Administrator permission to:
echo  - Register global hotkey (Left CTRL + Left ALT)
echo  - Add to startup (run in background)
echo.
pause

:: Check admin
net session >nul 2>&1
if %errorLevel% NEQ 0 (
    echo Requesting Administrator...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo [OK] Running as Administrator
echo.

:: Check python
python --version >nul 2>&1
if %errorLevel% NEQ 0 (
    echo [ERROR] Python not found! Please install Python 3.10+ from python.org
    echo Make sure to check "Add python to PATH" during install.
    pause
    exit /b
)

echo [1/4] Installing dependencies...
pip install -r requirements.txt
if %errorLevel% NEQ 0 (
    echo [WARN] pip install had issues, trying again...
    pip install --user -r requirements.txt
)

echo.
echo [2/4] Setting up config...
if not exist config.json (
    echo Creating config...
    copy config.json config.json >nul 2>&1
)

echo.
echo [3/4] Creating Start Menu shortcut...
set SCRIPT="%TEMP%\create_shortcut.ps1"
echo $WshShell = New-Object -comObject WScript.Shell > %SCRIPT%
echo $Shortcut = $WshShell.CreateShortcut("$env:APPDATA%\Microsoft\Windows\Start Menu\Programs\VoiceBox AI.lnk") >> %SCRIPT%
echo $Shortcut.TargetPath = "pythonw.exe" >> %SCRIPT%
echo $Shortcut.Arguments = """%CD%\main.py""" >> %SCRIPT%
echo $Shortcut.WorkingDirectory = "%CD%" >> %SCRIPT%
echo $Shortcut.IconLocation = "shell32.dll,14" >> %SCRIPT%
echo $Shortcut.Save() >> %SCRIPT%
powershell -ExecutionPolicy Bypass -File %SCRIPT% 2>nul
del %SCRIPT% 2>nul

:: Auto-start registry (optional)
echo.
echo [4/4] Add to startup? (runs in background on boot) (Y/N)
set /p choice="Choice [Y]: "
if /I "%choice%"=="N" goto skipstartup
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v VoiceBoxAI /t REG_SZ /d "pythonw.exe ""%CD%\main.py""" /f >nul
echo Added to startup.
:skipstartup

echo.
echo ===========================================
echo  Installation Complete!
echo ===========================================
echo Launching VoiceBox...
start "" pythonw.exe "%CD%\main.py"
echo.
echo VoiceBox is now running in background!
echo Look for the purple icon in system tray (bottom right).
echo Press LEFT CTRL + LEFT ALT to test it!
echo.
pause
