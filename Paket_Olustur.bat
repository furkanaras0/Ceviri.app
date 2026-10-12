@echo off
chcp 65001 >nul
echo ========================================================
echo Akademik Çeviri Uygulaması - Paketleyici (PyInstaller)
echo ========================================================
echo.
echo Bu işlem uygulamanın bağımsız (Python gerektirmeyen)
echo EXE sürümünü ve dağıtım paketini oluşturacaktır.
echo Lütfen bekleyin...
echo.

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "scripts\build_exe.py"
) else (
    python "scripts\build_exe.py"
)

echo.
pause
