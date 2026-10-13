"""Modern ve profesyonel tasarım sistemi (Design Tokens & Styles)
TranslAI Academic Translator Studio için özel koyu ve aydınlık tema paletleri.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ThemeColors:
    # Ana Arka Planlar
    bg_dark: str = "#0b0f19"         # Derin uzay mavisi/gece
    sidebar_bg: str = "#111827"      # Sol panel arka planı
    card_bg: str = "#1e293b"         # Yüzey / Kart arka planı
    card_border: str = "#334155"     # Kart kenarlığı
    inner_card_bg: str = "#0f172a"   # İç kart / kutu arka planı
    input_bg: str = "#0f172a"        # Giriş alanları

    # Vurgu ve Marka Renkleri
    primary: str = "#6366f1"         # Indigo (Ana butonlar, vurgular)
    primary_hover: str = "#4f46e5"   # Koyu Indigo hover
    primary_light: str = "#818cf8"
    
    accent: str = "#38bdf8"          # Canlı gök mavisi (Rozetler, alt metinler)
    accent_hover: str = "#0ea5e9"

    # Durum Renkleri
    success: str = "#10b981"         # Zümrüt yeşili (Tamamlandı, aktif)
    success_hover: str = "#059669"
    success_bg: str = "#064e3b"

    warning: str = "#f59e0b"         # Amber (Beklemede, dikkat)
    warning_hover: str = "#d97706"
    warning_bg: str = "#78350f"

    danger: str = "#ef4444"          # Rose/Kırmızı (Durdur, sil, hata)
    danger_hover: str = "#dc2626"
    danger_bg: str = "#7f1d1d"

    # Metin Renkleri
    text_primary: str = "#f8fafc"    # Parlak beyaz
    text_secondary: str = "#94a3b8"  # Yumuşak gri
    text_muted: str = "#64748b"      # Soluk gri
    text_accent: str = "#38bdf8"     # Vurgu metni

    # Sidebar Menü Buton Renkleri
    nav_active_bg: str = "#312e81"   # Aktif menü öğesi (Koyu indigo)
    nav_active_fg: str = "#e0e7ff"
    nav_inactive_fg: str = "#94a3b8"
    nav_hover_bg: str = "#1f293d"


THEME = ThemeColors()
