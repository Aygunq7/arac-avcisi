@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Araç Avcısı Mobil/PWA başlatılıyor...
if not exist .env (
  copy .env.example .env >nul
  echo .env dosyası oluşturuldu. Telegram/mail bilgilerini sonra buraya girebilirsin.
)
python --version >nul 2>&1
if errorlevel 1 (
  echo Python bulunamadı. Lütfen Python 3.11 veya 3.12 kur.
  pause
  exit /b 1
)
python -m venv .venv
call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Uygulama açılıyor...
echo Bilgisayardan: http://127.0.0.1:5050
echo Telefondan ayni Wi-Fi uzerinde: http://BILGISAYAR-IP:5050
echo Kapatmak icin bu pencerede CTRL+C yap.
python app.py
pause
