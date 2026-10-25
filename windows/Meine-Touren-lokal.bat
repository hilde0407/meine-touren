@echo off
rem Meine Touren lokal auf Windows starten (Doppelklick). Beim ersten Start wird alles eingerichtet.
rem Daten:  %USERPROFILE%\Meine-Touren-Daten   (Touren, Fotos-Index, Einstellungen)
rem Aufruf: Meine-Touren-lokal.bat [Port]      (Standard 8080) - Beenden: Fenster schliessen oder Strg+C
rem Fotoquelle: Umgebungsvariable MT_FOTOS (Standard: Eigene Bilder), Datenordner: MT_DATA
setlocal EnableExtensions
chcp 65001 >nul
rem Das Skript kopiert sich einmal in den Temp-Ordner und laeuft von dort - so kann ein Update den Programmordner ersetzen.
if defined MT_APP goto :weiter
for %%I in ("%~dp0..") do set "MT_APP=%%~fI"
copy /y "%~f0" "%TEMP%\meine-touren-start.bat" >nul
call "%TEMP%\meine-touren-start.bat" %*
exit /b
:weiter
set "APP=%MT_APP%"
if not exist "%APP%\app\main.py" (
  echo app\main.py nicht gefunden - bitte das Skript im Ordner "windows" des entpackten meine-touren belassen.
  pause
  exit /b 1
)
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8080"
set "DATA=%MT_DATA%"
if "%DATA%"=="" set "DATA=%USERPROFILE%\Meine-Touren-Daten"
set "VENV=%LOCALAPPDATA%\meine-touren-venv"

set "PY="
for %%C in ("py -3.13" "py -3.12" "py -3.11" "py -3.10" "py -3" "python") do (
  if not defined PY (
    %%~C -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && set "PY=%%~C"
  )
)
if not defined PY (
  echo Python 3.10 oder neuer fehlt.
  echo Installation:  winget install Python.Python.3.12     ^(oder https://www.python.org/downloads/ - Haken bei "Add python.exe to PATH"^)
  pause
  exit /b 1
)

call :einrichten || (pause & exit /b 1)
if not exist "%DATA%" mkdir "%DATA%"
if "%MT_FOTOS%"=="" set "MT_FOTOS=%USERPROFILE%\Pictures"
set "PHOTOS_DIR=%MT_FOTOS%"
set "DATA_DIR=%DATA%"
set "BACKUP_DIR=%DATA%\backups-system"
set "APP_NAME=meine-touren-lokal"
set "TILE_FETCH=1"
set "MT_SELF_UPDATE=1"
set "PYTHONUTF8=1"
echo Foto-Quelle: %MT_FOTOS%
echo Meine Touren laeuft auf http://127.0.0.1:%PORT%   ^(Daten: %DATA%^)
start "" /min powershell -NoProfile -Command "Start-Sleep 4; Start-Process 'http://127.0.0.1:%PORT%'"
cd /d "%APP%"

:lauf
if exist "%DATA%\.neustart" del "%DATA%\.neustart"
"%VENV%\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
if exist "%DATA%\.neustart" (
  echo Neustart nach Update ...
  del "%DATA%\.neustart"
  if exist "%VENV%\garmin.ok" del "%VENV%\garmin.ok"
  call :einrichten || (pause & exit /b 1)
  goto :lauf
)
exit /b 0

:einrichten
if not exist "%VENV%\Scripts\python.exe" goto :install
fc /b "%APP%\requirements.txt" "%VENV%\req.txt" >nul 2>&1
if errorlevel 1 goto :install
goto :optional
:install
echo Einrichtung ^(einmalig, 1-2 Minuten^) ...
%PY% -m venv "%VENV%"
if errorlevel 1 ( echo Die virtuelle Umgebung konnte nicht angelegt werden. & exit /b 1 )
"%VENV%\Scripts\python.exe" -m pip install -q --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install -q -r "%APP%\requirements.txt"
if errorlevel 1 ( echo Die Pakete konnten nicht installiert werden - Internetverbindung pruefen. & exit /b 1 )
copy /y "%APP%\requirements.txt" "%VENV%\req.txt" >nul
:optional
rem Garmin-Konto-Anbindung (optional, braucht Python 3.12+; ohne sie geht der Datei-Import trotzdem)
if exist "%VENV%\garmin.ok" exit /b 0
"%VENV%\Scripts\python.exe" -m pip install -q -r "%APP%\requirements-optional.txt" >nul 2>&1
echo ok> "%VENV%\garmin.ok"
exit /b 0
