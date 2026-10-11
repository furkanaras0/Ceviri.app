import os
import re
import time
import threading
from typing import Optional, List, Dict, Any
from PIL import Image
import customtkinter as ctk
from tkinter import filedialog, messagebox

from src import database
from src import pdf_parser
from src import translator
from src import doc_exporter
from src import image_translator
from src.ui.history_window import HistoryWindow

# CustomTkinter Temel Görünüm Ayarları
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class AcademicTranslatorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Veritabanını ilklendir
        database.init_db()

        # Pencere Yapılandırması
        self.title("Akademik Makale Çeviricisi")
        self.geometry("980x840")
        self.minsize(860, 720)

        # Durum Değişkenleri
        self.selected_pdf_path: Optional[str] = None
        self.parsed_paragraphs: List[Any] = []
        self.is_translating: bool = False
        self.cancel_requested: bool = False
        self.last_exported_docx: Optional[str] = None
        self.is_settings_expanded: bool = True

        # Arayüz Bileşenlerini Kur
        self._build_ui()

        # Kayıtlı Ayarları Yükle
        self._load_saved_settings()

    def _build_ui(self):
        # Ana Konteyner (Kaydırılabilir)
        self.main_scrollable = ctk.CTkScrollableFrame(self, corner_radius=0)
        self.main_scrollable.pack(fill="both", expand=True, padx=20, pady=15)

        # 1. Başlık ve Üst Bölüm
        self._create_header_section()

        # 2. Ayarlar ve API Anahtarı Kartı (BYOK)
        self._create_settings_card()

        # 3. PDF Dosyası Seçim Kartı
        self._create_file_selection_card()

        # 4. Çeviri İlerleme ve Kontrol Kartı
        self._create_progress_card()

        # 5. Canlı Önizleme ve Sonuç Kartı
        self._create_preview_card()

    def _create_header_section(self):
        header_frame = ctk.CTkFrame(self.main_scrollable, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 15))

        left_col = ctk.CTkFrame(header_frame, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True)

        title_label = ctk.CTkLabel(
            left_col,
            text="Akademik Makale Çeviricisi",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title_label.pack(anchor="w")

        subtitle_label = ctk.CTkLabel(
            left_col,
            text="Çift sütunlu akademik PDF'leri yapısal olarak okur, LLM ile çevirir ve iki dilli Word (.docx) çıktısı üretir.",
            font=ctk.CTkFont(size=13),
            text_color="gray"
        )
        subtitle_label.pack(anchor="w", pady=(2, 0))

        history_btn = ctk.CTkButton(
            header_frame,
            text="📚 Geçmiş ve Arşiv",
            width=160,
            height=36,
            fg_color="#3182ce",
            hover_color="#2b6cb0",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_history_window
        )
        history_btn.pack(side="right", padx=(10, 0))

    def _open_history_window(self):
        HistoryWindow(self)

    def _create_settings_card(self):
        self.settings_card = ctk.CTkFrame(self.main_scrollable, corner_radius=10)
        self.settings_card.pack(fill="x", pady=(0, 15), padx=2, ipady=4)

        # Kart Başlık ve Aç/Kapa Kontrol Satırı
        header_row = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(8, 6))

        left_title_box = ctk.CTkFrame(header_row, fg_color="transparent")
        left_title_box.pack(side="left", fill="y")

        title = ctk.CTkLabel(
            left_title_box,
            text="1. API ve Model Ayarları (BYOK)",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        title.pack(side="left", padx=(0, 10))

        self.api_badge_label = ctk.CTkLabel(
            left_title_box,
            text="Kontrol ediliyor...",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.api_badge_label.pack(side="left")

        self.toggle_settings_btn = ctk.CTkButton(
            header_row,
            text="Ayarları Gizle ▲",
            width=130,
            height=28,
            fg_color="#2b6cb0",
            hover_color="#2c5282",
            command=self._toggle_settings_card
        )
        self.toggle_settings_btn.pack(side="right")

        # Açılıp Kapanan İçerik Kutusu
        self.settings_content_frame = ctk.CTkFrame(self.settings_card, fg_color="transparent")
        self.settings_content_frame.pack(fill="x", padx=0, pady=(2, 6))

        # Sağlayıcı ve Model Seçimi Satırı
        row1 = ctk.CTkFrame(self.settings_content_frame, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=4)

        ctk.CTkLabel(row1, text="Sağlayıcı:", width=80, anchor="w").pack(side="left")
        self.provider_combo = ctk.CTkComboBox(
            row1,
            values=["Google Gemini", "OpenAI Uyumlu / Özel"],
            command=self._on_provider_change,
            width=180
        )
        self.provider_combo.pack(side="left", padx=(0, 20))

        ctk.CTkLabel(row1, text="Model:", width=60, anchor="w").pack(side="left")
        self.model_combo = ctk.CTkComboBox(
            row1,
            values=[
                "gemini-flash-lite-latest",
                "gemini-flash-latest",
                "gemini-3.5-flash",
                "gemini-3.7-flash",
                "gemini-3.8-flash",
                "Özel Model...",
            ],
            command=self._on_model_change,
            width=180
        )
        self.model_combo.pack(side="left")

        # Özel Model Girişi (Gerektiğinde Görünür)
        self.custom_model_frame = ctk.CTkFrame(self.settings_content_frame, fg_color="transparent")
        ctk.CTkLabel(self.custom_model_frame, text="Özel Model Adı:", width=110, anchor="w").pack(side="left")
        self.custom_model_entry = ctk.CTkEntry(self.custom_model_frame, placeholder_text="Örn: gemini-3.8-pro veya gpt-4o", width=300)
        self.custom_model_entry.pack(side="left")

        # Base URL Girişi (OpenAI uyumlu seçilirse görünür)
        self.base_url_frame = ctk.CTkFrame(self.settings_content_frame, fg_color="transparent")
        ctk.CTkLabel(self.base_url_frame, text="Base URL:", width=110, anchor="w").pack(side="left")
        self.base_url_entry = ctk.CTkEntry(
            self.base_url_frame,
            placeholder_text="Örn: https://api.deepseek.com/v1 veya https://api.groq.com/openai/v1",
            width=400
        )
        self.base_url_entry.pack(side="left")

        # API Key Satırı
        row_key = ctk.CTkFrame(self.settings_content_frame, fg_color="transparent")
        row_key.pack(fill="x", padx=15, pady=(8, 4))

        ctk.CTkLabel(row_key, text="API Anahtarı:", width=80, anchor="w").pack(side="left")
        self.api_key_entry = ctk.CTkEntry(
            row_key,
            placeholder_text="Google AI Studio API Key veya OpenAI API Key yapıştırın...",
            show="*",
            width=420
        )
        self.api_key_entry.pack(side="left", padx=(0, 10))

        self.show_key_btn = ctk.CTkButton(row_key, text="Göster", width=60, command=self._toggle_show_api_key)
        self.show_key_btn.pack(side="left", padx=(0, 10))

        self.test_btn = ctk.CTkButton(
            row_key,
            text="Bağlantıyı Test Et",
            width=130,
            fg_color="#2b6cb0",
            hover_color="#2c5282",
            command=self._test_connection_threaded
        )
        self.test_btn.pack(side="left", padx=(0, 10))

        self.save_settings_btn = ctk.CTkButton(
            row_key,
            text="Kaydet",
            width=80,
            fg_color="#2f855a",
            hover_color="#276749",
            command=self._save_settings
        )
        self.save_settings_btn.pack(side="left")

        # Görsel İçi Çeviri Seçeneği (In-Image Visual Translation)
        row_visual = ctk.CTkFrame(self.settings_content_frame, fg_color="transparent")
        row_visual.pack(fill="x", padx=15, pady=(8, 2))

        self.translate_images_switch = ctk.CTkSwitch(
            row_visual,
            text="Şekil ve Grafikleri Türkçe Olarak Yeniden Çiz (Görsel İçi Çeviri)",
            font=ctk.CTkFont(size=12, weight="bold"),
            progress_color="#3182ce"
        )
        self.translate_images_switch.pack(side="left")
        self.translate_images_switch.select()

        # Test Durum Etiketi
        self.test_status_label = ctk.CTkLabel(
            self.settings_content_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.test_status_label.pack(anchor="w", padx=95, pady=(2, 5))

    def _toggle_settings_card(self):
        """API Ayarları kartını açıp kapatır."""
        if self.is_settings_expanded:
            self.settings_content_frame.pack_forget()
            self.toggle_settings_btn.configure(text="Ayarları Düzenle ⚙️", fg_color="#4a5568")
            self.is_settings_expanded = False
        else:
            self.settings_content_frame.pack(fill="x", padx=0, pady=(2, 6))
            self.toggle_settings_btn.configure(text="Ayarları Gizle ▲", fg_color="#2b6cb0")
            self.is_settings_expanded = True


    def _create_file_selection_card(self):
        self.file_card = ctk.CTkFrame(self.main_scrollable, corner_radius=10)
        self.file_card.pack(fill="x", pady=(0, 15), padx=2, ipady=8)

        title = ctk.CTkLabel(
            self.file_card,
            text="2. PDF Dosyası Seçimi",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        title.pack(anchor="w", padx=15, pady=(8, 6))

        file_row = ctk.CTkFrame(self.file_card, fg_color="transparent")
        file_row.pack(fill="x", padx=15, pady=4)

        self.select_file_btn = ctk.CTkButton(
            file_row,
            text="PDF Dosyası Seç...",
            width=150,
            command=self._select_pdf_file
        )
        self.select_file_btn.pack(side="left", padx=(0, 15))

        self.file_path_label = ctk.CTkLabel(
            file_row,
            text="Henüz bir dosya seçilmedi.",
            text_color="gray",
            anchor="w"
        )
        self.file_path_label.pack(side="left", fill="x", expand=True)

        # Dosya Analiz ve Fail-Safe Bilgi Kutusu
        self.file_info_frame = ctk.CTkFrame(self.file_card, fg_color="transparent")
        self.file_info_label = ctk.CTkLabel(
            self.file_info_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="#63b3ed",
            anchor="w"
        )
        self.file_info_label.pack(side="left", padx=15, pady=(2, 4))

        # Fail-safe Devam Butonu
        self.resume_btn = ctk.CTkButton(
            self.file_info_frame,
            text="Kaldığı Yerden Devam Et (Fail-Safe)",
            width=230,
            fg_color="#dd6b20",
            hover_color="#c05621",
            command=self._resume_existing_translation
        )

    def _create_progress_card(self):
        self.progress_card = ctk.CTkFrame(self.main_scrollable, corner_radius=10)
        self.progress_card.pack(fill="x", pady=(0, 15), padx=2, ipady=10)

        title = ctk.CTkLabel(
            self.progress_card,
            text="3. Çeviri Kontrol ve İlerleme",
            font=ctk.CTkFont(size=15, weight="bold")
        )
        title.pack(anchor="w", padx=15, pady=(8, 6))

        # Butonlar
        btn_row = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=15, pady=4)

        self.start_btn = ctk.CTkButton(
            btn_row,
            text="Çeviriyi Başlat",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2b6cb0",
            hover_color="#2c5282",
            height=38,
            width=180,
            command=self._start_translation_threaded
        )
        self.start_btn.pack(side="left", padx=(0, 15))

        self.cancel_btn = ctk.CTkButton(
            btn_row,
            text="Durdur / İptal",
            font=ctk.CTkFont(size=13),
            fg_color="#718096",
            hover_color="#e53e3e",
            height=38,
            width=130,
            state="disabled",
            command=self._cancel_translation
        )
        self.cancel_btn.pack(side="left", padx=(0, 20))

        # Durum Metni ve Süre Göstergesi
        self.status_label = ctk.CTkLabel(
            btn_row,
            text="Durum: Hazır",
            font=ctk.CTkFont(size=13),
            anchor="w"
        )
        self.status_label.pack(side="left", fill="x", expand=True)

        # İlerleme Çubuğu
        self.progress_bar = ctk.CTkProgressBar(self.progress_card)
        self.progress_bar.pack(fill="x", padx=15, pady=(12, 6))
        self.progress_bar.set(0.0)

        self.eta_label = ctk.CTkLabel(
            self.progress_card,
            text="İlerleme: %0  |  Tahmini Kalan Süre: -",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.eta_label.pack(anchor="w", padx=15, pady=(0, 4))

        # Çıktı Tamamlanma Butonları (Başlangıçta gizli)
        self.actions_row = ctk.CTkFrame(self.progress_card, fg_color="transparent")
        self.open_doc_btn = ctk.CTkButton(
            self.actions_row,
            text="Word Belgesini Aç (.docx)",
            fg_color="#2f855a",
            hover_color="#276749",
            command=self._open_output_doc
        )
        self.open_doc_btn.pack(side="left", padx=(0, 15))

        self.open_folder_btn = ctk.CTkButton(
            self.actions_row,
            text="Klasörü Aç",
            fg_color="#4a5568",
            hover_color="#2d3748",
            command=self._open_output_folder
        )
        self.open_folder_btn.pack(side="left")

    def _create_preview_card(self):
        self.preview_card = ctk.CTkFrame(self.main_scrollable, corner_radius=10)
        self.preview_card.pack(fill="both", expand=True, padx=2, ipady=10)

        header_row = ctk.CTkFrame(self.preview_card, fg_color="transparent")
        header_row.pack(fill="x", padx=15, pady=(8, 6))

        title = ctk.CTkLabel(
            header_row,
            text="Canlı Çeviri Akışı ve Önizleme",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        title.pack(side="left")

        clear_btn = ctk.CTkButton(
            header_row,
            text="Akışı Temizle",
            width=90,
            height=26,
            fg_color="#4a5568",
            command=self._clear_preview
        )
        clear_btn.pack(side="right")

        self.preview_text = ctk.CTkTextbox(
            self.preview_card,
            font=ctk.CTkFont(size=12),
            wrap="word",
            height=240,
            state="disabled"
        )
        self.preview_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        self._lock_textbox_readonly(self.preview_text)

    def _lock_textbox_readonly(self, textbox_widget: ctk.CTkTextbox):
        """Kullanıcının kutuya yazmasını, silmesini ve yapıştırmasını engeller. Yalnızca kopyalama ve seçmeye izin verir."""
        textbox_widget.configure(state="disabled")
        def on_key(event):
            # Ctrl+C ve Ctrl+A izin ver
            if (event.state & 0x4) and event.keysym.lower() in ('c', 'a'):
                return None
            # Ok tuşları ve sayfa gezinmeye izin ver
            if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Prior', 'Next', 'Home', 'End'):
                return None
            # Harf girişi, backspace, delete, yapıştırma vb. engelle
            return "break"

        if hasattr(textbox_widget, "_textbox"):
            textbox_widget._textbox.bind("<Key>", on_key)


    # ==========================================
    # Ayarlar ve Arayüz Olayları
    # ==========================================

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
            self.base_url_frame.pack(fill="x", padx=15, pady=4, after=self.custom_model_frame)
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
            self.custom_model_frame.pack(fill="x", padx=15, pady=4)
        else:
            self.custom_model_frame.pack_forget()

    def _get_current_settings(self) -> Dict[str, Any]:
        provider_val = "gemini" if self.provider_combo.get() == "Google Gemini" else "openai_compatible"
        model_choice = self.model_combo.get()
        if model_choice == "Özel Model...":
            model_name = self.custom_model_entry.get().strip() or "gemini-2.5-flash"
        else:
            model_name = model_choice

        return {
            "provider": provider_val,
            "api_key": self.api_key_entry.get().strip(),
            "model_name": model_name,
            "base_url": self.base_url_entry.get().strip(),
            "translate_images": self.translate_images_switch.get() == 1,
        }

    def _update_api_badge(self):
        """Ayar kartının üstündeki durum etiketini günceller."""
        settings = self._get_current_settings()
        if settings["api_key"]:
            m_name = settings["model_name"]
            prov = "Gemini" if settings["provider"] == "gemini" else "Özel/OpenAI"
            self.api_badge_label.configure(
                text=f"✓ {prov} ({m_name})",
                text_color="#48bb78"
            )
        else:
            self.api_badge_label.configure(
                text="⚠️ API Anahtarı Gerekli",
                text_color="#ecc94b"
            )

    def _save_settings(self):
        settings = self._get_current_settings()
        database.set_setting("provider", settings["provider"])
        database.set_setting("api_key", settings["api_key"])
        database.set_setting("model_name", settings["model_name"])
        database.set_setting("base_url", settings["base_url"])
        database.set_setting("translate_images", "1" if settings.get("translate_images") else "0")
        
        self._update_api_badge()
        self.test_status_label.configure(
            text="Ayarlar başarıyla kaydedildi.",
            text_color="#48bb78"
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

        # Model ayarla
        if model_name in self.model_combo.cget("values"):
            self.model_combo.set(model_name)
        else:
            self.model_combo.set("Özel Model...")
            self._on_model_change("Özel Model...")
            self.custom_model_entry.delete(0, "end")
            self.custom_model_entry.insert(0, model_name)

        # Durum etiketini güncelle
        self._update_api_badge()

        # Eğer API anahtarı zaten tanımlıysa arayüzün sade kalması için ayar kartını kapalı başlat
        if api_key and self.is_settings_expanded:
            self._toggle_settings_card()

    # ==========================================
    # API Testi (Threaded)
    # ==========================================

    def _test_connection_threaded(self):
        settings = self._get_current_settings()
        if not settings["api_key"]:
            messagebox.showwarning("Uyarı", "Lütfen önce bir API anahtarı girin.")
            return

        self.test_btn.configure(state="disabled")
        self.test_status_label.configure(text="Bağlantı test ediliyor...", text_color="#ed8936")

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
            self.test_status_label.configure(text="✓ Bağlantı başarılı! Model yanıt verdi.", text_color="#48bb78")
            self._save_settings()
        else:
            self.test_status_label.configure(text=f"✗ {msg}", text_color="#f56565")

    # ==========================================
    # Dosya Seçimi & Fail-Safe Kontrolü
    # ==========================================

    def _select_pdf_file(self):
        file_path = filedialog.askopenfilename(
            title="Akademik PDF Makalesi Seç",
            filetypes=[("PDF Dosyaları", "*.pdf"), ("Tüm Dosyalar", "*.*")]
        )
        if not file_path:
            return

        self.selected_pdf_path = file_path
        file_name = os.path.basename(file_path)
        self.file_path_label.configure(text=file_path, text_color="white")
        
        # Seçilen PDF dosyasını ana dizini kirletmemesi için 'çevrilen' klasörüne arşivle
        try:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cevrilen_dir = os.path.join(root_dir, "çevrilen")
            os.makedirs(cevrilen_dir, exist_ok=True)
            target_path = os.path.join(cevrilen_dir, file_name)
            if os.path.abspath(file_path) != os.path.abspath(target_path) and not os.path.exists(target_path):
                import shutil
                shutil.copy2(file_path, target_path)
        except Exception:
            pass

        self.actions_row.pack_forget()

        self.file_info_frame.pack(fill="x")
        self.file_info_label.configure(text="PDF analiz ediliyor ve paragraflar ayrıştırılıyor...", text_color="#ecc94b")
        self.resume_btn.pack_forget()

        def parse_file():
            try:
                chunks = pdf_parser.extract_paragraphs_from_pdf(file_path)
                self.parsed_paragraphs = chunks
                
                existing = database.get_translations_by_file(file_name)
                existing_count = len(existing)
                
                self.after(0, lambda: self._on_parse_finished(chunks, existing_count, file_name))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("PDF Hatası", f"PDF okunamadı:\n{str(e)}"))

        threading.Thread(target=parse_file, daemon=True).start()

    def _on_parse_finished(self, chunks: List[Any], existing_count: int, file_name: str):
        total_chunks = len(chunks)
        
        if total_chunks == 0:
            self.file_info_label.configure(
                text="⚠️ Uyarı: Bu PDF dosyasında metin tespit edilemedi. Dosya açılamadı veya boş.",
                text_color="#f56565"
            )
            self.resume_btn.pack_forget()
            return

        is_vision = bool(chunks and isinstance(chunks[0], dict) and chunks[0].get("is_vision"))
        if is_vision:
            info_text = f"✨ Akıllı AI Görsel Modu (Vision): Çizim/taranmış PDF algılandı! Toplam {total_chunks} sayfa çeviriye hazır."
            if existing_count > 0:
                info_text += f" | DB'de {existing_count} kayıt mevcut."
                self.file_info_label.configure(text=info_text, text_color="#63b3ed")
                self.resume_btn.pack(side="left", padx=10)
            else:
                self.file_info_label.configure(text=info_text, text_color="#63b3ed")
                self.resume_btn.pack_forget()
        else:
            info_text = f"Toplam {total_chunks} adet akademik paragraf tespit edildi."
            if existing_count > 0:
                info_text += f" | Veritabanında {existing_count} adet önceden çevrilmiş kayıt bulundu!"
                self.file_info_label.configure(text=info_text, text_color="#ecc94b")
                self.resume_btn.pack(side="left", padx=10)
            else:
                self.file_info_label.configure(text=info_text, text_color="#48bb78")
                self.resume_btn.pack_forget()

    def _resume_existing_translation(self):
        self._start_translation_threaded(resume=True)

    # ==========================================
    # Çeviri Süreci ve Multi-Threading
    # ==========================================

    def _start_translation_threaded(self, resume: bool = False):
        if not self.selected_pdf_path:
            messagebox.showwarning("Uyarı", "Lütfen önce bir PDF dosyası seçin.")
            return

        if not self.parsed_paragraphs:
            messagebox.showwarning(
                "Metin Bulunamadı",
                "Seçilen PDF'te çevrilebilecek metin paragrafı bulunamadı.\n(Doküman taranmış veya resim formatında olabilir)."
            )
            return

        settings = self._get_current_settings()
        if not settings["api_key"]:
            messagebox.showwarning("Uyarı", "Lütfen API anahtarınızı girin.")
            return

        # Kullanıcı manuel basmasa bile ayarları otomatik kaydet
        self._save_settings()
        if self.is_settings_expanded:
            self._toggle_settings_card()

        self.is_translating = True
        self.cancel_requested = False

        self.start_btn.configure(state="disabled")
        self.resume_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal", fg_color="#e53e3e")
        self.actions_row.pack_forget()

        threading.Thread(target=self._run_translation_worker, args=(settings, resume), daemon=True).start()

    def _cancel_translation(self):
        if self.is_translating:
            self.cancel_requested = True
            self.status_label.configure(text="Durum: İptal ediliyor... Lütfen bekleyin.")

    def _run_translation_worker(self, settings: Dict[str, str], resume: bool):
        file_name = os.path.basename(self.selected_pdf_path)
        total_chunks = len(self.parsed_paragraphs)
        
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
            self.after(0, lambda: self._append_preview(f"--- Önceki {already_translated_count} çeviri veritabanından yüklendi ---\n\n"))

        start_time = time.time()
        start_index = already_translated_count
        is_vision_mode = bool(self.parsed_paragraphs and isinstance(self.parsed_paragraphs[0], dict) and self.parsed_paragraphs[0].get("is_vision"))
        should_translate_images = bool(settings.get("translate_images", True))

        if is_vision_mode:
            # Yapay Zeka Görsel Okuma (Vision OCR) Modu
            for idx in range(start_index, total_chunks):
                if self.cancel_requested:
                    self.after(0, lambda: self._on_translation_interrupted("Çeviri kullanıcı tarafından durduruldu."))
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

                status_msg = f"AI Görsel Okuma & Çeviri: Sayfa {current_num} / {total_chunks}"
                self.after(0, lambda p=progress_ratio, s=status_msg, eta=eta_seconds: self._update_progress_ui(p, s, eta))

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
                                        ext_dir = os.path.join("data", "extracted_images", re.sub(r'\W+', '_', file_name))
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

                        img_note = f" [Çevrilmiş Şekil Görseli: {len(pair_images)}]" if pair_images else ""
                        preview_chunk = f"[Sayfa {current_num} - Paragraf {p_idx}{img_note}]\nEN: {src_text}\nTR: {tr_text}\n{'-'*60}\n"
                        self.after(0, lambda txt=preview_chunk: self._append_preview(txt))

                    time.sleep(0.5)

                except Exception as e:
                    err_msg = f"Sayfa {current_num} çevrilirken hata oluştu: {str(e)}"
                    self.after(0, lambda m=err_msg: self._on_translation_interrupted(m))
                    return
        else:
            # Standart Metin Blok Çeviri Modu
            for idx in range(start_index, total_chunks):
                if self.cancel_requested:
                    self.after(0, lambda: self._on_translation_interrupted("Çeviri kullanıcı tarafından durduruldu."))
                    return

                chunk_item = self.parsed_paragraphs[idx]
                chunk_text = chunk_item["text"] if isinstance(chunk_item, dict) else str(chunk_item)
                chunk_images = chunk_item.get("images", []) if isinstance(chunk_item, dict) else []

                current_num = idx + 1

                progress_ratio = current_num / total_chunks
                elapsed = time.time() - start_time
                chunks_done_this_session = (idx - start_index) + 1
                avg_time = elapsed / max(chunks_done_this_session, 1)
                remaining_chunks = total_chunks - current_num
                eta_seconds = int(avg_time * remaining_chunks)

                status_msg = f"Çevriliyor: Paragraf {current_num} / {total_chunks}"
                self.after(0, lambda p=progress_ratio, s=status_msg, eta=eta_seconds: self._update_progress_ui(p, s, eta))

                try:
                    translated_text = engine.translate_single_chunk(chunk_text)

                    # Şekil ve görsellerin içindeki metinleri Türkçeleştir
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

                    database.save_translation(file_name, chunk_text, translated_text, image_paths=final_chunk_images)
                    
                    completed_pairs.append({
                        "source": chunk_text,
                        "translated": translated_text,
                        "images": final_chunk_images
                    })

                    img_info = f" [Çevrilmiş Şekil: {len(final_chunk_images)}]" if final_chunk_images else ""
                    preview_chunk = f"[Paragraf {current_num}{img_info}]\nEN: {chunk_text}\nTR: {translated_text}\n{'-'*60}\n"
                    self.after(0, lambda txt=preview_chunk: self._append_preview(txt))

                    time.sleep(0.4)

                except Exception as e:
                    err_msg = f"Paragraf {current_num} çevrilirken hata oluştu: {str(e)}"
                    self.after(0, lambda m=err_msg: self._on_translation_interrupted(m))
                    return

        total_export_items = len(completed_pairs)
        self.after(0, lambda: self._append_preview(
            f"\n{'='*60}\n"
            f"[BİLGİ] Tüm paragrafların çevirisi tamamlandı! ({total_export_items} paragraf)\n"
            f"Word dokümanı (.docx) oluşturuluyor...\n"
            f"{'='*60}\n"
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
            import traceback
            full_trace = traceback.format_exc()
            err_str = str(e)

            def _handle_word_err(err_msg=err_str, trace=full_trace):
                self.is_translating = False
                self.start_btn.configure(state="normal")
                self.resume_btn.configure(state="normal")
                self.cancel_btn.configure(state="disabled", fg_color="#718096")
                self.status_label.configure(text=f"Word Derleme Hatası: {err_msg}", text_color="#f56565")
                self.eta_label.configure(text="Word oluşturulamadı! Hata ayrıntıları aşağıya yazdırıldı.")

                # Canlı önizleme kutusuna detaylı hata raporunu yazdır
                err_report = (
                    f"\n{'!'*60}\n"
                    f"[HATA - WORD DOKÜMANI OLUŞTURULAMADI]\n"
                    f"Hata Mesajı: {err_msg}\n\n"
                    f"Ayrıntılı Hata İzi (Traceback):\n{trace}"
                    f"{'!'*60}\n"
                )
                self._append_preview(err_report)

                messagebox.showerror(
                    "Word Derleme Hatası",
                    f"Word belgesi oluşturulurken bir hata meydana geldi:\n\n{err_msg}\n\n"
                    f"Hata ayrıntıları Canlı Çeviri Akışı paneline yazdırıldı."
                )

            self.after(0, _handle_word_err)

    def _update_word_export_progress(self, ratio: float, pct: int, current: int, total: int, msg: str):
        self.progress_bar.set(ratio)
        self.status_label.configure(
            text=f"Word Derleniyor: %{pct} ({current}/{total})",
            text_color="#63b3ed"
        )
        self.eta_label.configure(text=f"Aşama: {msg}")

    def _update_progress_ui(self, ratio: float, status_msg: str, eta_seconds: int):
        self.progress_bar.set(ratio)
        self.status_label.configure(text=f"Durum: {status_msg}")
        
        pct = int(ratio * 100)
        eta_str = f"{eta_seconds} sn" if eta_seconds < 60 else f"{eta_seconds // 60} dk {eta_seconds % 60} sn"
        self.eta_label.configure(text=f"İlerleme: %{pct}  |  Tahmini Kalan Süre: {eta_str}")

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
        self.cancel_btn.configure(state="disabled", fg_color="#718096")
        self.progress_bar.set(1.0)
        self.status_label.configure(text="✓ Çeviri ve Word Dokümanı Başarıyla Tamamlandı!", text_color="#48bb78")
        self.eta_label.configure(text="İlerleme: %100  |  Word (.docx) belgesi hazır!")
        
        self.actions_row.pack(fill="x", padx=15, pady=(10, 4))
        
        messagebox.showinfo(
            "Başarılı",
            f"Çeviri başarıyla tamamlandı ve Word dosyası oluşturuldu:\n\n{docx_path}"
        )

    def _on_translation_interrupted(self, reason: str):
        self.is_translating = False
        self.start_btn.configure(state="normal")
        self.resume_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled", fg_color="#718096")
        self.status_label.configure(text=f"Duraklatıldı: {reason}", text_color="#ecc94b")
        
        # Hata veya kesinti durumunu önizleme akışına yazdır
        self._append_preview(
            f"\n{'!'*60}\n"
            f"[İŞLEM DURAKLATILDI / HATA ALINDI]\n"
            f"{reason}\n"
            f"{'!'*60}\n"
        )
        
        file_name = os.path.basename(self.selected_pdf_path)
        existing = database.get_translations_by_file(file_name)
        if existing:
            self.file_info_label.configure(
                text=f"Kesinti! {len(existing)} paragraf veritabanına kaydedildi. Dilediğinizde devam edebilirsiniz.",
                text_color="#ecc94b"
            )
            self.resume_btn.pack(side="left", padx=10)

    def _open_output_doc(self):
        if self.last_exported_docx and os.path.exists(self.last_exported_docx):
            try:
                os.startfile(self.last_exported_docx)
            except Exception as e:
                messagebox.showerror("Hata", f"Dosya açılamadı:\n{str(e)}")

    def _open_output_folder(self):
        if self.last_exported_docx and os.path.exists(self.last_exported_docx):
            try:
                folder = os.path.dirname(os.path.abspath(self.last_exported_docx))
                os.startfile(folder)
            except Exception as e:
                messagebox.showerror("Hata", f"Klasör açılamadı:\n{str(e)}")
