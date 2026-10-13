import os
import re
from typing import List, Dict, Any, Tuple, Optional
import pymupdf
from src.paths import get_app_dir


def clean_text(text: str) -> str:
    """
    Metindeki gereksiz boşlukları, satır sonu tirelemelerini (hyphenation)
    ve satır kaymalarını temizleyip akıcı bir paragrafa dönüştürür.
    """
    if not text:
        return ""
    
    # 1. Satır sonu tireleme düzeltmesi: "transla-\ntion" -> "translation"
    text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
    
    # 2. Satır sonlarını boşluğa çevir
    text = re.sub(r'\r?\n', ' ', text)
    
    # 3. Birden fazla boşlukları teke indir
    text = re.sub(r'[ \t]+', ' ', text)
    
    return text.strip()


def is_header_or_footer(bbox: Tuple[float, float, float, float], page_rect: pymupdf.Rect, text: str) -> bool:
    """
    Bir metin bloğunun sayfa numarası, üstbilgi (header) veya altbilgi (footer)
    olup olmadığını tespit eder.
    """
    x0, y0, x1, y1 = bbox
    height = page_rect.height
    cleaned = text.strip()
    
    top_margin_threshold = height * 0.07
    bottom_margin_threshold = height * 0.93
    
    is_page_number = bool(re.match(r'^(page\s*)?\d+(\s*of\s*\d+)?$|^[ivxlcdm]+$', cleaned, re.IGNORECASE))
    
    if y1 <= top_margin_threshold:
        if len(cleaned.split()) <= 15 or is_page_number:
            return True
            
    if y0 >= bottom_margin_threshold:
        if len(cleaned.split()) <= 15 or is_page_number:
            return True
            
    if is_page_number and (y0 < height * 0.12 or y1 > height * 0.88):
        return True

    return False


def is_caption(text: str) -> bool:
    """
    Metnin bir şekil (figure), grafik veya tablo açıklaması olup olmadığını belirler.
    """
    pattern = r'^(fig\.|figure|table|tab\.|şekil|tablo|chart|grafik)\s*\d+'
    return bool(re.match(pattern, text.strip(), re.IGNORECASE))


def sort_blocks_academic_order(blocks: List[Tuple], page_rect: pymupdf.Rect) -> List[Tuple]:
    """
    Akademik makalelerdeki çift sütunlu veya tek sütunlu düzeni tespit ederek
    metin bloklarını doğru okuma sırasına dizer.
    """
    if not blocks:
        return []

    mid_x = page_rect.width / 2.0
    column_tolerance = page_rect.width * 0.08

    top_spanning = []
    left_column = []
    right_column = []
    bottom_spanning = []

    for block in blocks:
        x0, y0, x1, y1, text, block_no, block_type = block
        
        if block_type != 0:
            continue
            
        block_width = x1 - x0
        is_spanning_full_width = (block_width > page_rect.width * 0.65) or (x0 < (mid_x - column_tolerance) and x1 > (mid_x + column_tolerance))
        
        if is_spanning_full_width:
            if y0 < page_rect.height * 0.4:
                top_spanning.append(block)
            else:
                bottom_spanning.append(block)
        else:
            block_center_x = (x0 + x1) / 2.0
            if block_center_x < mid_x:
                left_column.append(block)
            else:
                right_column.append(block)

    top_spanning.sort(key=lambda b: b[1])
    left_column.sort(key=lambda b: b[1])
    right_column.sort(key=lambda b: b[1])
    bottom_spanning.sort(key=lambda b: b[1])

    return top_spanning + left_column + right_column + bottom_spanning


