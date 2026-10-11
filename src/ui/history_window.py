import os
from typing import Optional, Callable
import customtkinter as ctk
from tkinter import filedialog, messagebox

from src import database
from src import doc_exporter


class HistoryWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_reload_file: Optional[Callable[[str], None]] = None):
        super().__init__(parent)

        self.on_reload_file = on_reload_file
        self.selected_file: Optional[str] = None
        self.cached_history = []

        self.title("Geçmiş Çeviriler ve Arşiv")
        self.geometry("860x580")
        self.minsize(760, 480)

        # Modal gibi öne al
        self.after(100, self.lift)
        self.focus_set()

        self._build_ui()
        self._refresh_file_list()

    def _build_ui(self):
        # Üst Başlık
        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=(15, 10))

        title = ctk.CTkLabel(
            top_bar,
            text="📚 Çeviri Geçmişi ve Arşiv",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(side="left")

        refresh_btn = ctk.CTkButton(
            top_bar,
            text="Yenile",
            width=80,
            fg_color="#4a5568",
            command=self._refresh_file_list
        )
        refresh_btn.pack(side="right")

        # Ana Bölücü (Sol: Dosya Listesi, Sağ: Detay ve Önizleme)
        main_panes = ctk.CTkFrame(self, fg_color="transparent")
        main_panes.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        # Sol Panel (Dosya Listesi)
        left_frame = ctk.CTkFrame(main_panes, width=320, corner_radius=8)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        left_frame.pack_propagate(False)

        ctk.CTkLabel(
            left_frame,
            text="Kayıtlı Çeviri Dosyaları",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=12, pady=(10, 6))

        self.files_scrollable = ctk.CTkScrollableFrame(left_frame)
        self.files_scrollable.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Sağ Panel (Detay ve Önizleme)
        right_frame = ctk.CTkFrame(main_panes, corner_radius=8)
        right_frame.pack(side="left", fill="both", expand=True)

        self.detail_title = ctk.CTkLabel(
            right_frame,
            text="Lütfen sol taraftan bir dosya seçin.",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        self.detail_title.pack(fill="x", padx=15, pady=(12, 4))

        self.detail_info = ctk.CTkLabel(
            right_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray",
            anchor="w"
        )
        self.detail_info.pack(fill="x", padx=15, pady=(0, 8))

        # Önizleme Kutusu
        self.preview_box = ctk.CTkTextbox(right_frame, font=ctk.CTkFont(size=12), wrap="word", state="disabled")
        self.preview_box.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        self._lock_textbox_readonly(self.preview_box)

        # Alt Eylem Butonları
        actions_bar = ctk.CTkFrame(right_frame, fg_color="transparent")
        actions_bar.pack(fill="x", padx=15, pady=(0, 12))

        self.export_btn = ctk.CTkButton(
            actions_bar,
            text="Word Olarak Dışa Aktar (.docx)",
            fg_color="#2f855a",
            hover_color="#276749",
            state="disabled",
            command=self._export_selected_to_docx
        )
        self.export_btn.pack(side="left", padx=(0, 10))

        self.delete_btn = ctk.CTkButton(
            actions_bar,
            text="Kayıtları Sil",
            fg_color="#e53e3e",
            hover_color="#c53030",
            state="disabled",
            command=self._delete_selected_records
        )
        self.delete_btn.pack(side="left")

        close_btn = ctk.CTkButton(
            actions_bar,
            text="Kapat",
            width=80,
            fg_color="#718096",
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
        # Scrollable içindeki eski butonları temizle
        for widget in self.files_scrollable.winfo_children():
            widget.destroy()

        self.cached_history = database.get_history_summary()

        if not self.cached_history:
            ctk.CTkLabel(
                self.files_scrollable,
                text="Henüz kaydedilmiş bir\nçeviri geçmişi yok.",
                text_color="gray"
            ).pack(pady=40)
            self._select_file(None)
            return

        for item in self.cached_history:
            fname = item["file_name"]
            total = item["total_paragraphs"]
            date_str = str(item.get("last_updated", "")).split(".")[0]

            btn_frame = ctk.CTkFrame(self.files_scrollable, fg_color="#2d3748", corner_radius=6)
            btn_frame.pack(fill="x", pady=4, padx=2)

            # Dosya Seç Butonu
            file_btn = ctk.CTkButton(
                btn_frame,
                text=f"📄 {fname}\n{total} Paragraf | {date_str}",
                anchor="w",
                fg_color="transparent",
                hover_color="#3b485d",
                text_color="white",
                font=ctk.CTkFont(size=12),
                command=lambda f=fname: self._select_file(f)
            )
            file_btn.pack(fill="both", expand=True, padx=4, pady=4)

        # İlk dosyayı otomatik seç
        if self.cached_history:
            self._select_file(self.cached_history[0]["file_name"])

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

        # Önizlemeyi doldur
        for i, r in enumerate(records, 1):
            src = r["source_paragraph"]
            tr = r["translated_paragraph"]
            imgs = r.get("image_paths", [])
            img_note = f" (İlişkili Görsel: {len(imgs)} adet)" if imgs else ""
            
            entry_text = f"[Paragraf {i}{img_note}]\nEN: {src}\nTR: {tr}\n{'-'*60}\n"
            self.preview_box.insert("end", entry_text)

        self.preview_box.configure(state="disabled")

    def _export_selected_to_docx(self):
        if not self.selected_file:
            return

        records = database.get_translations_by_file(self.selected_file)
        if not records:
            messagebox.showwarning("Uyarı", "Bu dosyaya ait çeviri kaydı bulunamadı.")
            return

        # Kullanıcıdan kayıt yeri iste ('çevrilmiş' klasörünü varsayılan olarak öner)
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        default_dir = os.path.join(root_dir, "çevrilmiş")
        os.makedirs(default_dir, exist_ok=True)

        default_name = f"{os.path.splitext(self.selected_file)[0]}_cevrilmis.docx"
        out_path = filedialog.asksaveasfilename(
            title="Word Dosyasını Kaydet",
            initialdir=default_dir,
            initialfile=default_name,
            defaultextension=".docx",
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
            saved_path = doc_exporter.export_bilingual_docx(
                translation_pairs=pairs,
                output_path=out_path,
                original_filename=self.selected_file
            )
            
            if messagebox.askyesno("Başarılı", f"Word belgesi oluşturuldu:\n{saved_path}\n\nDosyayı şimdi açmak ister misiniz?"):
                os.startfile(saved_path)
        except Exception as e:
            messagebox.showerror("Hata", f"Dışa aktarma başarısız:\n{str(e)}")

    def _delete_selected_records(self):
        if not self.selected_file:
            return

        confirm = messagebox.askyesno(
            "Kayıtları Sil",
            f"'{self.selected_file}' dosyasına ait tüm çeviri kayıtları silinecek.\nBu işlem geri alınamaz. Emin misiniz?"
        )
        if confirm:
            database.clear_translations_for_file(self.selected_file)
            messagebox.showinfo("Bilgi", "Kayıtlar başarıyla silindi.")
            self._refresh_file_list()
