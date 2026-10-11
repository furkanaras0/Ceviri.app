import os
import subprocess
import sys
import customtkinter


def build():
    print("=" * 60)
    print("Akademik Çeviri Uygulaması - PyInstaller Derleme Başlıyor")
    print("=" * 60)

    # Proje kök dizini (scripts'in bir üstü)
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    main_file = os.path.join(root_dir, "main.py")

    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconsole",
        "--onefile",
        "--name=AkademikCevirici",
        "--paths=" + root_dir,
        "--collect-all=customtkinter",
        "--collect-all=pymupdf",
        "--collect-all=docx",
        "--collect-all=google.genai",
        main_file
    ]

    print(f"Çalıştırılan komut:\n{' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=root_dir)

    if result.returncode == 0:
        exe_path = os.path.join(root_dir, "dist", "AkademikCevirici.exe")
        print("\n" + "=" * 60)
        print("✓ DERLEME BAŞARIYLA TAMAMLANDI!")
        print(f"Üretilen Bağımsız EXE: {exe_path}")
        print("=" * 60)
    else:
        print("\n✗ Derleme sırasında bir hata oluştu.")


if __name__ == "__main__":
    build()
