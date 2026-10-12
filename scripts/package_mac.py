import os
import zipfile
import shutil

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dist_dir = os.path.join(root_dir, "dist")
os.makedirs(dist_dir, exist_ok=True)

mac_pkg_dir = os.path.join(dist_dir, "CeviriApp_Mac")
if os.path.exists(mac_pkg_dir):
    shutil.rmtree(mac_pkg_dir)
os.makedirs(mac_pkg_dir, exist_ok=True)

# Gerekli dosya ve klasörleri kopyala
shutil.copy2(os.path.join(root_dir, "main.py"), os.path.join(mac_pkg_dir, "main.py"))
shutil.copy2(os.path.join(root_dir, "requirements.txt"), os.path.join(mac_pkg_dir, "requirements.txt"))
shutil.copy2(os.path.join(root_dir, "run_mac.sh"), os.path.join(mac_pkg_dir, "run_mac.sh"))

# src klasörünü kopyala (__pycache__ hariç)
def copy_tree_without_pycache(src, dst):
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        if item == "__pycache__":
            continue
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_tree_without_pycache(s, d)
        else:
            shutil.copy2(s, d)

copy_tree_without_pycache(os.path.join(root_dir, "src"), os.path.join(mac_pkg_dir, "src"))

# Boş klasörler
os.makedirs(os.path.join(mac_pkg_dir, "çevrilen"), exist_ok=True)
os.makedirs(os.path.join(mac_pkg_dir, "çevrilmiş"), exist_ok=True)
os.makedirs(os.path.join(mac_pkg_dir, "data"), exist_ok=True)

# Mac Kullanım Kılavuzu
readme_content = """====================================================================
AKADEMİK MAKALE ÇEVİRİCİSİ - macOS KULLANIM REHBERİ
====================================================================

Bu paket macOS (Intel veya Apple Silicon M1/M2/M3/M4) bilgisayarlarda
çalışacak şekilde hazırlanmıştır.

NASIL ÇALIŞTIRILIR?
1. Bu klasörü Mac bilgisayarınızda istediğiniz bir yere açın (Örn: Masaüstü veya İndirilenler).
2. Terminal uygulamasını açın (Spotlight'ta "Terminal" yazarak bulabilirsiniz).
3. Klasörün içine girin. Örneğin klasör İndirilenler'deyse:
   cd ~/Downloads/CeviriApp_Mac
   (veya terminale "cd " yazıp klasörü terminal penceresine sürükleyip Enter'a basın)

4. Şu komutu yazıp Enter'a basın:
   bash run_mac.sh

Bu kadar! Betik sanal ortamı otomatik kuracak, gerekli paketleri yükleyecek
ve uygulamayı başlatacaktır.
====================================================================
"""
with open(os.path.join(mac_pkg_dir, "Mac_Kullanim_Kilavuzu.txt"), "w", encoding="utf-8") as f:
    f.write(readme_content)

# ZIP Arşivi Oluştur
zip_path = os.path.join(dist_dir, "CeviriApp_Mac.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(mac_pkg_dir):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, mac_pkg_dir)
            zipf.write(full_path, arcname=os.path.join("CeviriApp_Mac", rel_path))

print(f"[OK] Mac ZIP Paketi olusturuldu: {zip_path}")
