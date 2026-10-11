# 🎓 Akademik Makale Çeviricisi (Academic Paper Translator)

Çift sütunlu akademik PDF makalelerini yapısal ve mantıksal sırasıyla okuyan, LLM (Google Gemini & OpenAI uyumlu modeller) ile çeviren ve iki dilli (EN / TR) Word dokümanı (.docx) üreten modern masaüstü uygulaması.

---

## ✨ Temel Özellikler

- **Çift Sütun ve Akademik PDF Desteği:** PyMuPDF tabanlı geometrik sıralama algoritması ile çift sütunlu bilimsel makalelerin okuma sırasını (sol sütun -> sağ sütun) kusursuz çözer.
- **BYOK (Kendi Anahtarını Getir - Bring Your Own Key):** Sunucusuz ve tamamen yerel mimari. Kullanıcılar kendi Google Gemini veya OpenAI uyumlu API anahtarlarını güvenle kullanır.
- **İki Dilli (Bilingual) Word (.docx) Çıktısı:**
  - Orijinal İngilizce metin: İtalik, 10pt, gri tonlu (`EN: `).
  - Türkçe çeviri metin: 11pt, okunaklı koyu tonlu (`TR: `).
- **Akıllı Görsel ve Şekil Çevirisi:** Makale içindeki grafik, diyagram ve şekiller tespit edilir; görsel üzerindeki İngilizce metinler estetiği bozmadan yerinde Türkçe'ye aktarılarak Word belgesine yerleştirilir.
- **Fail-Safe & Kaldığı Yerden Devam Etme:** Her paragraf anlık olarak yerel SQLite veritabanına işlenir. İnternet kesintisi veya kota sınırında çeviri duraklatılabilir ve kaldığı yerden devam ettirilebilir.
- **Canlı İlerleme & Hata Takibi:** Çeviri ve Word derleme aşamalarını anlık yüzde, kalan süre ve ayrıntılı hata bildirim paneli ile canlı izleme.
- **Sessiz Başlatma:** Windows ortamında siyah konsol penceresi açılmadan doğrudan arayüzü başlatan `Başlat.vbs` desteği.

---

## 🚀 Kurulum ve Çalıştırma

### Gereksinimler
- Python 3.10 veya üzeri
- Windows 10 / 11

### 1. Depoyu Klonlayın
```bash
git clone https://github.com/KULLANICI_ADINIZ/CeviriAPP.git
cd CeviriAPP
```

### 2. Sanal Ortam Oluşturun ve Paketleri Yükleyin
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Uygulamayı Başlatın
- **Normal Başlatma:**
  ```bash
  python main.py
  ```
- **Konsolsuz (Sessiz) Başlatma:**
  `Başlat.vbs` dosyasına çift tıklayarak doğrudan çalıştırabilirsiniz.

---

## 📁 Klasör Yapısı

```
ÇeviriAPP/
├── data/              # Yerel SQLite veritabanı (otomatik oluşturulur, Git'e dahil edilmez)
├── docs/              # Sistem ve gereksinim dokümanları
├── scripts/           # Bağımsız EXE derleme betikleri (PyInstaller)
├── src/               # Kaynak kodlar
│   ├── ui/            # CustomTkinter modern kullanıcı arayüzü
│   ├── database.py    # SQLite veri yönetim katmanı
│   ├── doc_exporter.py# İki dilli Word (.docx) derleyici
│   ├── image_translator.py # Görsel tespiti ve görsel içi çeviri
│   ├── pdf_parser.py  # Çift sütunlu akademik PDF ayrıştırıcı
│   └── translator.py  # LLM API istemcisi ve istem şablonları
├── çevrilen/          # Yüklenen kaynak PDF makaleler (Git'e dahil edilmez)
├── çevrilmiş/         # Üretilen iki dilli Word belgeleri (Git'e dahil edilmez)
├── Başlat.vbs         # Konsolsuz arka plan başlatıcı
├── requirements.txt   # Bağımlılık listesi
└── main.py            # Uygulama giriş noktası
```

---

## 🔒 Gizlilik ve Güvenlik
- API anahtarlarınız asla uzak bir sunucuya veya depoya aktarılmaz; yalnızca yerel bilgisayarınızdaki SQLite dosyasında tutulur.
- `.gitignore` yapılandırması sayesinde kişisel PDF'leriniz, oluşturulan Word çıktıları ve API anahtarı içeren veritabanı dosyaları GitHub'a gönderilmez.
