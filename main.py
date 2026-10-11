import sys
import os

# Proje kök dizinini sys.path'e ekle
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# pythonw.exe ile çalışırken terminal olmadığı için sys.stdout None olabilir; hata almamak için yönlendir
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from src.ui.main_window import AcademicTranslatorApp


def main():
    """Uygulamanın ana giriş noktası."""
    app = AcademicTranslatorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