def get_pdf_page_count(pdf_path: str) -> int:
    """PDF dosyasının toplam sayfa sayısını döndürür."""
    try:
        doc = pymupdf.open(pdf_path)
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def parse_page_range(range_str: Optional[str], total_pages: int) -> List[int]:
    """
    Kullanıcının girdiği sayfa aralığı metnini (örn: '1-5', '1, 3, 5-8', 'Tümü') 0-indeksli sayfa listesine dönüştürür.
    Geçersiz veya boş girişlerde tüm sayfaları döndürür.
    """
    if not range_str or not range_str.strip():
        return list(range(total_pages))

    s = range_str.strip().lower()
    if s in ["tümü", "all", "*", "hepsi"]:
        return list(range(total_pages))

    selected = set()
    parts = [p.strip() for p in s.split(",") if p.strip()]

    for part in parts:
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) == 2:
                try:
                    start = int(bounds[0].strip())
                    end = int(bounds[1].strip())
                    if start <= end:
                        for p in range(start, end + 1):
                            if 1 <= p <= total_pages:
                                selected.add(p - 1)
                except ValueError:
                    continue
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    selected.add(p - 1)
            except ValueError:
                continue

    if not selected:
        return list(range(total_pages))

    return sorted(list(selected))


def extract_paragraphs_from_pdf(
    pdf_path: str,
    min_words: int = 10,
    extract_images: bool = True,
    page_range_str: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    PDF dosyasını açar, belirtilen sayfa aralığında çift sütunlu akademik düzeni çözerek
    sayfa numaralarını ve parazitleri ayıklar.
    """
    doc = pymupdf.open(pdf_path)
    total_doc_pages = len(doc)
    target_pages = parse_page_range(page_range_str, total_doc_pages)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    
    # Görsellerin kaydedileceği dizin: data/extracted_images/<pdf_adi>/
    images_dir = ""
    if extract_images:
        root_dir = get_app_dir()
        images_dir = os.path.join(root_dir, "data", "extracted_images", re.sub(r'\W+', '_', base_name))
        os.makedirs(images_dir, exist_ok=True)

    raw_chunks: List[Dict[str, Any]] = []
    pending_caption: str = ""
    pending_images: List[str] = []

    for page_idx in target_pages:
        page = doc[page_idx]
        page_rect = page.rect
        blocks = page.get_text("blocks")
        
        # Sayfadaki görselleri ayıkla
        page_images: List[Dict[str, Any]] = []
        if extract_images:
            try:
                img_infos = page.get_image_info(xrefs=True)
                for img_idx, info in enumerate(img_infos):
                    xref = info.get("xref")
                    if not xref:
                        continue
                    # Çok küçük ikonları / mermi işaretlerini filtrele
                    if info.get("width", 0) < 60 or info.get("height", 0) < 60:
                        continue

                    # Sayfanın tamamını kaplayan zemin taramalarını (arka plan resimlerini) filtrele
                    bbox = info.get("bbox")
                    if bbox:
                        bx0, by0, bx1, by1 = bbox
                        cov_w = (bx1 - bx0) / max(page_rect.width, 1)
                        cov_h = (by1 - by0) / max(page_rect.height, 1)
                        if cov_w > 0.85 and cov_h > 0.85:
                            continue  # Bu bir diyagram değil, taranmış tam sayfa zeminidir
                        
                    img_data = doc.extract_image(xref)
                    if not img_data or not img_data.get("image"):
                        continue
                        
                    ext = img_data.get("ext", "png")
                    img_filename = f"page_{page_idx+1}_img_{img_idx+1}.{ext}"
                    img_filepath = os.path.join(images_dir, img_filename)
                    
                    with open(img_filepath, "wb") as f:
                        f.write(img_data["image"])
                        
                    bbox = info.get("bbox", (0, 0, 0, 0))
                    page_images.append({
                        "path": img_filepath,
                        "bbox": bbox,
                        "y0": bbox[1] if bbox else 0
                    })
            except Exception:
                pass  # Görsel çıkarma hatası olursa metin akışını kesme

        # Metin bloklarını akademik sırada diz
        ordered_blocks = sort_blocks_academic_order(blocks, page_rect)
        
        for block in ordered_blocks:
            bbox = (block[0], block[1], block[2], block[3])
            text = block[4]
            
            if is_header_or_footer(bbox, page_rect, text):
                continue
                
            cleaned = clean_text(text)
            if not cleaned:
                continue
                
            # Şekil / Grafik açıklaması mı?
            if is_caption(cleaned):
                caption_formatted = f"[Şekil/Tablo Verisi: {cleaned}]"
                
                # Bu açıklamaya en yakın sayfadaki görseli bul
                matched_imgs = []
                if page_images:
                    # Caption ile yakın y0 koordinatına sahip görseller
                    caption_y = bbox[1]
                    for img in list(page_images):
                        if abs(img["y0"] - caption_y) < page_rect.height * 0.35:
                            matched_imgs.append(img["path"])
                            page_images.remove(img)

                if raw_chunks:
                    raw_chunks[-1]["text"] += f" {caption_formatted}"
                    raw_chunks[-1]["images"].extend(matched_imgs)
                else:
                    pending_caption = caption_formatted
                    pending_images.extend(matched_imgs)
                continue
                
            # Önceden kalan bir caption veya görsel varsa bağla
            matched_imgs = []
            if pending_caption:
                cleaned = f"{cleaned} {pending_caption}"
                matched_imgs.extend(pending_images)
                pending_caption = ""
                pending_images = []

            # Sayfada henüz eşleşmemiş görsel varsa ve bu bloğa yakınsa ekle
            if page_images:
                block_y = bbox[1]
                for img in list(page_images):
                    if abs(img["y0"] - block_y) < page_rect.height * 0.25:
                        matched_imgs.append(img["path"])
                        page_images.remove(img)

            raw_chunks.append({
                "text": cleaned,
                "images": matched_imgs
            })

    doc.close()

    # 10 kelimeden küçük parçaları birleştirme (Chunking)
    final_paragraphs: List[Dict[str, Any]] = []
    buffer_text = ""
    buffer_images: List[str] = []

    for chunk in raw_chunks:
        text = chunk["text"]
        imgs = chunk["images"]

        if not buffer_text:
            buffer_text = text
            buffer_images = list(imgs)
        else:
            word_count = len(buffer_text.split())
            if word_count < min_words:
                buffer_text = f"{buffer_text} {text}"
                buffer_images.extend(imgs)
            else:
                final_paragraphs.append({
                    "text": buffer_text,
                    "images": list(set(buffer_images))
                })
                buffer_text = text
                buffer_images = list(imgs)

    if buffer_text:
        if len(buffer_text.split()) < min_words and final_paragraphs:
            final_paragraphs[-1]["text"] += f" {buffer_text}"
            final_paragraphs[-1]["images"].extend(buffer_images)
            final_paragraphs[-1]["images"] = list(set(final_paragraphs[-1]["images"]))
        else:
            final_paragraphs.append({
                "text": buffer_text,
                "images": list(set(buffer_images))
            })

    # Eğer metin bulunamadıysa (vektörel çizim veya taranmış PDF ise) AI Görsel Moduna geç
    if not final_paragraphs:
        return prepare_scanned_pdf_pages(pdf_path, target_pages)

    return final_paragraphs


def prepare_scanned_pdf_pages(pdf_path: str, target_pages: Optional[List[int]] = None) -> List[Dict[str, Any]]:
    """
    Eğer PDF içinde doğrudan okunabilir metin yoksa (vektörel eğri veya taranmış resimse),
    belirtilen sayfaları yüksek çözünürlükte PNG olarak kaydeder ve AI Vision moduna hazırlar.
    """
    doc = pymupdf.open(pdf_path)
    pages_to_process = target_pages if target_pages is not None else list(range(len(doc)))
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    root_dir = get_app_dir()
    scanned_dir = os.path.join(root_dir, "data", "scanned_pages", re.sub(r'\W+', '_', base_name))
    os.makedirs(scanned_dir, exist_ok=True)

    vision_chunks: List[Dict[str, Any]] = []

    for page_idx in pages_to_process:
        page = doc[page_idx]
        pix = page.get_pixmap(dpi=150)
        img_filename = f"page_{page_idx+1}.png"
        img_path = os.path.join(scanned_dir, img_filename)
        pix.save(img_path)

        vision_chunks.append({
            "text": f"[Sayfa {page_idx+1} - AI Görsel Okuma]",
            "page_image": img_path,
            "images": [img_path],
            "page_num": page_idx + 1,
            "is_vision": True
        })

    doc.close()
    return vision_chunks

