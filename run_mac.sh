#!/bin/bash
# Akademik Çeviri Uygulaması - macOS Başlatıcı

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

echo "========================================================"
echo " Akademik Çeviri Uygulaması - macOS"
echo "========================================================"

# Python3 kontrolü
if ! command -v python3 &> /dev/null; then
    echo "[HATA] Python3 bulunamadı! Lütfen python.org adresinden veya 'brew install python' ile kurun."
    exit 1
fi

# Sanal ortam (venv) kontrolü
if [ ! -d ".venv" ]; then
    echo "Sanal ortam oluşturuluyor (.venv)..."
    python3 -m venv .venv
    echo "Gerekli kütüphaneler yükleniyor..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

echo "Uygulama başlatılıyor..."
.venv/bin/python main.py
