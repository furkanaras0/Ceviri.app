import os
import re
import time
import threading
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox

from src import database
from src import pdf_parser
from src import translator
from src import doc_exporter
from src import image_translator
from src.paths import get_app_dir, open_file_or_folder
from src.logger import logger
from src.ui.history_window import HistoryWindow
from src.ui.theme import THEME

# CustomTkinter Temel Görünüm Ayarları
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AcademicTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Veritabanını ilklendir
        database.init_db()

        # Pencere Yapılandırması
        self.title("TranslAI Academic Studio • Profesyonel Akademik Çevirici")
        self.geometry("1240x860")
        self.minsize(1040, 720)
        self.configure(fg_color=THEME.bg_dark)

        # Durum Değişkenleri
        self.selected_pdf_path: Optional[str] = None
        self.total_pdf_pages: int = 0
        self.parsed_paragraphs: List[Any] = []
        self.is_translating: bool = False
        self.cancel_requested: bool = False
        self.last_exported_docx: Optional[str] = None
        self.active_tab: str = "studio"
        self.cached_history: List[Dict[str, Any]] = []
        self.archive_selected_file: Optional[str] = None

        # Arayüz Bileşenlerini Kur
        self._build_ui()

        # Kayıtlı Ayarları Yükle
        self._load_saved_settings()

        # İlk sekmeyi göster
        self._navigate_to("studio")

    def _build_ui(self):
        # Ana Taşıyıcı Frame
        self.main_container = ctk.CTkFrame(self, fg_color=THEME.bg_dark, corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        # 1. Sol Sidebar
        self._create_sidebar()

        # 2. Sağ Çalışma Alanı (Sekme Konteyneri)
        self.content_area = ctk.CTkFrame(self.main_container, fg_color=THEME.bg_dark, corner_radius=0)
        self.content_area.pack(side="left", fill="both", expand=True)

        # Sayfaları Oluştur
        self.views: Dict[str, ctk.CTkFrame] = {}
        self.views["studio"] = self._create_studio_view()
        self.views["glossary"] = self._create_glossary_view()
        self.views["archive"] = self._create_archive_view()
        self.views["settings"] = self._create_settings_view()
        self.views["guide"] = self._create_guide_view()

    # ==========================================
    # SOL SİDEBAR
    # ==========================================
    def _create_sidebar(self):
        self.sidebar = ctk.CTkFrame(
            self.main_container,
            width=260,
            fg_color=THEME.sidebar_bg,
            corner_radius=0,
            border_width=0
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Marka / Logo Bölümü
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.pack(fill="x", padx=20, pady=(24, 20))

        logo_row = ctk.CTkFrame(brand_frame, fg_color="transparent")
        logo_row.pack(anchor="w")

        logo_icon = ctk.CTkLabel(
            logo_row,
            text="⚡",
            font=ctk.CTkFont(size=24)
        )
        logo_icon.pack(side="left", padx=(0, 8))

        logo_title = ctk.CTkLabel(
            logo_row,
            text="TranslAI",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=THEME.text_primary
        )
        logo_title.pack(side="left")

        badge = ctk.CTkLabel(
            logo_row,
            text="PRO",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color=THEME.primary,
            text_color="white",
            corner_radius=4,
            width=36,
            height=18
        )
        badge.pack(side="left", padx=(8, 0))

        sub_brand = ctk.CTkLabel(
            brand_frame,
            text="Akademik Çeviri Stüdyosu",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_secondary
        )
        sub_brand.pack(anchor="w", pady=(2, 0))

        # İnce Ayrım Çizgisi
        sep = ctk.CTkFrame(self.sidebar, height=1, fg_color=THEME.card_border)
        sep.pack(fill="x", padx=18, pady=(0, 16))

        # Menü Başlığı
        menu_lbl = ctk.CTkLabel(
            self.sidebar,
            text="NAVİGASYON",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME.text_muted
        )
        menu_lbl.pack(anchor="w", padx=20, pady=(0, 8))

        # Menü Butonları
        self.nav_buttons: Dict[str, ctk.CTkButton] = {}

        nav_items = [
            ("studio", "🚀  Çeviri Stüdyosu"),
            ("glossary", "📖  Terim Sözlüğü"),
            ("archive", "📚  Çeviri Arşivi"),
            ("settings", "⚙️  Model & API"),
            ("guide", "ℹ️  Kılavuz & İpuçları"),
        ]

        for tab_id, tab_label in nav_items:
            btn = ctk.CTkButton(
                self.sidebar,
                text=tab_label,
                anchor="w",
                height=40,
                corner_radius=8,
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color="transparent",
                hover_color=THEME.nav_hover_bg,
                text_color=THEME.nav_inactive_fg,
                command=lambda t=tab_id: self._navigate_to(t)
            )
            btn.pack(fill="x", padx=12, pady=2)
            self.nav_buttons[tab_id] = btn

        # Alt Bölüm (API Durumu ve Tema Seçici)
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", padx=16, pady=20)

        # Durum Kartı
        status_box = ctk.CTkFrame(
            bottom_frame,
            fg_color=THEME.card_bg,
            corner_radius=10,
            border_width=1,
            border_color=THEME.card_border
        )
        status_box.pack(fill="x", pady=(0, 12))

        status_content = ctk.CTkFrame(status_box, fg_color="transparent")
        status_content.pack(fill="x", padx=12, pady=10)

        status_head = ctk.CTkLabel(
            status_content,
            text="SİSTEM DURUMU",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=THEME.text_muted
        )
        status_head.pack(anchor="w")

        self.sidebar_api_status = ctk.CTkLabel(
            status_content,
            text="● Kontrol ediliyor...",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME.text_secondary,
            anchor="w"
        )
        self.sidebar_api_status.pack(anchor="w", pady=(3, 0))

        self.sidebar_model_status = ctk.CTkLabel(
            status_content,
            text="Model: -",
            font=ctk.CTkFont(size=11),
            text_color=THEME.text_muted,
            anchor="w"
        )
        self.sidebar_model_status.pack(anchor="w")

        # Tema Değiştirici
        theme_row = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        theme_row.pack(fill="x")

        ctk.CTkLabel(
            theme_row,
            text="Görünüm:",
            font=ctk.CTkFont(size=11),
            text_color=THEME.text_muted
        ).pack(side="left")

        self.theme_menu = ctk.CTkOptionMenu(
            theme_row,
            values=["Dark", "Light", "System"],
            width=90,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color=THEME.card_bg,
            button_color=THEME.card_border,
            command=self._change_appearance_mode
        )
        self.theme_menu.pack(side="right")
        self.theme_menu.set("Dark")

    def _navigate_to(self, tab_id: str):
        self.active_tab = tab_id

        for t_id, btn in self.nav_buttons.items():
            if t_id == tab_id:
                btn.configure(
                    fg_color=THEME.nav_active_bg,
                    text_color=THEME.nav_active_fg
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=THEME.nav_inactive_fg
                )

        for t_id, frame in self.views.items():
            if t_id == tab_id:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        if tab_id == "archive":
            self._archive_refresh_list()
        elif tab_id == "glossary":
            self._glossary_refresh_list()

    def _change_appearance_mode(self, mode: str):
        ctk.set_appearance_mode(mode)

    # ==========================================
    # SEKME 1: ÇEVİRİ STÜDYOSU (ANA EKRAN)
    # ==========================================
    def _create_studio_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.content_area, fg_color=THEME.bg_dark, corner_radius=0)

        # Üst Header Bar
        header = ctk.CTkFrame(view, height=64, fg_color=THEME.sidebar_bg, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=24)

        title_box = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_box.pack(side="left", fill="y", pady=12)

        page_title = ctk.CTkLabel(
            title_box,
            text="Çeviri Çalışma Alanı",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME.text_primary
        )
        page_title.pack(anchor="w")

        page_sub = ctk.CTkLabel(
            title_box,
            text="Çift sütunlu akademik PDF'leri yapısal çevirir, görselleri Türkçeleştirir ve Word (.docx) üretir.",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_muted
        )
        page_sub.pack(anchor="w")

        # Üst Sağ Rozet
        self.top_status_badge = ctk.CTkLabel(
            header_inner,
            text="Hazır",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=THEME.card_bg,
            text_color=THEME.accent,
            corner_radius=6,
            padx=12,
            pady=4
        )
        self.top_status_badge.pack(side="right", pady=18)

        # 2 Sütunlu Ana Gövde
        body = ctk.CTkFrame(view, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=18)

        # SOL PANEL: Kontrol ve Yapılandırma (440px)
        left_col = ctk.CTkScrollableFrame(
            body,
            width=440,
            fg_color="transparent",
            corner_radius=0
        )
        left_col.pack(side="left", fill="both", padx=(0, 16))

        # Kart 1: PDF Belgesi Seçimi & Sayfa Aralığı
        self._build_studio_file_card(left_col)

        # Kart 2: İşlem & Performans Seçenekleri (Paralel İş Parçacığı & Görsel)
        self._build_studio_options_card(left_col)

        # Kart 3: Kontrol & İlerleme
        self._build_studio_progress_card(left_col)

        # SAĞ PANEL: Canlı Akış & Önizleme
        self._build_studio_preview_panel(body)

        return view

    def _build_studio_file_card(self, parent):
        card = ctk.CTkFrame(
            parent,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        card.pack(fill="x", pady=(0, 14))

        # Kart Başlığı
        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 10))

        ctk.CTkLabel(
            head,
            text="1. PDF Belgesi & Sayfa Aralığı",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME.text_primary
        ).pack(side="left")

        # Seçim Butonu ve Yükleme Alanı
        dropzone = ctk.CTkFrame(
            card,
            fg_color=THEME.inner_card_bg,
            corner_radius=10,
            border_width=1,
            border_color=THEME.card_border
        )
        dropzone.pack(fill="x", padx=16, pady=(0, 10))

        dz_content = ctk.CTkFrame(dropzone, fg_color="transparent")
        dz_content.pack(fill="x", padx=14, pady=12)

        self.select_file_btn = ctk.CTkButton(
            dz_content,
            text="📁  PDF Dosyası Seç...",
            height=38,
            corner_radius=8,
            fg_color=THEME.primary,
            hover_color=THEME.primary_hover,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._select_pdf_file
        )
        self.select_file_btn.pack(fill="x", pady=(0, 8))

        self.file_name_label = ctk.CTkLabel(
            dz_content,
            text="Henüz bir dosya seçilmedi.",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_muted,
            anchor="w",
            wraplength=380
        )
        self.file_name_label.pack(fill="x")

        # Sayfa Aralığı Seçim Satırı
        page_range_row = ctk.CTkFrame(card, fg_color="transparent")
        page_range_row.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            page_range_row,
            text="📑 Sayfa Aralığı:",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME.text_secondary
        ).pack(side="left", padx=(0, 8))

        self.page_range_entry = ctk.CTkEntry(
            page_range_row,
            placeholder_text="Örn: 1-5 veya Tümü",
            width=140,
            height=30,
            corner_radius=6,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.page_range_entry.pack(side="left", padx=(0, 8))
        self.page_range_entry.insert(0, "Tümü")
        self.page_range_entry.bind("<FocusOut>", lambda e: self._on_page_range_changed())

        apply_range_btn = ctk.CTkButton(
            page_range_row,
            text="Uygula",
            width=65,
            height=30,
            corner_radius=6,
            fg_color=THEME.inner_card_bg,
            hover_color=THEME.card_border,
            font=ctk.CTkFont(size=11),
            command=self._on_page_range_changed
        )
        apply_range_btn.pack(side="left")

        # Analiz Rozeti / Bilgisi
        self.file_status_box = ctk.CTkFrame(card, fg_color="transparent")
        self.file_status_box.pack(fill="x", padx=16, pady=(0, 12))

        self.file_info_badge = ctk.CTkLabel(
            self.file_status_box,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=THEME.accent,
            anchor="w",
            wraplength=380,
            justify="left"
        )
        self.file_info_badge.pack(fill="x")

        # Fail-Safe Butonu
        self.resume_btn = ctk.CTkButton(
            self.file_status_box,
            text="⚡ Kaldığı Yerden Devam Et (Fail-Safe)",
            height=34,
            corner_radius=8,
            fg_color=THEME.warning,
            hover_color=THEME.warning_hover,
            text_color="black",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._resume_existing_translation
        )

    def _build_studio_options_card(self, parent):
        card = ctk.CTkFrame(
            parent,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        card.pack(fill="x", pady=(0, 14))

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 8))

        ctk.CTkLabel(
            head,
            text="2. Performans & Çeviri Seçenekleri",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME.text_primary
        ).pack(side="left")

        quick_settings_btn = ctk.CTkButton(
            head,
            text="⚙️ Modeller",
            width=80,
            height=26,
            corner_radius=6,
            fg_color=THEME.inner_card_bg,
            hover_color=THEME.card_border,
            font=ctk.CTkFont(size=11),
            command=lambda: self._navigate_to("settings")
        )
        quick_settings_btn.pack(side="right")

        opts_body = ctk.CTkFrame(card, fg_color="transparent")
        opts_body.pack(fill="x", padx=16, pady=(0, 14))

        # Eşzamanlılık (Worker Threads) Satırı
        speed_row = ctk.CTkFrame(opts_body, fg_color="transparent")
        speed_row.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            speed_row,
            text="⚡ Çeviri Hızı (Paralel İş):",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=THEME.text_primary
        ).pack(side="left")

        self.concurrency_combo = ctk.CTkComboBox(
            speed_row,
            values=["1x (Sıralı / Güvenli)", "2x (Hızlı)", "3x (Çok Hızlı)", "4x (Maksimum Hız)"],
            width=165,
            height=30,
            corner_radius=6,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.concurrency_combo.pack(side="right")
        self.concurrency_combo.set("3x (Çok Hızlı)")

        # Görsel İçi Çeviri Switch
        self.translate_images_switch = ctk.CTkSwitch(
            opts_body,
            text="Şekil ve Grafikleri Türkçe Olarak Yeniden Çiz",
            font=ctk.CTkFont(size=12, weight="bold"),
            progress_color=THEME.primary,
            text_color=THEME.text_primary
        )
        self.translate_images_switch.pack(anchor="w", pady=(0, 10))
        self.translate_images_switch.select()

        # Aktif Model & Önbellek Bilgisi
        info_row = ctk.CTkFrame(opts_body, fg_color=THEME.inner_card_bg, corner_radius=8)
        info_row.pack(fill="x")

        ctk.CTkLabel(
            info_row,
            text="Model:",
            font=ctk.CTkFont(size=11),
            text_color=THEME.text_muted
        ).pack(side="left", padx=(10, 4), pady=8)

        self.current_model_tag = ctk.CTkLabel(
            info_row,
            text="gemini-flash-latest",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=THEME.accent
        )
        self.current_model_tag.pack(side="left", pady=8)

        self.cache_stat_tag = ctk.CTkLabel(
            info_row,
            text="• Önbellek Aktif",
            font=ctk.CTkFont(size=11),
            text_color=THEME.success
        )
        self.cache_stat_tag.pack(side="right", padx=10, pady=8)

    def _build_studio_progress_card(self, parent):
        card = ctk.CTkFrame(
            parent,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        card.pack(fill="x", pady=(0, 14))

        head = ctk.CTkFrame(card, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 10))

        ctk.CTkLabel(
            head,
            text="3. Çeviri Yönetimi & İlerleme",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME.text_primary
        ).pack(side="left")

        btn_box = ctk.CTkFrame(card, fg_color="transparent")
        btn_box.pack(fill="x", padx=16, pady=(0, 12))

        self.start_btn = ctk.CTkButton(
            btn_box,
            text="🚀  Çeviriyi Başlat",
            height=44,
            corner_radius=8,
            fg_color=THEME.primary,
            hover_color=THEME.primary_hover,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._start_translation_threaded
        )
        self.start_btn.pack(fill="x", pady=(0, 8))

        self.cancel_btn = ctk.CTkButton(
            btn_box,
            text="⏹  Durdur / İptal",
            height=34,
            corner_radius=8,
            fg_color=THEME.card_border,
            hover_color=THEME.danger,
            text_color=THEME.text_secondary,
            font=ctk.CTkFont(size=12),
            state="disabled",
            command=self._cancel_translation
        )
        self.cancel_btn.pack(fill="x")

        # İlerleme Çubuğu
        prog_box = ctk.CTkFrame(card, fg_color="transparent")
        prog_box.pack(fill="x", padx=16, pady=(4, 12))

        self.progress_bar = ctk.CTkProgressBar(
            prog_box,
            height=10,
            corner_radius=5,
            progress_color=THEME.primary,
            fg_color=THEME.inner_card_bg
        )
        self.progress_bar.pack(fill="x", pady=(0, 6))
        self.progress_bar.set(0.0)

        # Durum Metni
        self.status_label = ctk.CTkLabel(
            prog_box,
            text="Durum: Beklemede",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_secondary,
            anchor="w"
        )
        self.status_label.pack(fill="x")

        # Metrik Kutuları
        metrics_grid = ctk.CTkFrame(card, fg_color="transparent")
        metrics_grid.pack(fill="x", padx=16, pady=(0, 14))

        m1 = ctk.CTkFrame(metrics_grid, fg_color=THEME.inner_card_bg, corner_radius=8)
        m1.pack(side="left", fill="x", expand=True, padx=(0, 6))

        ctk.CTkLabel(m1, text="PARAGRAF", font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME.text_muted).pack(pady=(6, 0))
        self.metric_count_lbl = ctk.CTkLabel(m1, text="0 / 0", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME.text_primary)
        self.metric_count_lbl.pack(pady=(0, 6))

        m2 = ctk.CTkFrame(metrics_grid, fg_color=THEME.inner_card_bg, corner_radius=8)
        m2.pack(side="left", fill="x", expand=True, padx=(6, 0))

        ctk.CTkLabel(m2, text="KALAN SÜRE", font=ctk.CTkFont(size=10, weight="bold"), text_color=THEME.text_muted).pack(pady=(6, 0))
        self.metric_eta_lbl = ctk.CTkLabel(m2, text="-", font=ctk.CTkFont(size=14, weight="bold"), text_color=THEME.accent)
        self.metric_eta_lbl.pack(pady=(0, 6))

        # Çıktı / Başarı Kartı
        self.actions_row = ctk.CTkFrame(
            card,
            fg_color=THEME.success_bg,
            corner_radius=10,
            border_width=1,
            border_color=THEME.success
        )

        success_inner = ctk.CTkFrame(self.actions_row, fg_color="transparent")
        success_inner.pack(fill="x", padx=12, pady=12)

        ctk.CTkLabel(
            success_inner,
            text="✓ Word Belgesi Başarıyla Hazırlandı!",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#a7f3d0"
        ).pack(anchor="w", pady=(0, 8))

        self.open_doc_btn = ctk.CTkButton(
            success_inner,
            text="📄  Word Belgesini Aç (.docx)",
            height=36,
            fg_color=THEME.success,
            hover_color=THEME.success_hover,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_output_doc
        )
        self.open_doc_btn.pack(fill="x", pady=(0, 6))

        self.open_folder_btn = ctk.CTkButton(
            success_inner,
            text="📁  Klasörde Göster",
            height=32,
            fg_color=THEME.card_border,
            hover_color=THEME.card_bg,
            font=ctk.CTkFont(size=12),
            command=self._open_output_folder
        )
        self.open_folder_btn.pack(fill="x")

    def _build_studio_preview_panel(self, parent):
        right_panel = ctk.CTkFrame(
            parent,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        right_panel.pack(side="left", fill="both", expand=True)

        p_head = ctk.CTkFrame(right_panel, fg_color="transparent")
        p_head.pack(fill="x", padx=18, pady=(14, 10))

        title_box = ctk.CTkFrame(p_head, fg_color="transparent")
        title_box.pack(side="left")

        ctk.CTkLabel(
            title_box,
            text="Canlı Çeviri Akışı ve Önizleme",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=THEME.text_primary
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Paragraf bazında çift dilli anlık çeviri konsolu",
            font=ctk.CTkFont(size=11),
            text_color=THEME.text_muted
        ).pack(anchor="w")

        tools = ctk.CTkFrame(p_head, fg_color="transparent")
        tools.pack(side="right")

        copy_btn = ctk.CTkButton(
            tools,
            text="📋 Kopyala",
            width=80,
            height=30,
            corner_radius=6,
            fg_color=THEME.inner_card_bg,
            hover_color=THEME.card_border,
            font=ctk.CTkFont(size=11),
            command=self._copy_preview_content
        )
        copy_btn.pack(side="left", padx=(0, 8))

        clear_btn = ctk.CTkButton(
            tools,
            text="🗑️ Temizle",
            width=80,
            height=30,
            corner_radius=6,
            fg_color=THEME.inner_card_bg,
            hover_color=THEME.card_border,
            font=ctk.CTkFont(size=11),
            command=self._clear_preview
        )
        clear_btn.pack(side="left")

        self.preview_text = ctk.CTkTextbox(
            right_panel,
            font=ctk.CTkFont(size=12, family="Consolas"),
            fg_color=THEME.inner_card_bg,
            border_width=1,
            border_color=THEME.card_border,
            corner_radius=8,
            wrap="word",
            state="disabled"
        )
        self.preview_text.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        self._lock_textbox_readonly(self.preview_text)

    def _copy_preview_content(self):
        content = self.preview_text.get("1.0", "end-1c")
        if content:
            self.clipboard_clear()
            self.clipboard_append(content)
            messagebox.showinfo("Kopyalandı", "Canlı çeviri metni panoya kopyalandı!")

    # ==========================================
    # SEKME 2: ÖZEL TERİM SÖZLÜĞÜ (GLOSSARY)
    # ==========================================
    def _create_glossary_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.content_area, fg_color=THEME.bg_dark, corner_radius=0)

        header = ctk.CTkFrame(view, height=64, fg_color=THEME.sidebar_bg, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=24)

        title_box = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_box.pack(side="left", fill="y", pady=12)

        ctk.CTkLabel(
            title_box,
            text="Özel Akademik Terim Sözlüğü (Glossary)",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME.text_primary
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Çeviri modelinin kesinlikle uymasını istediğiniz teknik terim çiftlerini tanımlayın.",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_muted
        ).pack(anchor="w")

        body = ctk.CTkFrame(view, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=18)

        # Sol Panel: Terim Ekleme Kartı
        add_card = ctk.CTkFrame(
            body,
            width=360,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        add_card.pack(side="left", fill="y", padx=(0, 16))
        add_card.pack_propagate(False)

        ctk.CTkLabel(
            add_card,
            text="Yeni Terim Tanımla",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME.text_primary
        ).pack(anchor="w", padx=16, pady=(16, 12))

        ctk.CTkLabel(add_card, text="İngilizce Orijinal Terim:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME.text_secondary).pack(anchor="w", padx=16, pady=(0, 4))
        self.glossary_en_entry = ctk.CTkEntry(add_card, placeholder_text="Örn: reinforcement learning", height=36, corner_radius=8, fg_color=THEME.inner_card_bg, border_color=THEME.card_border)
        self.glossary_en_entry.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(add_card, text="Türkçe Karşılığı:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME.text_secondary).pack(anchor="w", padx=16, pady=(0, 4))
        self.glossary_tr_entry = ctk.CTkEntry(add_card, placeholder_text="Örn: pekiştirmeli öğrenme", height=36, corner_radius=8, fg_color=THEME.inner_card_bg, border_color=THEME.card_border)
        self.glossary_tr_entry.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(add_card, text="Kategori / Alan:", font=ctk.CTkFont(size=11, weight="bold"), text_color=THEME.text_secondary).pack(anchor="w", padx=16, pady=(0, 4))
        self.glossary_cat_entry = ctk.CTkEntry(add_card, placeholder_text="Örn: Yapay Zeka / Tıp / Hukuk", height=36, corner_radius=8, fg_color=THEME.inner_card_bg, border_color=THEME.card_border)
        self.glossary_cat_entry.pack(fill="x", padx=16, pady=(0, 14))
        self.glossary_cat_entry.insert(0, "Genel")

        add_btn = ctk.CTkButton(
            add_card,
            text="➕  Terimi Kaydet",
            height=38,
            corner_radius=8,
            fg_color=THEME.primary,
            hover_color=THEME.primary_hover,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._glossary_add_term
        )
        add_btn.pack(fill="x", padx=16, pady=(0, 12))

        # Sağ Panel: Kayıtlı Terimler Listesi
        list_card = ctk.CTkFrame(
            body,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        list_card.pack(side="left", fill="both", expand=True)

        list_head = ctk.CTkFrame(list_card, fg_color="transparent")
        list_head.pack(fill="x", padx=18, pady=(16, 10))

        self.glossary_count_lbl = ctk.CTkLabel(
            list_head,
            text="Kayıtlı Terimler (0)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME.text_primary
        )
        self.glossary_count_lbl.pack(side="left")

        self.glossary_scrollable = ctk.CTkScrollableFrame(list_card, fg_color="transparent")
        self.glossary_scrollable.pack(fill="both", expand=True, padx=12, pady=(0, 14))

        return view

    def _glossary_refresh_list(self):
        terms = database.get_all_glossary_terms()
        self.glossary_count_lbl.configure(text=f"Kayıtlı Terimler ({len(terms)})")

        for widget in self.glossary_scrollable.winfo_children():
            widget.destroy()

        if not terms:
            ctk.CTkLabel(
                self.glossary_scrollable,
                text="Henüz kayıtlı bir sözlük terimi yok.\nSol panelden ekleyebilirsiniz.",
                text_color=THEME.text_muted
            ).pack(pady=40)
            return

        for t in terms:
            row = ctk.CTkFrame(
                self.glossary_scrollable,
                fg_color=THEME.inner_card_bg,
                corner_radius=8,
                border_width=1,
                border_color=THEME.card_border
            )
            row.pack(fill="x", pady=3, padx=2)

            info_box = ctk.CTkFrame(row, fg_color="transparent")
            info_box.pack(side="left", fill="both", expand=True, padx=10, pady=8)

            txt = f"🇬🇧 {t['term_en']}  ➔  🇹🇷 {t['term_tr']}"
            ctk.CTkLabel(
                info_box,
                text=txt,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=THEME.text_primary,
                anchor="w"
            ).pack(fill="x")

            ctk.CTkLabel(
                info_box,
                text=f"Kategori: {t.get('category', 'Genel')}",
                font=ctk.CTkFont(size=10),
                text_color=THEME.text_muted,
                anchor="w"
            ).pack(fill="x")

            del_btn = ctk.CTkButton(
                row,
                text="Sil",
                width=55,
                height=26,
                corner_radius=6,
                fg_color=THEME.danger,
                hover_color=THEME.danger_hover,
                font=ctk.CTkFont(size=11),
                command=lambda tid=t["id"]: self._glossary_delete_term(tid)
            )
            del_btn.pack(side="right", padx=10)

    def _glossary_add_term(self):
        en = self.glossary_en_entry.get().strip()
        tr = self.glossary_tr_entry.get().strip()
        cat = self.glossary_cat_entry.get().strip() or "Genel"

        if not en or not tr:
            messagebox.showwarning("Uyarı", "Lütfen hem İngilizce hem Türkçe terimi doldurun.")
            return

        success = database.add_glossary_term(en, tr, cat)
        if success:
            self.glossary_en_entry.delete(0, "end")
            self.glossary_tr_entry.delete(0, "end")
            self._glossary_refresh_list()
        else:
            messagebox.showerror("Hata", "Terim kaydedilemedi.")

    def _glossary_delete_term(self, term_id: int):
        database.delete_glossary_term(term_id)
        self._glossary_refresh_list()

    # ==========================================
    # SEKME 3: ÇEVİRİ ARŞİVİ
    # ==========================================
    def _create_archive_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.content_area, fg_color=THEME.bg_dark, corner_radius=0)

        header = ctk.CTkFrame(view, height=64, fg_color=THEME.sidebar_bg, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=24)

        title_box = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_box.pack(side="left", fill="y", pady=12)

        ctk.CTkLabel(
            title_box,
            text="Çeviri Arşivi ve Doküman Geçmişi",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME.text_primary
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Veritabanında kayıtlı önceki çevirilerinizi inceleyin, dışa aktarın veya yönetin.",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_muted
        ).pack(anchor="w")

        right_header = ctk.CTkFrame(header_inner, fg_color="transparent")
        right_header.pack(side="right", fill="y", pady=14)

        self.archive_search = ctk.CTkEntry(
            right_header,
            placeholder_text="Arşivde ara...",
            width=220,
            height=34,
            corner_radius=8,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.archive_search.pack(side="left", padx=(0, 10))
        self.archive_search.bind("<KeyRelease>", lambda e: self._archive_filter_list())

        refresh_btn = ctk.CTkButton(
            right_header,
            text="🔄 Yenile",
            width=90,
            height=34,
            corner_radius=8,
            fg_color=THEME.card_bg,
            hover_color=THEME.card_border,
            border_width=1,
            border_color=THEME.card_border,
            command=self._archive_refresh_list
        )
        refresh_btn.pack(side="left")

        body = ctk.CTkFrame(view, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=18)

        left_card = ctk.CTkFrame(
            body,
            width=360,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        left_card.pack(side="left", fill="y", padx=(0, 16))
        left_card.pack_propagate(False)

        ctk.CTkLabel(
            left_card,
            text="Kayıtlı Belgeler",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=THEME.text_secondary
        ).pack(anchor="w", padx=16, pady=(14, 8))

        self.archive_scrollable = ctk.CTkScrollableFrame(left_card, fg_color="transparent")
        self.archive_scrollable.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        right_card = ctk.CTkFrame(
            body,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        right_card.pack(side="left", fill="both", expand=True)

        detail_bar = ctk.CTkFrame(right_card, fg_color="transparent")
        detail_bar.pack(fill="x", padx=18, pady=(14, 10))

        self.archive_detail_title = ctk.CTkLabel(
            detail_bar,
            text="Lütfen listeden bir belge seçin.",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=THEME.text_primary,
            anchor="w"
        )
        self.archive_detail_title.pack(fill="x")

        self.archive_detail_info = ctk.CTkLabel(
            detail_bar,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_secondary,
            anchor="w"
        )
        self.archive_detail_info.pack(fill="x", pady=(2, 0))

        self.archive_preview = ctk.CTkTextbox(
            right_card,
            font=ctk.CTkFont(size=12, family="Consolas"),
            fg_color=THEME.inner_card_bg,
            border_width=1,
            border_color=THEME.card_border,
            corner_radius=8,
            wrap="word",
            state="disabled"
        )
        self.archive_preview.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self._lock_textbox_readonly(self.archive_preview)

        actions_bar = ctk.CTkFrame(right_card, fg_color="transparent")
        actions_bar.pack(fill="x", padx=18, pady=(0, 16))

        self.archive_export_btn = ctk.CTkButton(
            actions_bar,
            text="📄 Word Olarak Dışa Aktar (.docx)",
            height=38,
            corner_radius=8,
            fg_color=THEME.success,
            hover_color=THEME.success_hover,
            font=ctk.CTkFont(size=13, weight="bold"),
            state="disabled",
            command=self._archive_export_selected
        )
        self.archive_export_btn.pack(side="left", padx=(0, 10))

        self.archive_delete_btn = ctk.CTkButton(
            actions_bar,
            text="🗑️ Kayıtları Sil",
            height=38,
            corner_radius=8,
            fg_color=THEME.danger,
            hover_color=THEME.danger_hover,
            font=ctk.CTkFont(size=12),
            state="disabled",
            command=self._archive_delete_selected
        )
        self.archive_delete_btn.pack(side="left")

        return view

    def _archive_refresh_list(self):
        self.cached_history = database.get_history_summary()
        self._archive_render_items(self.cached_history)

    def _archive_filter_list(self):
        query = self.archive_search.get().strip().lower()
        if not query:
            self._archive_render_items(self.cached_history)
        else:
            filtered = [item for item in self.cached_history if query in item["file_name"].lower()]
            self._archive_render_items(filtered)

    def _archive_render_items(self, items):
        for widget in self.archive_scrollable.winfo_children():
            widget.destroy()

        if not items:
            ctk.CTkLabel(
                self.archive_scrollable,
                text="Henüz kaydedilmiş bir çeviri yok.",
                text_color=THEME.text_muted
            ).pack(pady=40)
            self._archive_select_file(None)
            return

        for item in items:
            fname = item["file_name"]
            total = item["total_paragraphs"]
            date_str = str(item.get("last_updated", "")).split(".")[0]

            is_selected = (fname == self.archive_selected_file)
            bg_col = THEME.nav_active_bg if is_selected else THEME.inner_card_bg

            btn_frame = ctk.CTkFrame(
                self.archive_scrollable,
                fg_color=bg_col,
                corner_radius=8,
                border_width=1,
                border_color=THEME.primary if is_selected else THEME.card_border
            )
            btn_frame.pack(fill="x", pady=4, padx=2)

            file_btn = ctk.CTkButton(
                btn_frame,
                text=f"📄 {fname}\n{total} Paragraf • {date_str}",
                anchor="w",
                fg_color="transparent",
                hover_color=THEME.card_border,
                text_color=THEME.text_primary,
                font=ctk.CTkFont(size=12),
                command=lambda f=fname: self._archive_select_file(f)
            )
            file_btn.pack(fill="both", expand=True, padx=6, pady=6)

        if not self.archive_selected_file and items:
            self._archive_select_file(items[0]["file_name"])

    def _archive_select_file(self, file_name: Optional[str]):
        self.archive_selected_file = file_name
        self.archive_preview.configure(state="normal")
        self.archive_preview.delete("1.0", "end")

        if not file_name:
            self.archive_detail_title.configure(text="Seçili belge yok.")
            self.archive_detail_info.configure(text="")
            self.archive_export_btn.configure(state="disabled")
            self.archive_delete_btn.configure(state="disabled")
            self.archive_preview.configure(state="disabled")
            return

        self.archive_export_btn.configure(state="normal")
        self.archive_delete_btn.configure(state="normal")
        self.archive_detail_title.configure(text=f"📄 {file_name}")

        records = database.get_translations_by_file(file_name)
        count = len(records)
        self.archive_detail_info.configure(text=f"Toplam {count} adet çevrilmiş paragraf kayıtlı.")

        for i, r in enumerate(records, 1):
            src = r["source_paragraph"]
            tr = r["translated_paragraph"]
            imgs = r.get("image_paths", [])
            img_note = f" (Şekil/Görsel: {len(imgs)})" if imgs else ""

            self.archive_preview.insert("end", f"┌── [Paragraf #{i}{img_note}] {'─'*45}\n")
            self.archive_preview.insert("end", f"│ EN: {src}\n")
            self.archive_preview.insert("end", f"│ TR: {tr}\n")
            self.archive_preview.insert("end", f"└──{'─'*60}\n\n")

        self.archive_preview.configure(state="disabled")

    def _archive_export_selected(self):
        if not self.archive_selected_file:
            return

        records = database.get_translations_by_file(self.archive_selected_file)
        if not records:
            messagebox.showwarning("Uyarı", "Bu dosya için çeviri kaydı bulunamadı.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Word Dosyası Olarak Kaydet",
            defaultextension=".docx",
            initialfile=f"{os.path.splitext(self.archive_selected_file)[0]}_Ceviri.docx",
            filetypes=[("Word Dokümanı", "*.docx")]
        )
        if not out_path:
            return

        pairs = [{
            "source": r["source_paragraph"],
            "translated": r["translated_paragraph"],
            "images": r.get("image_paths", [])
        } for r in records]

        try:
            doc_exporter.export_bilingual_docx(
                translation_pairs=pairs,
                output_path=out_path,
                original_filename=self.archive_selected_file,
                model_name="Arşiv Kaydı"
            )
            msg = f"Word dokümanı başarıyla dışa aktarıldı:\n{out_path}\n\nDosyayı şimdi açmak ister misiniz?"
            if messagebox.askyesno("Dışa Aktarma Başarılı", msg):
                open_file_or_folder(out_path)
        except Exception as e:
            messagebox.showerror("Hata", f"Word belgesi oluşturulurken hata çıktı:\n{str(e)}")

    def _archive_delete_selected(self):
        if not self.archive_selected_file:
            return

        confirm = messagebox.askyesno(
            "Kayıtları Sil",
            f"'{self.archive_selected_file}' dosyasına ait tüm çeviri kayıtları silinecek.\nEmin misiniz?"
        )
        if confirm:
            database.clear_translations_for_file(self.archive_selected_file)
            self._archive_refresh_list()

    # ==========================================
    # SEKME 4: MODEL VE API YAPILANDIRMASI
    # ==========================================
    def _create_settings_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.content_area, fg_color=THEME.bg_dark, corner_radius=0)

        header = ctk.CTkFrame(view, height=64, fg_color=THEME.sidebar_bg, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=24)

        title_box = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_box.pack(side="left", fill="y", pady=12)

        ctk.CTkLabel(
            title_box,
            text="Model ve API Yapılandırması (BYOK)",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME.text_primary
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="Kendi API anahtarınızı (Bring Your Own Key) tanımlayın ve dilediğiniz LLM modelini seçin.",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_muted
        ).pack(anchor="w")

        body = ctk.CTkScrollableFrame(view, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=18)

        # Kart: Sağlayıcı ve Model
        card1 = ctk.CTkFrame(
            body,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        card1.pack(fill="x", pady=(0, 16))

        c1_head = ctk.CTkFrame(card1, fg_color="transparent")
        c1_head.pack(fill="x", padx=20, pady=(16, 12))

        ctk.CTkLabel(
            c1_head,
            text="Yapay Zeka Sağlayıcısı ve Model Seçimi",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME.text_primary
        ).pack(anchor="w")

        c1_content = ctk.CTkFrame(card1, fg_color="transparent")
        c1_content.pack(fill="x", padx=20, pady=(0, 18))

        ctk.CTkLabel(c1_content, text="Sağlayıcı:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME.text_secondary).pack(anchor="w", pady=(0, 4))
        self.provider_combo = ctk.CTkComboBox(
            c1_content,
            values=["Google Gemini", "OpenAI Uyumlu / Özel"],
            command=self._on_provider_change,
            height=38,
            corner_radius=8,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.provider_combo.pack(fill="x", pady=(0, 14))

        ctk.CTkLabel(c1_content, text="Model Adı:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME.text_secondary).pack(anchor="w", pady=(0, 4))
        self.model_combo = ctk.CTkComboBox(
            c1_content,
            values=[
                "gemini-flash-lite-latest",
                "gemini-flash-latest",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "Özel Model...",
            ],
            command=self._on_model_change,
            height=38,
            corner_radius=8,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.model_combo.pack(fill="x", pady=(0, 10))

        self.custom_model_frame = ctk.CTkFrame(c1_content, fg_color="transparent")
        ctk.CTkLabel(self.custom_model_frame, text="Özel Model Adı:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME.text_secondary).pack(anchor="w", pady=(0, 4))
        self.custom_model_entry = ctk.CTkEntry(
            self.custom_model_frame,
            placeholder_text="Örn: gemini-3.8-pro veya gpt-4o",
            height=38,
            corner_radius=8,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.custom_model_entry.pack(fill="x", pady=(0, 10))

        self.base_url_frame = ctk.CTkFrame(c1_content, fg_color="transparent")
        ctk.CTkLabel(self.base_url_frame, text="Base URL (OpenAI Uyumlu Uç Nokta):", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME.text_secondary).pack(anchor="w", pady=(0, 4))
        self.base_url_entry = ctk.CTkEntry(
            self.base_url_frame,
            placeholder_text="Örn: https://api.deepseek.com/v1 veya https://api.groq.com/openai/v1",
            height=38,
            corner_radius=8,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.base_url_entry.pack(fill="x", pady=(0, 10))

        # Kart 2: API Anahtarı ve Doğrulama
        card2 = ctk.CTkFrame(
            body,
            fg_color=THEME.card_bg,
            corner_radius=12,
            border_width=1,
            border_color=THEME.card_border
        )
        card2.pack(fill="x", pady=(0, 16))

        c2_head = ctk.CTkFrame(card2, fg_color="transparent")
        c2_head.pack(fill="x", padx=20, pady=(16, 12))

        ctk.CTkLabel(
            c2_head,
            text="API Anahtarı ve Güvenlik",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=THEME.text_primary
        ).pack(anchor="w")

        c2_content = ctk.CTkFrame(card2, fg_color="transparent")
        c2_content.pack(fill="x", padx=20, pady=(0, 18))

        ctk.CTkLabel(c2_content, text="API Key:", font=ctk.CTkFont(size=12, weight="bold"), text_color=THEME.text_secondary).pack(anchor="w", pady=(0, 4))

        key_row = ctk.CTkFrame(c2_content, fg_color="transparent")
        key_row.pack(fill="x", pady=(0, 12))

        self.api_key_entry = ctk.CTkEntry(
            key_row,
            placeholder_text="Google AI Studio veya OpenAI API Anahtarınızı yapıştırın...",
            show="*",
            height=38,
            corner_radius=8,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.api_key_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.show_key_btn = ctk.CTkButton(
            key_row,
            text="Göster",
            width=70,
            height=38,
            corner_radius=8,
            fg_color=THEME.inner_card_bg,
            hover_color=THEME.card_border,
            command=self._toggle_show_api_key
        )
        self.show_key_btn.pack(side="left")

        action_row = ctk.CTkFrame(c2_content, fg_color="transparent")
        action_row.pack(fill="x", pady=(4, 8))

        self.test_btn = ctk.CTkButton(
            action_row,
            text="🔍  Bağlantıyı Doğrula & Test Et",
            height=38,
            corner_radius=8,
            fg_color=THEME.inner_card_bg,
            hover_color=THEME.card_border,
            border_width=1,
            border_color=THEME.card_border,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._test_connection_threaded
        )
        self.test_btn.pack(side="left", padx=(0, 12))

        self.save_settings_btn = ctk.CTkButton(
            action_row,
            text="💾  Ayarları Kaydet",
            height=38,
            corner_radius=8,
            fg_color=THEME.primary,
            hover_color=THEME.primary_hover,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._save_settings
        )
        self.save_settings_btn.pack(side="left")

        # Önbellek Yönetim Butonu
        clear_cache_btn = ctk.CTkButton(
            action_row,
            text="🗑️ Önbelleği Temizle",
            height=38,
            corner_radius=8,
            fg_color=THEME.card_border,
            hover_color=THEME.danger,
            font=ctk.CTkFont(size=11),
            command=self._clear_cache_action
        )
        clear_cache_btn.pack(side="right")

        self.test_status_label = ctk.CTkLabel(
            c2_content,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_secondary,
            anchor="w"
        )
        self.test_status_label.pack(fill="x", pady=(6, 0))

        return view

    def _clear_cache_action(self):
        cnt = database.get_cache_count()
        if messagebox.askyesno("Önbelleği Temizle", f"Önbellekte kayıtlı {cnt} adet paragraf silinecek. Emin misiniz?"):
            database.clear_cache()
            messagebox.showinfo("Başarılı", "Çeviri önbelleği temizlendi.")

    # ==========================================
    # SEKME 5: KILAVUZ VE ÖZELLİKLER
    # ==========================================
    def _create_guide_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.content_area, fg_color=THEME.bg_dark, corner_radius=0)

        header = ctk.CTkFrame(view, height=64, fg_color=THEME.sidebar_bg, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_inner = ctk.CTkFrame(header, fg_color="transparent")
        header_inner.pack(fill="both", expand=True, padx=24)

        title_box = ctk.CTkFrame(header_inner, fg_color="transparent")
        title_box.pack(side="left", fill="y", pady=12)

        ctk.CTkLabel(
            title_box,
            text="Kullanım Kılavuzu & Gelişmiş Özellikler",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME.text_primary
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text="TranslAI Studio'nun arkasındaki mimari, hız ve verimlilik mekanizmaları.",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_muted
        ).pack(anchor="w")

        body = ctk.CTkScrollableFrame(view, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24, pady=18)

        guide_cards = [
            (
                "⚡ Eşzamanlı & Çok İş Parçacıklı Çeviri (Parallel Worker)",
                "Uygulama, seçtiğiniz hız moduna göre (1x, 2x, 3x, 4x) paragrafları eşzamanlı olarak LLM API'sine gönderir. Bu sayede 30 sayfalık bir makalenin çeviri süresi 4 katına kadar hızlanır."
            ),
            (
                "📑 Esnek Sayfa Aralığı Filtresi (Page Range)",
                "Makalenin sadece istediğiniz sayfalarını ('1-5', '3, 7-10' veya 'Tümü') çevirebilirsiniz. Böylece kaynakça ve gereksiz sayfalar için API kotası harcanmaz."
            ),
            (
                "🗄️ SHA-256 Paragraf Düzeyinde Yerel Önbellekleme (Cache)",
                "Daha önce çevrilmiş bir paragraf veya cümle algılandığında tekrar API çağrısı yapılmaz. Doğrudan yerel veritabanından 0 milisaniyede yüklenir."
            ),
            (
                "📖 Özel Akademik Terim Sözlüğü (Custom Glossary)",
                "Tıp, Hukuk, Mühendislik gibi alanlara özel terimler tanımlayarak modelin bu kavramları her zaman sizin belirlediğiniz Türkçe karşılığıyla çevirmesini sağlayabilirsiniz."
            ),
            (
                "🖼️ Akıllı Görsel İçi Çeviri (Figure Translation)",
                "PDF içindeki grafik ve diyagramlar kırpılır, içlerindeki İngilizce etiketler AI ile algılanıp Türkçe olarak görsel üzerine yeniden işlenir ve doğrudan Word belgesine gömülür."
            ),
            (
                "🛡️ Kesintisiz Fail-Safe SQLite Mimarisi",
                "Çeviri işlemi sırasında internet kopsa veya program kapatılsa bile çevrilen hiçbir paragraf kaybolmaz. Belgeyi yeniden açtığınızda 'Kaldığı Yerden Devam Et' butonu otomatik belirir."
            )
        ]

        for title, desc in guide_cards:
            card = ctk.CTkFrame(
                body,
                fg_color=THEME.card_bg,
                corner_radius=12,
                border_width=1,
                border_color=THEME.card_border
            )
            card.pack(fill="x", pady=(0, 14))

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=20, pady=16)

            ctk.CTkLabel(
                inner,
                text=title,
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=THEME.text_accent
            ).pack(anchor="w", pady=(0, 6))

            ctk.CTkLabel(
                inner,
                text=desc,
                font=ctk.CTkFont(size=12),
                text_color=THEME.text_secondary,
                wraplength=760,
                justify="left"
            ).pack(anchor="w")

        return view

    # ==========================================
    # İŞ MANTIĞI: AYARLAR VE ETKİLEŞİM
    # ==========================================
    def _lock_textbox_readonly(self, textbox_widget: ctk.CTkTextbox):
        textbox_widget.configure(state="disabled")
        def on_key(event):
            if (event.state & 0x4) and event.keysym.lower() in ('c', 'a'):
                return None
            if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End'):
                return None
            return "break"
        if hasattr(textbox_widget, "_textbox"):
            textbox_widget._textbox.bind("<Key>", on_key)

    def _toggle_show_api_key(self):
        if self.api_key_entry.cget("show") == "*":
            self.api_key_entry.configure(show="")
            self.show_key_btn.configure(text="Gizle")
        else:
            self.api_key_entry.configure(show="*")
            self.show_key_btn.configure(text="Göster")

    def _on_provider_change(self, choice: str):
        if choice == "Google Gemini":
            self.base_url_frame.pack_forget()
            self.model_combo.configure(values=[
                "gemini-flash-lite-latest",
                "gemini-flash-latest",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "Özel Model...",
            ])
            self.model_combo.set("gemini-flash-lite-latest")
            self._on_model_change("gemini-flash-lite-latest")
        else:
            self.base_url_frame.pack(fill="x", pady=(0, 10))
            self.model_combo.configure(values=[
                "gpt-4o-mini",
                "deepseek-chat",
                "llama-3.3-70b-versatile",
                "Özel Model...",
            ])
            self.model_combo.set("deepseek-chat")
            self._on_model_change("deepseek-chat")

    def _on_model_change(self, choice: str):
        if choice == "Özel Model...":
            self.custom_model_frame.pack(fill="x", pady=(0, 10))
        else:
            self.custom_model_frame.pack_forget()

        model_name = self.custom_model_entry.get().strip() if choice == "Özel Model..." else choice
        self.current_model_tag.configure(text=model_name)
        self.sidebar_model_status.configure(text=f"Model: {model_name}")

    def _get_current_settings(self) -> Dict[str, Any]:
        provider_val = "gemini" if self.provider_combo.get() == "Google Gemini" else "openai_compatible"
        model_choice = self.model_combo.get()
        if model_choice == "Özel Model...":
            model_name = self.custom_model_entry.get().strip() or "gemini-2.5-flash"
        else:
            model_name = model_choice

        # Eşzamanlı işçi sayısı
        conc_choice = self.concurrency_combo.get()
        workers = 1
        if "2x" in conc_choice:
            workers = 2
        elif "3x" in conc_choice:
            workers = 3
        elif "4x" in conc_choice:
            workers = 4

        return {
            "provider": provider_val,
            "api_key": self.api_key_entry.get().strip(),
            "model_name": model_name,
            "base_url": self.base_url_entry.get().strip(),
            "translate_images": self.translate_images_switch.get() == 1,
            "workers": workers,
        }

    def _update_api_badge(self):
        settings = self._get_current_settings()
        if settings["api_key"]:
            m_name = settings["model_name"]
            prov = "Gemini" if settings["provider"] == "gemini" else "OpenAI/Özel"
            self.sidebar_api_status.configure(
                text=f"● {prov} Bağlı",
                text_color=THEME.success
            )
            self.sidebar_model_status.configure(text=f"Model: {m_name}")
            self.top_status_badge.configure(
                text="Hazır",
                fg_color=THEME.card_bg,
                text_color=THEME.accent
            )
        else:
            self.sidebar_api_status.configure(
                text="● API Anahtarı Gerekli",
                text_color=THEME.warning
            )
            self.sidebar_model_status.configure(text="Model: -")
            self.top_status_badge.configure(
                text="API Gerekli",
                fg_color=THEME.warning_bg,
                text_color=THEME.warning
            )

    def _save_settings(self):
        settings = self._get_current_settings()
        database.set_setting("provider", settings["provider"])
        database.set_setting("api_key", settings["api_key"])
        database.set_setting("model_name", settings["model_name"])
        database.set_setting("base_url", settings["base_url"])
        database.set_setting("translate_images", "1" if settings.get("translate_images") else "0")

        self.current_model_tag.configure(text=settings["model_name"])
        self._update_api_badge()
        self.test_status_label.configure(
            text="✓ Ayarlar başarıyla kaydedildi.",
            text_color=THEME.success
        )

    def _load_saved_settings(self):
        provider = database.get_setting("provider", default="gemini")
        api_key = database.get_setting("api_key", default="")
        model_name = database.get_setting("model_name", default="gemini-flash-latest")
        base_url = database.get_setting("base_url", default="")
        translate_img_val = database.get_setting("translate_images", default="1")

        if translate_img_val == "1":
            self.translate_images_switch.select()
        else:
            self.translate_images_switch.deselect()

        if provider == "gemini":
            self.provider_combo.set("Google Gemini")
            self._on_provider_change("Google Gemini")
        else:
            self.provider_combo.set("OpenAI Uyumlu / Özel")
            self._on_provider_change("OpenAI Uyumlu / Özel")

        if api_key:
            self.api_key_entry.delete(0, "end")
            self.api_key_entry.insert(0, api_key)

        if base_url:
            self.base_url_entry.delete(0, "end")
            self.base_url_entry.insert(0, base_url)

        if model_name in self.model_combo.cget("values"):
            self.model_combo.set(model_name)
        else:
            self.model_combo.set("Özel Model...")
            self._on_model_change("Özel Model...")
            self.custom_model_entry.delete(0, "end")
            self.custom_model_entry.insert(0, model_name)

        self.current_model_tag.configure(text=model_name)
        self._update_api_badge()

    def _test_connection_threaded(self):
        settings = self._get_current_settings()
        if not settings["api_key"]:
            messagebox.showwarning("Uyarı", "Lütfen önce bir API anahtarı girin.")
            return

        self.test_btn.configure(state="disabled")
        self.test_status_label.configure(text="Bağlantı test ediliyor...", text_color=THEME.warning)

        def run_test():
            success, msg = translator.test_api_credentials(
                provider=settings["provider"],
                api_key=settings["api_key"],
                model_name=settings["model_name"],
                base_url=settings["base_url"]
            )
            self.after(0, lambda: self._on_test_finished(success, msg))

        threading.Thread(target=run_test, daemon=True).start()

    def _on_test_finished(self, success: bool, msg: str):
        self.test_btn.configure(state="normal")
        if success:
            self.test_status_label.configure(text="✓ Bağlantı başarılı! Model yanıt verdi.", text_color=THEME.success)
            self._save_settings()
        else:
            self.test_status_label.configure(text=f"✗ {msg}", text_color=THEME.danger)

    # ==========================================
    # DOSYA SEÇİMİ VE ANALİZİ
    # ==========================================
    def _select_pdf_file(self):
        file_path = filedialog.askopenfilename(
            title="Akademik PDF Makalesi Seç",
            filetypes=[("PDF Dosyaları", "*.pdf"), ("Tüm Dosyalar", "*.*")]
        )
        if not file_path:
            return

        self.selected_pdf_path = file_path
        self.total_pdf_pages = pdf_parser.get_pdf_page_count(file_path)
        file_name = os.path.basename(file_path)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)

        self.file_name_label.configure(
            text=f"📄 {file_name} ({file_size_mb:.2f} MB, {self.total_pdf_pages} Sayfa)",
            text_color=THEME.text_primary
        )

        try:
            root_dir = get_app_dir()
            cevrilen_dir = os.path.join(root_dir, "çevrilen")
            os.makedirs(cevrilen_dir, exist_ok=True)
            target_path = os.path.join(cevrilen_dir, file_name)
            if os.path.abspath(file_path) != os.path.abspath(target_path) and not os.path.exists(target_path):
                import shutil
                shutil.copy2(file_path, target_path)
        except Exception:
            pass

        self._parse_selected_pdf()

    def _on_page_range_changed(self):
        if self.selected_pdf_path:
            self._parse_selected_pdf()

    def _parse_selected_pdf(self):
        if not self.selected_pdf_path:
            return

        self.actions_row.pack_forget()
        self.file_info_badge.configure(text="PDF analiz ediliyor ve sayfalar ayrıştırılıyor...", text_color=THEME.warning)
        self.resume_btn.pack_forget()

        range_str = self.page_range_entry.get().strip()
        file_path = self.selected_pdf_path
        file_name = os.path.basename(file_path)

        def parse_worker():
            try:
                chunks = pdf_parser.extract_paragraphs_from_pdf(
                    file_path,
                    page_range_str=range_str
                )
                self.parsed_paragraphs = chunks
                existing = database.get_translations_by_file(file_name)
                existing_count = len(existing)
                self.after(0, lambda: self._on_parse_finished(chunks, existing_count, file_name, range_str))
            except Exception as e:
                logger.error(f"PDF okuma hatası: {e}")
                self.after(0, lambda: messagebox.showerror("PDF Hatası", f"PDF okunamadı:\n{str(e)}"))

        threading.Thread(target=parse_worker, daemon=True).start()

    def _on_parse_finished(self, chunks: List[Any], existing_count: int, file_name: str, range_str: str):
        total_chunks = len(chunks)

        if total_chunks == 0:
            self.file_info_badge.configure(
                text="⚠️ Bu sayfa aralığında metin tespit edilemedi.",
                text_color=THEME.danger
            )
            self.resume_btn.pack_forget()
            return

        is_vision = bool(chunks and isinstance(chunks[0], dict) and chunks[0].get("is_vision"))
        page_info = f"[{range_str}]" if range_str and range_str.lower() not in ["tümü", "all"] else f"[{self.total_pdf_pages} Sayfa]"

        if is_vision:
            info_text = f"✨ Akıllı Vision OCR Modu {page_info}: {total_chunks} sayfa çeviriye hazır."
            if existing_count > 0:
                info_text += f"\n(Veritabanında {existing_count} kayıt mevcut)"
                self.file_info_badge.configure(text=info_text, text_color=THEME.accent)
                self.resume_btn.pack(fill="x", pady=(6, 0))
            else:
                self.file_info_badge.configure(text=info_text, text_color=THEME.accent)
                self.resume_btn.pack_forget()
        else:
            info_text = f"✓ {page_info}: {total_chunks} adet akademik paragraf tespit edildi."
            if existing_count > 0:
                info_text += f"\n(Veritabanında önceden kayıtlı {existing_count} çeviri bulundu!)"
                self.file_info_badge.configure(text=info_text, text_color=THEME.warning)
                self.resume_btn.pack(fill="x", pady=(6, 0))
            else:
                self.file_info_badge.configure(text=info_text, text_color=THEME.success)
                self.resume_btn.pack_forget()

        self.metric_count_lbl.configure(text=f"0 / {total_chunks}")

    def _resume_existing_translation(self):
        self._start_translation_threaded(resume=True)

    # ==========================================
    # ÇEVİRİ MOTORU VE PARALEL İŞ PARÇACIKLARI
    # ==========================================
    def _start_translation_threaded(self, resume: bool = False):
        if not self.selected_pdf_path:
            messagebox.showwarning("Uyarı", "Lütfen önce bir PDF dosyası seçin.")
            return

        if not self.parsed_paragraphs:
            messagebox.showwarning("Metin Bulunamadı", "Seçilen sayfada çevrilebilecek metin paragrafı bulunamadı.")
            return

        settings = self._get_current_settings()
        if not settings["api_key"]:
            messagebox.showwarning("Uyarı", "Lütfen Ayarlar sekmesinden API anahtarınızı girin.")
            self._navigate_to("settings")
            return

        self._save_settings()

        self.is_translating = True
        self.cancel_requested = False

        self.start_btn.configure(state="disabled")
        self.resume_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal", fg_color=THEME.danger, text_color="white")
        self.actions_row.pack_forget()

        self.top_status_badge.configure(
            text="Çevriliyor...",
            fg_color=THEME.primary,
            text_color="white"
        )

        threading.Thread(target=self._run_translation_worker, args=(settings, resume), daemon=True).start()

    def _cancel_translation(self):
        if self.is_translating:
            self.cancel_requested = True
            self.status_label.configure(text="Durum: İptal ediliyor... Lütfen bekleyin.")

    def _run_translation_worker(self, settings: Dict[str, Any], resume: bool):
        file_name = os.path.basename(self.selected_pdf_path)
        total_chunks = len(self.parsed_paragraphs)
        workers_count = settings.get("workers", 3)

        engine = translator.TranslationEngine(
            provider=settings["provider"],
            api_key=settings["api_key"],
            model_name=settings["model_name"],
            base_url=settings["base_url"]
        )

        existing_records = []
        if resume:
            existing_records = database.get_translations_by_file(file_name)
        else:
            database.clear_translations_for_file(file_name)

        already_translated_count = len(existing_records)
        completed_pairs = [{
            "source": r["source_paragraph"],
            "translated": r["translated_paragraph"],
            "images": r.get("image_paths", [])
        } for r in existing_records]

        if already_translated_count > 0:
            self.after(0, lambda: self._append_preview(f"── Önceki {already_translated_count} çeviri veritabanından yüklendi ──\n\n"))

        start_time = time.time()
        start_index = already_translated_count
        is_vision_mode = bool(self.parsed_paragraphs and isinstance(self.parsed_paragraphs[0], dict) and self.parsed_paragraphs[0].get("is_vision"))
        should_translate_images = bool(settings.get("translate_images", True))

        if is_vision_mode:
            # AI Vision Modu (Sayfa Görseli Çevirisi)
            for idx in range(start_index, total_chunks):
                if self.cancel_requested:
                    self.after(0, lambda: self._on_translation_interrupted("Çeviri durduruldu."))
                    return

                page_item = self.parsed_paragraphs[idx]
                page_img = page_item.get("page_image") or page_item.get("images", [""])[0]
                current_num = idx + 1

                progress_ratio = current_num / total_chunks
                elapsed = time.time() - start_time
                chunks_done_this_session = (idx - start_index) + 1
                avg_time = elapsed / max(chunks_done_this_session, 1)
                remaining_chunks = total_chunks - current_num
                eta_seconds = int(avg_time * remaining_chunks)

                status_msg = f"AI Vision: Sayfa {current_num} / {total_chunks}"
                self.after(0, lambda p=progress_ratio, s=status_msg, eta=eta_seconds, c=current_num, t=total_chunks: self._update_progress_ui(p, s, eta, c, t))

                try:
                    pairs = engine.translate_scanned_page(page_img)
                    for p_idx, pair in enumerate(pairs, 1):
                        src_text = pair.get("source", "").strip()
                        tr_text = pair.get("translated", "").strip()
                        if not src_text and not tr_text:
                            continue

                        pair_images = []
                        fig_box = pair.get("figure_box")
                        is_likely_figure = ("FIGURE" in src_text.upper() or "ŞEKİL" in tr_text.upper() or "TABLO" in tr_text.upper())

                        if should_translate_images and (fig_box or is_likely_figure):
                            try:
                                page_pil = Image.open(page_img)
                                p_w, p_h = page_pil.size
                                if fig_box and len(fig_box) == 4:
                                    ymin, xmin, ymax, xmax = fig_box
                                    x0, y0 = int(xmin * p_w / 1000.0), int(ymin * p_h / 1000.0)
                                    x1, y1 = int(xmax * p_w / 1000.0), int(ymax * p_h / 1000.0)
                                    if (x1 - x0) > 60 and (y1 - y0) > 40:
                                        fig_crop = page_pil.crop((x0, y0, x1, y1))
                                        ext_dir = os.path.join(get_app_dir(), "data", "extracted_images", re.sub(r'\W+', '_', file_name))
                                        os.makedirs(ext_dir, exist_ok=True)
                                        crop_path = os.path.join(ext_dir, f"fig_p{current_num}_{p_idx}.png")
                                        fig_crop.save(crop_path)

                                        tr_fig_path = image_translator.translate_figure_image(
                                            image_path=crop_path,
                                            provider=settings["provider"],
                                            api_key=settings["api_key"],
                                            model_name=settings["model_name"],
                                            base_url=settings.get("base_url", "")
                                        )
                                        pair_images.append(tr_fig_path)
                            except Exception:
                                pass

                        database.save_translation(file_name, src_text, tr_text, image_paths=pair_images)
                        completed_pairs.append({
                            "source": src_text,
                            "translated": tr_text,
                            "images": pair_images
                        })

                        img_note = f" [Şekil: {len(pair_images)}]" if pair_images else ""
                        preview_chunk = f"┌── [Sayfa {current_num} - Paragraf {p_idx}{img_note}] {'─'*40}\n│ EN: {src_text}\n│ TR: {tr_text}\n└──{'─'*60}\n\n"
                        self.after(0, lambda txt=preview_chunk: self._append_preview(txt))

                    time.sleep(0.4)

                except Exception as e:
                    err_msg = f"Sayfa {current_num} çevrilirken hata oluştu: {str(e)}"
                    self.after(0, lambda m=err_msg: self._on_translation_interrupted(m))
                    return
        else:
            # Standart Metin Blok Modu (Eşzamanlı / Paralel Worker Destekli)
            remaining_indices = list(range(start_index, total_chunks))
            chunks_completed = 0
            total_to_do = len(remaining_indices)

            def translate_task(idx: int):
                if self.cancel_requested:
                    return None
                chunk_item = self.parsed_paragraphs[idx]
                chunk_text = chunk_item["text"] if isinstance(chunk_item, dict) else str(chunk_item)
                chunk_images = chunk_item.get("images", []) if isinstance(chunk_item, dict) else []

                translated_text, is_cached = engine.translate_single_chunk(chunk_text, use_cache=True)

                final_chunk_images = []
                if should_translate_images and chunk_images:
                    for img_p in chunk_images:
                        try:
                            tr_img = image_translator.translate_figure_image(
                                image_path=img_p,
                                provider=settings["provider"],
                                api_key=settings["api_key"],
                                model_name=settings["model_name"],
                                base_url=settings.get("base_url", "")
                            )
                            final_chunk_images.append(tr_img)
                        except Exception:
                            final_chunk_images.append(img_p)
                else:
                    final_chunk_images = chunk_images

                return {
                    "idx": idx,
                    "source": chunk_text,
                    "translated": translated_text,
                    "images": final_chunk_images,
                    "is_cached": is_cached
                }

            with ThreadPoolExecutor(max_workers=workers_count) as executor:
                future_to_idx = {executor.submit(translate_task, idx): idx for idx in remaining_indices}

                for future in as_completed(future_to_idx):
                    if self.cancel_requested:
                        self.after(0, lambda: self._on_translation_interrupted("Çeviri kullanıcı tarafından durduruldu."))
                        return

                    res = future.result()
                    if not res:
                        continue

                    idx = res["idx"]
                    src_txt = res["source"]
                    tr_txt = res["translated"]
                    imgs = res["images"]
                    is_cached = res["is_cached"]

                    database.save_translation(file_name, src_txt, tr_txt, image_paths=imgs)
                    completed_pairs.append({
                        "source": src_txt,
                        "translated": tr_txt,
                        "images": imgs
                    })

                    chunks_completed += 1
                    current_num = start_index + chunks_completed
                    progress_ratio = current_num / total_chunks

                    elapsed = time.time() - start_time
                    avg_time = elapsed / max(chunks_completed, 1)
                    rem = total_chunks - current_num
                    eta_seconds = int(avg_time * rem)

                    cache_tag = " (Önbellek)" if is_cached else ""
                    status_msg = f"Çevriliyor: Paragraf {current_num} / {total_chunks}{cache_tag}"
                    self.after(0, lambda p=progress_ratio, s=status_msg, eta=eta_seconds, c=current_num, t=total_chunks: self._update_progress_ui(p, s, eta, c, t))

                    img_info = f" [Şekil: {len(imgs)}]" if imgs else ""
                    cache_note = " ⚡ [Önbellekten Alındı]" if is_cached else ""
                    preview_chunk = f"┌── [Paragraf {idx+1}{img_info}{cache_note}] {'─'*45}\n│ EN: {src_txt}\n│ TR: {tr_txt}\n└──{'─'*60}\n\n"
                    self.after(0, lambda txt=preview_chunk: self._append_preview(txt))

        # Word Derlemesi
        total_export_items = len(completed_pairs)
        self.after(0, lambda: self._append_preview(
            f"\n{'═'*60}\n"
            f"[BİLGİ] Tüm paragraflar tamamlandı! ({total_export_items} adet)\n"
            f"Word dokümanı (.docx) oluşturuluyor...\n"
            f"{'═'*60}\n"
        ))

        def _docx_progress(cur: int, tot: int, msg: str):
            ratio = (cur / tot) if tot > 0 else 1.0
            pct = int(ratio * 100)
            self.after(0, lambda r=ratio, p=pct, c=cur, t=tot, m=msg: self._update_word_export_progress(r, p, c, t, m))

        try:
            output_docx_path = doc_exporter.get_default_output_path(self.selected_pdf_path)
            doc_exporter.export_bilingual_docx(
                translation_pairs=completed_pairs,
                output_path=output_docx_path,
                original_filename=file_name,
                model_name=settings["model_name"],
                progress_callback=_docx_progress
            )
            self.last_exported_docx = output_docx_path
            self.after(0, lambda path=output_docx_path: self._on_translation_completed(path))
        except Exception as e:
            logger.error(f"Word derleme hatası: {e}")
            err_str = str(e)

            def _handle_word_err(err_msg=err_str):
                self.is_translating = False
                self.start_btn.configure(state="normal")
                self.resume_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled", fg_color=THEME.card_border, text_color=THEME.text_secondary)
                self.status_label.configure(text=f"Word Derleme Hatası: {err_msg}", text_color=THEME.danger)
                self.top_status_badge.configure(text="Word Hatası", fg_color=THEME.danger_bg, text_color=THEME.danger)
                messagebox.showerror("Word Derleme Hatası", f"Word belgesi oluşturulurken hata meydana geldi:\n\n{err_msg}")

            self.after(0, _handle_word_err)

    def _update_word_export_progress(self, ratio: float, pct: int, current: int, total: int, msg: str):
        self.progress_bar.set(ratio)
        self.status_label.configure(
            text=f"Word Derleniyor: %{pct} ({current}/{total}) - {msg}",
            text_color=THEME.accent
        )

    def _update_progress_ui(self, ratio: float, status_msg: str, eta_seconds: int, cur: int, total: int):
        self.progress_bar.set(ratio)
        self.status_label.configure(text=f"Durum: {status_msg}")
        self.metric_count_lbl.configure(text=f"{cur} / {total}")

        eta_str = f"{eta_seconds} sn" if eta_seconds < 60 else f"{eta_seconds // 60} dk {eta_seconds % 60} sn"
        self.metric_eta_lbl.configure(text=eta_str)

    def _clear_preview(self):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.configure(state="disabled")

    def _append_preview(self, text: str):
        self.preview_text.configure(state="normal")
        self.preview_text.insert("end", text)
        self.preview_text.see("end")
        self.preview_text.configure(state="disabled")

    def _on_translation_completed(self, docx_path: str):
        self.is_translating = False
        self.start_btn.configure(state="normal")
        self.resume_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled", fg_color=THEME.card_border, text_color=THEME.text_secondary)
        self.progress_bar.set(1.0)
        self.status_label.configure(text="✓ Çeviri ve Word Dokümanı Tamamlandı!", text_color=THEME.success)
        self.metric_eta_lbl.configure(text="Hazır ✓")
        self.top_status_badge.configure(text="Tamamlandı ✓", fg_color=THEME.success_bg, text_color=THEME.success)

        self.actions_row.pack(fill="x", padx=16, pady=(0, 14))

        messagebox.showinfo(
            "Başarılı",
            f"Çeviri başarıyla tamamlandı ve Word dosyası oluşturuldu:\n\n{docx_path}"
        )

    def _on_translation_interrupted(self, reason: str):
        self.is_translating = False
        self.start_btn.configure(state="normal")
        self.resume_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled", fg_color=THEME.card_border, text_color=THEME.text_secondary)
        self.status_label.configure(text=f"Duraklatıldı: {reason}", text_color=THEME.warning)
        self.top_status_badge.configure(text="Duraklatıldı", fg_color=THEME.warning_bg, text_color=THEME.warning)

        self._append_preview(
            f"\n{'!'*60}\n"
            f"[İŞLEM DURAKLATILDI / HATA]\n"
            f"{reason}\n"
            f"{'!'*60}\n"
        )

        file_name = os.path.basename(self.selected_pdf_path)
        existing = database.get_translations_by_file(file_name)
        if existing:
            self.file_info_badge.configure(
                text=f"Kesinti! {len(existing)} paragraf veritabanına kaydedildi. Dilediğinizde devam edebilirsiniz.",
                text_color=THEME.warning
            )
            self.resume_btn.pack(fill="x", pady=(6, 0))

    def _open_output_doc(self):
        if self.last_exported_docx and os.path.exists(self.last_exported_docx):
            try:
                open_file_or_folder(self.last_exported_docx)
            except Exception as e:
                messagebox.showerror("Hata", f"Dosya açılamadı:\n{str(e)}")

    def _open_output_folder(self):
        if self.last_exported_docx and os.path.exists(self.last_exported_docx):
            try:
                folder = os.path.dirname(os.path.abspath(self.last_exported_docx))
                open_file_or_folder(folder)
            except Exception as e:
                messagebox.showerror("Hata", f"Klasör açılamadı:\n{str(e)}")
