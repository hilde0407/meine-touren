@echo off
rem Meine Touren mit Beispieldaten ausprobieren (Doppelklick) - ohne eigene Daten, ohne Konto.
rem Die Demo-Daten liegen in %USERPROFILE%\Meine-Touren-Demo und sind unabhaengig von deinen echten Daten.
set "MT_DEMO=1"
if "%MT_DATA%"=="" set "MT_DATA=%USERPROFILE%\Meine-Touren-Demo"
if not exist "%MT_DATA%\quelle" mkdir "%MT_DATA%\quelle"
set "MT_FOTOS=%MT_DATA%\quelle"
if "%~1"=="" (call "%~dp0Meine-Touren-lokal.bat" 8090) else (call "%~dp0Meine-Touren-lokal.bat" %*)
