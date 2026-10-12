import os
import re
from datetime import datetime
from typing import List, Dict, Optional, Callable
import docx
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from src.paths import get_app_dir


def sanitize_xml_text(text: str) -> str:
    """Word OpenXML ile uyumsuz kontrol karakterlerini (\x00-\x08, \x0b-\x0c, \x0e-\x1f vb.) temizler."""
    if not text:
        return ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]', '', str(text))


def get_default_output_path(pdf_path: str, suffix: str = "_cevrilmis.docx") -> str:
    """
    Kaynak PDF dosya yolundan varsayılan Word çıktı yolunu üretir.
    Çıktı dosyalarını ana dizini kirletmemesi için 'çevrilmiş' klasöründe toplar.
    Klasör oluşturulamazsa güvenli bir şekilde PDF'in kendi dizinine döner.
    """
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    output_filename = f"{base_name}{suffix}"

    try:
        root_dir = get_app_dir()
        output_dir = os.path.join(root_dir, "çevrilmiş")
        os.makedirs(output_dir, exist_ok=True)
        if os.path.isdir(output_dir):
            return os.path.join(output_dir, output_filename)
    except Exception:
        pass

    directory = os.path.dirname(os.path.abspath(pdf_path))
    return os.path.join(directory, output_filename)


def export_bilingual_docx(
    translation_pairs: List[Dict[str, str]],
    output_path: str,
    original_filename: Optional[str] = None,
    model_name: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> str:
    """
    İngilizce orijinal ve Türkçe çeviri metin bloklarını dokümanda belirtilen
    görsel hiyerarşiye uygun olarak iki dilli bir Word belgesine (.docx) derler.
    
    translation_pairs: [{'source': '...', 'translated': '...'}, ...]
    
    Görsel Hiyerarşi Kuralları:
    - İngilizce Orijinal Paragraf: İtalik, 10pt, gri tonlu (#555555), başında 'EN: ' etiketi.
    - Türkçe Çeviri Paragrafı: Standart, 11pt, siyah/koyu (#000000), başında 'TR: ' etiketi.
    """
    doc = docx.Document()
    
    # Sayfa kenar boşlukları (Standart 1 inç / 2.54 cm)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # 1. Başlık ve Üstbilgi Bölümü
    raw_title = original_filename or (os.path.basename(output_path).replace("_cevrilmis.docx", ".pdf"))
    file_title = sanitize_xml_text(raw_title)
    
    title_p = doc.add_paragraph()
    title_run = title_p.add_run("İki Dilli Akademik Çeviri Dokümanı")
    title_run.font.name = "Calibri"
    title_run.font.size = Pt(16)
    title_run.font.bold = True
    title_run.font.color.rgb = RGBColor(26, 54, 93)  # Koyu lacivert kurumsal ton
    title_p.paragraph_format.space_after = Pt(2)

    subtitle_p = doc.add_paragraph()
    sub_text = f"Kaynak Dosya: {file_title}  |  Tarih: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    if model_name:
        sub_text += f"  |  Model: {sanitize_xml_text(model_name)}"
    subtitle_run = subtitle_p.add_run(sub_text)
    subtitle_run.font.name = "Calibri"
    subtitle_run.font.size = Pt(9.5)
    subtitle_run.font.italic = True
    subtitle_run.font.color.rgb = RGBColor(113, 128, 150)
    subtitle_p.paragraph_format.space_after = Pt(16)

    total_count = len(translation_pairs)
    if progress_callback:
        progress_callback(0, total_count, "Word dokümanı şablonu hazırlanıyor...")

    # 2. İki Dilli Paragraf Blokları
    for idx, pair in enumerate(translation_pairs, 1):
        if progress_callback:
            progress_callback(idx, total_count, f"Word derleniyor: Paragraf {idx}/{total_count}")

        source_text = sanitize_xml_text(pair.get("source", "")).strip()
        translated_text = sanitize_xml_text(pair.get("translated", "")).strip()

        if not source_text and not translated_text:
            continue

        # A. İngilizce Orijinal Paragraf (İtalik, 10pt, Gri ton #555555, başında 'EN: ')
        en_p = doc.add_paragraph()
        en_p.paragraph_format.space_before = Pt(0)
        en_p.paragraph_format.space_after = Pt(3)
        en_p.paragraph_format.line_spacing = 1.15
        
        tag_en = en_p.add_run("EN: ")
        tag_en.font.name = "Calibri"
        tag_en.font.size = Pt(10)
        tag_en.font.bold = True
        tag_en.font.color.rgb = RGBColor(100, 110, 120)

        body_en = en_p.add_run(source_text)
        body_en.font.name = "Calibri"
        body_en.font.size = Pt(10)
        body_en.font.italic = True
        body_en.font.color.rgb = RGBColor(85, 85, 85)

        # B. Türkçe Çeviri Paragrafı (Standart font, 11pt, Siyah #000000, başında 'TR: ')
        tr_p = doc.add_paragraph()
        tr_p.paragraph_format.space_before = Pt(0)
        tr_p.paragraph_format.space_after = Pt(14)  # Bloklar arası belirgin boşluk
        tr_p.paragraph_format.line_spacing = 1.2
        
        tag_tr = tr_p.add_run("TR: ")
        tag_tr.font.name = "Calibri"
        tag_tr.font.size = Pt(11)
        tag_tr.font.bold = True
        tag_tr.font.color.rgb = RGBColor(0, 0, 0)

        body_tr = tr_p.add_run(translated_text)
        body_tr.font.name = "Calibri"
        body_tr.font.size = Pt(11)
        body_tr.font.italic = False
        body_tr.font.color.rgb = RGBColor(17, 24, 39)

        # C. İlişkili Görseller / Grafikler / Şekiller (Varsa Ortalanmış Olarak Ekle)
        images = pair.get("images") or pair.get("image_paths") or []
        for img_path in images:
            if not img_path:
                continue
            # Eğer görselin çevrilmiş versiyonu (_tr.png) varsa öncelikli olarak onu yerleştir
            tr_candidate = os.path.splitext(img_path)[0] + "_tr.png"
            actual_img_path = tr_candidate if os.path.exists(tr_candidate) else img_path
            
            if os.path.exists(actual_img_path):
                try:
                    img_p = doc.add_paragraph()
                    img_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    img_p.paragraph_format.space_before = Pt(6)
                    img_p.paragraph_format.space_after = Pt(14)
                    run = img_p.add_run()
                    run.add_picture(actual_img_path, width=Inches(5.0))
                except Exception:
                    pass

    # Klasör yoksa oluştur ve dosyayı kaydet
    out_dir = os.path.dirname(os.path.abspath(output_path))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    if progress_callback:
        progress_callback(total_count, total_count, "Word belgesi diske kaydediliyor...")

    try:
        doc.save(output_path)
        if progress_callback:
            progress_callback(total_count, total_count, "Word belgesi başarıyla tamamlandı!")
        return output_path
    except PermissionError:
        # Eğer dosya Microsoft Word'de açıksa kilitlidir; yeni bir isimle kaydet
        timestamp_str = datetime.now().strftime("%H%M%S")
        base_root, ext = os.path.splitext(output_path)
        fallback_path = f"{base_root}_{timestamp_str}{ext}"
        doc.save(fallback_path)
        if progress_callback:
            progress_callback(total_count, total_count, "Word belgesi alternatif isimle kaydedildi!")
        return fallback_path

