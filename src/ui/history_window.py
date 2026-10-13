import os
from typing import Optional, Callable
import customtkinter as ctk
from tkinter import filedialog, messagebox

from src import database
from src import doc_exporter
from src.paths import open_file_or_folder
from src.ui.theme import THEME


class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_reload_file: Optional[Callable[[str], None]] = None):
        super().__init__(parent)

        self.on_reload_file = on_reload_file
        self.selected_file: Optional[str] = None
        self.cached_history = []

        self.title("Çeviri Geçmişi ve Arşiv Yöneticisi")
        self.geometry("960x640")
        self.minsize(820, 520)
        self.configure(fg_color=THEME.bg_dark)

        # Modal gibi öne al
        self.after(100, self.lift)
        self.focus_set()

        self._build_ui()
        self._refresh_file_list()

    def _build_ui(self):
        # Üst Başlık Çubuğu
        header = ctk.CTkFrame(self, fg_color=THEME.sidebar_bg, corner_radius=0, height=65)
        header.pack(fill="x")
        header.pack_propagate(False)

        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(fill="both", expand=True, padx=20)

        left_header = ctk.CTkFrame(header_content, fg_color="transparent")
        left_header.pack(side="left", fill="y")

        title = ctk.CTkLabel(
            left_header,
            text="📚 Çeviri Geçmişi ve Arşiv",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=THEME.text_primary
        )
        title.pack(side="left", pady=18)

        # Arama ve Yenileme Butonları
        right_header = ctk.CTkFrame(header_content, fg_color="transparent")
        right_header.pack(side="right", fill="y")

        self.search_entry = ctk.CTkEntry(
            right_header,
            placeholder_text="Dosya ara...",
            width=200,
            height=34,
            fg_color=THEME.inner_card_bg,
            border_color=THEME.card_border
        )
        self.search_entry.pack(side="left", padx=(0, 10), pady=15)
        self.search_entry.bind("<KeyRelease>", lambda e: self._filter_file_list())

        refresh_btn = ctk.CTkButton(
            right_header,
            text="🔄 Yenile",
            width=85,
            height=34,
            fg_color=THEME.card_bg,
            hover_color=THEME.card_border,
            border_width=1,
            border_color=THEME.card_border,
            text_color=THEME.text_primary,
            command=self._refresh_file_list
        )
        refresh_btn.pack(side="left", pady=15)

        # Ana Bölücü Paneller
        main_panes = ctk.CTkFrame(self, fg_color="transparent")
        main_panes.pack(fill="both", expand=True, padx=20, pady=15)

        # Sol Panel (Dosya Listesi Kartı)
        left_card = ctk.CTkFrame(main_panes, width=340, corner_radius=12, fg_color=THEME.card_bg, border_width=1, border_color=THEME.card_border)
        left_card.pack(side="left", fill="y", padx=(0, 12))
        left_card.pack_propagate(False)

        left_header_lbl = ctk.CTkLabel(
            left_card,
            text="Kayıtlı Çeviriler",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=THEME.text_secondary
        )
        left_header_lbl.pack(anchor="w", padx=16, pady=(14, 8))

        self.files_scrollable = ctk.CTkScrollableFrame(
            left_card,
            fg_color="transparent"
        )
        self.files_scrollable.pack(fill="both", expand=True, padx=8, pady=(0, 12))

        # Sağ Panel (Detay ve Önizleme Kartı)
        right_card = ctk.CTkFrame(main_panes, corner_radius=12, fg_color=THEME.card_bg, border_width=1, border_color=THEME.card_border)
        right_card.pack(side="left", fill="both", expand=True)

        # Sağ Üst Bilgi Barı
        info_bar = ctk.CTkFrame(right_card, fg_color="transparent")
        info_bar.pack(fill="x", padx=18, pady=(14, 10))

        self.detail_title = ctk.CTkLabel(
            info_bar,
            text="Lütfen sol taraftan bir dosya seçin.",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=THEME.text_primary,
            anchor="w"
        )
        self.detail_title.pack(fill="x")

        self.detail_info = ctk.CTkLabel(
            info_bar,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=THEME.text_secondary,
            anchor="w"
        )
        self.detail_info.pack(fill="x", pady=(2, 0))

        # Önizleme Kutusu
        self.preview_box = ctk.CTkTextbox(
            right_card,
            font=ctk.CTkFont(size=12, family="Consolas"),
            fg_color=THEME.inner_card_bg,
            border_width=1,
            border_color=THEME.card_border,
            wrap="word",
            state="disabled"
        )
        self.preview_box.pack(fill="both", expand=True, padx=18, pady=(0, 14))
        self._lock_textbox_readonly(self.preview_box)

        # Alt Eylem Butonları
        actions_bar = ctk.CTkFrame(right_card, fg_color="transparent")
        actions_bar.pack(fill="x", padx=18, pady=(0, 16))

        self.export_btn = ctk.CTkButton(
            actions_bar,
            text="📄 Word Olarak Dışa Aktar (.docx)",
            height=36,
            fg_color=THEME.success,
            hover_color=THEME.success_hover,
            font=ctk.CTkFont(size=12, weight="bold"),
            state="disabled",
            command=self._export_selected_to_docx
        )
        self.export_btn.pack(side="left", padx=(0, 10))

        self.delete_btn = ctk.CTkButton(
            actions_bar,
            text="🗑️ Kayıtları Sil",
            height=36,
            fg_color=THEME.danger,
            hover_color=THEME.danger_hover,
            font=ctk.CTkFont(size=12),
            state="disabled",
            command=self._delete_selected_records
        )
        self.delete_btn.pack(side="left")

        close_btn = ctk.CTkButton(
            actions_bar,
            text="Kapat",
            width=80,
            height=36,
            fg_color=THEME.card_border,
            hover_color=THEME.card_bg,
            command=self.destroy
        )
        close_btn.pack(side="right")

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

    def _refresh_file_list(self):
        self.cached_history = database.get_history_summary()
        self._render_file_items(self.cached_history)

    def _filter_file_list(self):
        query = self.search_entry.get().strip().lower()
        if not query:
            self._render_file_items(self.cached_history)
        else:
            filtered = [item for item in self.cached_history if query in item["file_name"].lower()]
            self._render_file_items(filtered)

    def _render_file_items(self, items):
        for widget in self.files_scrollable.winfo_children():
            widget.destroy()

        if not items:
            ctk.CTkLabel(
                self.files_scrollable,
                text="Kayıtlı çeviri bulunamadı.",
                text_color=THEME.text_muted
            ).pack(pady=30)
            self._select_file(None)
            return

        for item in items:
            fname = item["file_name"]
            total = item["total_paragraphs"]
            date_str = str(item.get("last_updated", "")).split(".")[0]

            is_selected = (fname == self.selected_file)
            bg_col = THEME.nav_active_bg if is_selected else THEME.inner_card_bg

            btn_frame = ctk.CTkFrame(
                self.files_scrollable,
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
                command=lambda f=fname: self._select_file(f)
            )
            file_btn.pack(fill="both", expand=True, padx=6, pady=6)

        if not self.selected_file and items:
            self._select_file(items[0]["file_name"])

    def _select_file(self, file_name: Optional[str]):
        self.selected_file = file_name
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")

        if not file_name:
            self.detail_title.configure(text="Seçili dosya yok.")
            self.detail_info.configure(text="")
            self.export_btn.configure(state="disabled")
            self.delete_btn.configure(state="disabled")
            self.preview_box.configure(state="disabled")
            return

        self.export_btn.configure(state="normal")
        self.delete_btn.configure(state="normal")
        self.detail_title.configure(text=f"📄 {file_name}")

        records = database.get_translations_by_file(file_name)
        count = len(records)
        self.detail_info.configure(text=f"Toplam {count} adet çevrilmiş paragraf kayıtlı.")

        for i, r in enumerate(records, 1):
            src = r["source_paragraph"]
            tr = r["translated_paragraph"]
            imgs = r.get("image_paths", [])
            img_note = f" (Görsel Sayısı: {len(imgs)})" if imgs else ""

            self.preview_box.insert("end", f"┌── Paragraf #{i}{img_note} {'─'*40}\n")
            self.preview_box.insert("end", f"│ EN: {src}\n")
            self.preview_box.insert("end", f"│ TR: {tr}\n")
            self.preview_box.insert("end", f"└──{'─'*55}\n\n")

        self.preview_box.configure(state="disabled")

    def _export_selected_to_docx(self):
        if not self.selected_file:
            return

        records = database.get_translations_by_file(self.selected_file)
        if not records:
            messagebox.showwarning("Uyarı", "Bu dosya için çeviri kaydı bulunamadı.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Word Dosyası Olarak Kaydet",
            defaultextension=".docx",
            initialfile=f"{os.path.splitext(self.selected_file)[0]}_Ceviri.docx",
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
                original_filename=self.selected_file,
                model_name="Arşiv Kaydı"
            )
            msg = f"Word dokümanı başarıyla dışa aktarıldı:\n{out_path}\n\nDosyayı şimdi açmak ister misiniz?"
            if messagebox.askyesno("Dışa Aktarma Başarılı", msg):
                open_file_or_folder(out_path)
        except Exception as e:
            messagebox.showerror("Hata", f"Word belgesi oluşturulurken hata çıktı:\n{str(e)}")

    def _delete_selected_records(self):
        if not self.selected_file:
            return

        confirm = messagebox.askyesno(
            "Kayıtları Sil",
            f"'{self.selected_file}' dosyasına ait tüm çeviri kayıtları silinecek.\nEmin misiniz?"
        )
        if confirm:
            database.clear_translations_for_file(self.selected_file)
            self._refresh_file_list()
