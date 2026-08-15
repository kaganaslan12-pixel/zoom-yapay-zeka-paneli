@echo off
title Zoom Katilim Paneli - Sistem Kontrol ve Baslatici
color 0B

echo ===================================================
echo      SISTEM KONTROL EDILLIYOR LUTFEN BEKLEYIN...
echo ===================================================
echo.

:: 1. KONTROL: Python kodunda (server.py) yazım/syntax hatası var mı?
echo [1/3] Kod soz dizimi (Syntax) kontrol ediliyor...
python -m py_compile server.py
if %errorlevel% neq 0 (
    color 0C
    echo.
    echo [CRITICAL ERROR] Kodlarda hata tespit edildi! 
    echo Uygulama baslatilamadi. Lutfen server.py dosyanizi kontrol edin.
    pause
    exit
)
echo -- KODLAR TEMIZ! --
echo.

:: 2. KONTROL: Kritik veritabanı (JSON) dosyaları yerinde mi?
echo [2/3] Veri dosyalari kontrol ediliyor...
if not exist "users.json" echo [UYARI] users.json bulunamadi!
if not exist "rehber.json" echo [UYARI] rehber.json bulunamadi!
if not exist "katilimlar.json" echo [UYARI] katilimlar.json bulunamadi!
echo -- DOSYALAR KONTROL EDILDI --
echo.

:: 3. ASAMA: Sunucuyu başlat ve Arayüzü aç
echo [3/3] Her sey yolunda. Yerel sunucu ayaga kaldiriliyor...
echo.

:: Tarayıcısını 3 saniye sonra http://127.0.0.1:5050 adresinde otomatik aç
start "" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:5050"

:: Flask uygulamasını (server.py) çalıştır
python server.py

pause