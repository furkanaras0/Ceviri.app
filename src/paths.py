import os
import sys
import subprocess


def get_app_dir() -> str:
    """
    Uygulamanın çalıştığı ana dizini döndürür.
    PyInstaller ile derlenmişse (.exe veya .app) çalıştırılabilir dosyanın bulunduğu dizini,
    normal Python ile çalışıyorsa proje kök dizinini döndürür.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def open_file_or_folder(target_path: str) -> None:
    """
    Windows, macOS ve Linux üzerinde belirtilen dosya veya klasörü
    sistemin varsayılan uygulamasıyla (Finder, Explorer vb.) açar.
    """
    if not target_path or not os.path.exists(target_path):
        return

    if sys.platform.startswith("win"):
        os.startfile(target_path)
    elif sys.platform == "darwin":  # macOS
        subprocess.run(["open", target_path])
    else:  # Linux
        subprocess.run(["xdg-open", target_path])
