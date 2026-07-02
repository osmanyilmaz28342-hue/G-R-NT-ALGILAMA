@echo off
chcp 65001 >nul
title Shift + Sag Click Bot v9.0

echo.
echo  +==================================================+
echo  ^|   Shift + Sag Click Bot  v9.0  - OpenCV         ^|
echo  ^|   mss + CLAHE + Bezier + 7 Mod + Profil         ^|
echo  +==================================================+
echo.

REM Python kontrol
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [HATA] Python bulunamadi!
    echo.
    echo  Cozum:
    echo    1. https://python.org adresine git
    echo    2. Python 3.10 veya uzeri indir ve kur
    echo    3. Kurulumda "Add Python to PATH" secenegini ISARETLE
    echo.
    pause
    exit /b 1
)

echo  [OK] Python bulundu:
python --version
echo.

REM pip guncelle
echo  [..] pip guncelleniyor...
python -m pip install --upgrade pip --quiet
echo.

REM Paketleri yukle - gruplar halinde
echo  [..] Temel paketler yukleniyor...
pip install opencv-python numpy Pillow mss --upgrade --quiet
echo  [..] Otomasyon paketleri yukleniyor...
pip install pyautogui pyscreeze pygetwindow --upgrade --quiet
echo  [..] Sistem paketleri yukleniyor...
pip install psutil keyboard pystray --upgrade --quiet

echo.
echo  [OK] Tum paketler tamam.
echo  [OK] Bot aciliyor...
echo.

REM Botu calistir
python "%~dp0main.py"

REM Hata kontrolu
if %errorlevel% neq 0 (
    echo.
    echo  +====================================+
    echo  ^|   Program hatayla kapandi!         ^|
    echo  +====================================+
    echo.
    echo  Cozum onerileri:
    echo    1. python -m pip install --upgrade pip
    echo    2. pip install opencv-python numpy mss --upgrade
    echo    3. Bu dosyaya sag tik - Yonetici olarak calistir
    echo    4. Python 3.10 veya uzeri kurulu olmali
    echo.
    pause
)
