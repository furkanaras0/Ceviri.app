import os
import subprocess
import sys
import shutil
import zipfile

# Windows terminal Türkçe kod sayfası uyumluluğu
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def build(rebuild_exe: bool = True):
    print("=" * 60)
    print("Akademik Ceviri Uygulamasi - Bagimsiz Paketleme Basliyor")
    print("=" * 60)

    # Proje kök dizini (scripts'in bir üstü)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_file = os.path.join(root_dir, "main.py")
    exe_path = os.path.join(root_dir, "dist", "AkademikCevirici.exe")

    if rebuild_exe or not os.path.exists(exe_path):
        cmd = [
            sys.executable,
            "-m", "PyInstaller",
            "--noconsole",
            "--onefile",
            "--clean",
            "--name=AkademikCevirici",
            "--paths=" + root_dir,
            "--collect-all=customtkinter",
            "--collect-all=pymupdf",
            "--collect-all=docx",
            "--collect-all=google.genai",
            "--collect-all=certifi",
            "--collect-all=PIL",
            "--collect-all=pydantic",
            main_file
        ]

        print(f"Calistirilacak komut:\n{' '.join(cmd)}\n")
        result = subprocess.run(cmd, cwd=root_dir)

        if result.returncode != 0:
            print("\n[HATA] Derleme sirasinda bir sorun olustu.")
            return False

    if not os.path.exists(exe_path):
        print(f"\n[HATA] EXE dosyasi bulunamadi: {exe_path}")
        return False

    print("\n" + "=" * 60)
    print("[OK] EXE DERLEMESI HAZIR!")
    print(f"Uretilen Bagimsiz EXE: {exe_path}")
    print("=" * 60)

    # Dağıtılabilir Taşınabilir Paket Klasörü Hazırla
    pkg_dir = os.path.join(root_dir, "dist", "CeviriApp_Paket")
    if os.path.exists(pkg_dir):
        shutil.rmtree(pkg_dir)
    os.makedirs(pkg_dir, exist_ok=True)

    # Gerekli alt dizinleri oluştur
    os.makedirs(os.path.join(pkg_dir, "çevrilen"), exist_ok=True)
    os.makedirs(os.path.join(pkg_dir, "çevrilmiş"), exist_ok=True)
    os.makedirs(os.path.join(pkg_dir, "data"), exist_ok=True)

    # EXE'yi paket klasörüne kopyala
    pkg_exe = os.path.join(pkg_dir, "AkademikCevirici.exe")
    shutil.copy2(exe_path, pkg_exe)

    # BeniOku.txt dosyası ekle
    readme_content = """====================================================================
AKADEMIK MAKALE CEVIRICISI - TASINABILIR SURUM (PORTABLE)
====================================================================

Bu paket, Python veya herhangi bir ek kutuphane yuklu OLMAYAN tum
Windows (10 / 11) bilgisayarlarda dogrudan calisacak sekilde hazirlanmistir.

NASIL KULLANILIR?
1. "AkademikCevirici.exe" dosyasina cift tiklayarak uygulamayi baslatin.
2. Acilan pencerede sag ustteki "Ayarlar" butonuna tiklayin.
3. Ceviri yapmak istediginiz yapay zeka servisini secip API anahtarinizi girin:
   - Google Gemini (Onerilen - Ucretsiz API: aistudio.google.com)
   - DeepSeek veya OpenRouter
4. "PDF Dosyasi Sec" butonuna basarak makalenizi yukleyin ve ceviriyi baslatin.

KLASORLER:
- cevrilen/  : Yuklediginiz orijinal PDF dosyalarinin arsivi.
- cevrilmis/ : Cevrilen makalelerin Word (.docx) olarak kaydedildigi klasor.
- data/      : Ayarlarinizin ve ceviri gecmisinizin saklandigi yerel veritabani.

KISAYOL:
- Isterseniz "Masaustune_Kisayol_Olustur.bat" dosyasina cift tiklayarak
  masaustunuze tek tikla calistirma kisayolu ekleyebilirsiniz.

NOT:
Bu klasoru flash bellege (USB) veya baska bir bilgisayara oldugu gibi
kopyalayip goturebilirsiniz. Bilgisayara hicbir sey yuklemenize gerek yoktur.
====================================================================
"""
    with open(os.path.join(pkg_dir, "BeniOku.txt"), "w", encoding="utf-8") as f:
        f.write(readme_content)

    # Masaüstüne Kısayol Oluşturucu .bat dosyası ekle
    shortcut_bat = r"""@echo off
chcp 65001 >nul
echo Masaustune kisayol olusturuluyor...
set SCRIPT_DIR=%~dp0
set TARGET=%SCRIPT_DIR%AkademikCevirici.exe
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut([Environment]::GetFolderPath('Desktop') + '\Akademik Cevirici.lnk'); $s.TargetPath = '%TARGET%'; $s.WorkingDirectory = '%SCRIPT_DIR%'; $s.IconLocation = '%TARGET%,0'; $s.Save()"
echo.
echo Basariyla masaustune kisayol olusturuldu!
pause
"""
    with open(os.path.join(pkg_dir, "Masaustune_Kisayol_Olustur.bat"), "w", encoding="utf-8") as f:
        f.write(shortcut_bat)

    # ZIP Arşivi Oluştur
    zip_path = os.path.join(root_dir, "dist", "CeviriApp_Paket.zip")
    print(f"\nZIP arsivi paketleniyor: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(pkg_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, pkg_dir)
                zipf.write(full_path, arcname=os.path.join("CeviriApp", rel_path))

    print("\n" + "=" * 60)
    print("[OK] DAGITIM PAKETI EKSIKSIZ HAZIRLANDI!")
    print(f"Klasor : {pkg_dir}")
    print(f"ZIP    : {zip_path}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    rebuild = True
    if "--package-only" in sys.argv:
        rebuild = False
    build(rebuild_exe=rebuild)
