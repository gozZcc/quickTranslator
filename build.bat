@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   Translator - Build Script
echo ========================================
echo.

where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/3] Installing PyInstaller...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo Failed. Please run: pip install pyinstaller
        pause
        exit /b 1
    )
) else (
    echo [1/3] PyInstaller found
)

echo.
echo [2/3] Cleaning old files...
if exist dist\Translator.exe del /q dist\Translator.exe
if exist build rmdir /s /q build

echo.
echo [3/3] Building...
pyinstaller --onefile --name Translator --noconsole --clean --distpath dist translator.py

echo.
if exist build rmdir /s /q build
if exist Translator.spec del /q Translator.spec

if exist dist\Translator.exe (
    echo ========================================
    echo   Build OK: dist\Translator.exe
    echo ========================================
) else (
    echo ========================================
    echo   Build FAILED - check errors above
    echo ========================================
)
echo.
pause
