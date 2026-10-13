"""Profesyonel Loglama ve Çökme Raporlayıcı (Crash Reporter)
Uygulama çökmelerini yakalar, logs/ klasörüne kaydeder ve kullanıcıya anlaşılır hata diyaloğu gösterir.
"""

import os
import sys
import logging
import traceback
import threading
from datetime import datetime
from src.paths import get_app_dir, open_file_or_folder


def get_logs_dir() -> str:
    """Logs klasörünün yolunu döndürür ve oluşturur."""
    log_dir = os.path.join(get_app_dir(), "logs")
    os.makedirs(log_dir, exist_ok=True)
    return log_dir


def setup_logger() -> logging.Logger:
    """Uygulama genelinde kullanılacak loglama motorunu yapılandırır."""
    logger = logging.getLogger("TranslAI")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        log_dir = get_logs_dir()
        log_file = os.path.join(log_dir, "app.log")

        # Dosya loglayıcısı (UTF-8)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(threadName)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Konsol loglayıcısı
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(file_formatter)
        logger.addHandler(stream_handler)

    return logger


logger = setup_logger()


def handle_unhandled_exception(exc_type, exc_value, exc_traceback):
    """Sistem genelindeki yakalanmamış hataları loglar ve kullanıcıya hata raporu sunar."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    crash_log_name = f"crash_{timestamp}.log"
    crash_log_path = os.path.join(get_logs_dir(), crash_log_name)

    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    full_trace = "".join(tb_lines)

    logger.critical(f"KRİTİK HATA! Uygulama durdu:\n{full_trace}")

    try:
        with open(crash_log_path, "w", encoding="utf-8") as f:
            f.write(f"=== TranslAI Crash Report [{datetime.now().isoformat()}] ===\n\n")
            f.write(f"Python: {sys.version}\n")
            f.write(f"Platform: {sys.platform}\n")
            f.write(f"Hata Tipi: {exc_type.__name__}\n")
            f.write(f"Hata Mesajı: {str(exc_value)}\n\n")
            f.write("Ayrıntılı Hata İzi (Traceback):\n")
            f.write(full_trace)
    except Exception:
        pass

    # Kullanıcıya hata modalı göster
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        
        msg = (
            f"Beklenmeyen bir sistem hatası meydana geldi:\n\n"
            f"{exc_type.__name__}: {str(exc_value)}\n\n"
            f"Ayrıntılı hata raporu kaydedildi:\n{crash_log_path}\n\n"
            f"Hata raporu klasörünü açmak ister misiniz?"
        )
        if messagebox.askyesno("TranslAI - Hata Raporlayıcı (Crash Reporter)", msg):
            open_file_or_folder(get_logs_dir())
        root.destroy()
    except Exception:
        pass


def install_crash_reporter():
    """Global sys.excepthook ve threading excepthook kurulumunu yapar."""
    sys.excepthook = handle_unhandled_exception

    def thread_exception_handler(args):
        handle_unhandled_exception(args.exc_type, args.exc_value, args.exc_traceback)

    if hasattr(threading, "excepthook"):
        threading.excepthook = thread_exception_handler
