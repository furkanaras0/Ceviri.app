#!/bin/bash
# ========================================================
# TranslAI Academic Studio - macOS Başlatıcı & Kurulumcu
# ========================================================

# Scriptin bulunduğu dizine geç
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "========================================================"
echo " TranslAI Academic Studio - macOS"
echo "========================================================"

# Python3 kontrolü
if ! command -v python3 &> /dev/null; then
    echo "[HATA] Python3 bulunamadı!"
    echo "Lütfen 'brew install python' veya python.org üzerinden Python 3 kurun."
    read -p "Çıkmak için Enter'a basın..."
    exit 1
fi

# Sanal ortam (.venv) kurulumu
if [ ! -d ".venv" ]; then
    echo "⚡ Sanal ortam ilk kez oluşturuluyor (.venv)..."
    python3 -m venv .venv
    echo "📦 Bağımlılıklar yükleniyor (bu işlem ilk seferde biraz sürebilir)..."
    .venv/bin/pip install --upgrade pip --quiet
    .venv/bin/pip install -r requirements.txt --quiet
    echo "✓ Kurulum tamamlandı!"
fi

echo "🚀 TranslAI Studio başlatılıyor..."
.venv/bin/python main.py
