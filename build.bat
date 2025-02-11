@echo off
echo Cleaning previous builds...
rmdir /s /q build dist
echo Building executable...
pyinstaller --clean recorder.spec
echo Done!
pause 