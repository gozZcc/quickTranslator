@echo off
chcp 65001 >nul 2>&1
echo ========================================
echo   划词翻译器 - Windows 打包脚本
echo ========================================
echo.

where pyinstaller >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/3] 安装 PyInstaller...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo 安装失败，请手动运行: pip install pyinstaller
        pause
        exit /b 1
    )
) else (
    echo [1/3] PyInstaller 已安装
)

echo.
echo [2/3] 清理旧文件...
if exist dist\Translator.exe del /q dist\Translator.exe
if exist build rmdir /s /q build

echo.
echo [3/3] 打包中...
pyinstaller --onefile --name Translator --noconsole --clean --distpath dist translator.py

echo.
if exist build rmdir /s /q build
if exist Translator.spec del /q Translator.spec

if exist dist\Translator.exe (
    echo ========================================
    echo   打包成功!
    echo   输出文件: dist\Translator.exe
    echo ========================================
) else (
    echo ========================================
    echo   打包失败，请检查上方错误信息
    echo ========================================
)
echo.
pause
