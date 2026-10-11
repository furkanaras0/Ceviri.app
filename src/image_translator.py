import os
import json
import re
from typing import Optional, List, Dict, Any, Tuple
from collections import Counter
from PIL import Image, ImageDraw, ImageFont

# Windows standart font yolları
FONT_REGULAR_PATHS = [
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\calibri.ttf"
]
FONT_BOLD_PATHS = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\calibrib.ttf"
]


def _get_font(is_bold: bool, size: int) -> ImageFont.FreeTypeFont:
    """Sistemde mevcut olan en uygun TrueType fontunu yükler."""
    font_paths = FONT_BOLD_PATHS if is_bold else FONT_REGULAR_PATHS
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    try:
        return ImageFont.load_default()
    except Exception:
        return None


def sample_edge_background(
    im: Image.Image,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    fallback: Tuple[int, int, int] = (255, 255, 255)
) -> Tuple[int, int, int]:
    """
    Kutunun çevresindeki (kenarlardaki) pikselleri örnekleyerek zemin rengini tespit eder.
    Böylece çizim/şema zeminleri orijinal renk tonuyla pürüzsüzce eşleşir.
    """
    W, H = im.size
    sample_pts = [
        (max(0, x0 - 4), max(0, y0 - 4)),
        (min(W - 1, x1 + 4), max(0, y0 - 4)),
        (max(0, x0 - 4), min(H - 1, y1 + 4)),
        (min(W - 1, x1 + 4), min(H - 1, y1 + 4)),
        (max(0, x0 - 4), (y0 + y1) // 2),
        (min(W - 1, x1 + 4), (y0 + y1) // 2),
        ((x0 + x1) // 2, max(0, y0 - 4)),
        ((x0 + x1) // 2, min(H - 1, y1 + 4)),
    ]
    pixels = []
    for p in sample_pts:
        try:
            px = im.getpixel(p)
            if isinstance(px, (tuple, list)):
                pixels.append(px[:3])
            elif isinstance(px, int):
                pixels.append((px, px, px))
        except Exception:
            continue

    if pixels:
        return Counter(pixels).most_common(1)[0][0]
    return fallback


def _wrap_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: Any,
    max_width: int
) -> List[str]:
    """Metni verilen piksel genişliğini aşmayacak şekilde satırlara böler."""
    words = text.split()
    if not words:
        return []
    lines = []
    curr = []
    for w in words:
        curr.append(w)
        try:
            bbox = draw.textbbox((0, 0), " ".join(curr), font=font)
            w_line = bbox[2] - bbox[0]
        except Exception:
            w_line = len(" ".join(curr)) * 8

        if w_line > max_width and len(curr) > 1:
            curr.pop()
            lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))
    return lines


def _parse_hex_color(color_str: str, default: Tuple[int, int, int] = (0, 0, 0)) -> Tuple[int, int, int]:
    """Hex renk kodunu (örn: #0088CC veya #FFFFFF) RGB tuple'a dönüştürür."""
    if not color_str:
        return default
    c = color_str.strip().lstrip("#")
    if len(c) == 6:
        try:
            return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
        except Exception:
            pass
    return default


def translate_figure_image(
    image_path: str,
    provider: str,
    api_key: str,
    model_name: str,
    base_url: str = ""
) -> str:
    """
    Bir grafik/şema görselini analiz eder, içindeki İngilizce metinleri tespit edip
    orijinal çizgileri, okları ve kutuları bozmadan zemin rengiyle temizler,
    aynı koordinatlara Türkçe çevirisini yazar ve oluşturulan '_tr.png' dosya yolunu döner.
    
    Hata durumunda veya metin yoksa orijinal 'image_path' döner (fail-safe).
    """
    if not image_path or not os.path.exists(image_path):
        return image_path

    # Zaten çevrilmiş bir görselse tekrar çevirme
    if image_path.endswith("_tr.png") or image_path.endswith("_tr.jpg"):
        return image_path

    try:
        orig_im = Image.open(image_path)
    except Exception:
        return image_path

    # Çok küçük resimleri veya tam sayfa zemin taramalarını atla
    if orig_im.width < 120 or orig_im.height < 60:
        return image_path
    if orig_im.width > 1200 and orig_im.height > 1600:
        return image_path

    # 1. Gemini / LLM Vision ile görseldeki metinleri tespit et ve çevir
    detected_items = _detect_and_translate_text_regions(
        image_path=image_path,
        provider=provider,
        api_key=api_key,
        model_name=model_name,
        base_url=base_url
    )

    if not detected_items:
        return image_path

    # 2. Pillow ile görsel üzerinde hassas inpainting ve metin çizimi
    try:
        im = orig_im.convert("RGB")
        draw = ImageDraw.Draw(im)
        W, H = im.size

        for item in detected_items:
            box_2d = item.get("box_2d") or [0, 0, 0, 0]
            if len(box_2d) != 4:
                continue

            ymin, xmin, ymax, xmax = box_2d
            x0 = int(xmin * W / 1000.0)
            y0 = int(ymin * H / 1000.0)
            x1 = int(xmax * W / 1000.0)
            y1 = int(ymax * H / 1000.0)

            orig_txt = item.get("original_text", "").strip()
            tr_txt = item.get("translated_text", "").strip()
            if not tr_txt:
                continue

            # X ve Y gibi tek harfli düğüm/değişken sembollerini eğer değişmediyse bozma
            if orig_txt in ["X", "Y", "Z", "A", "B"] and tr_txt == orig_txt:
                continue

            # Kenar örneklemesiyle arka plan rengini yakala
            bg_color = sample_edge_background(im, x0, y0, x1, y1)

            # Yazı rengini parse et (veya arka plan koyuluğuna göre kontrast seç)
            fg_hex = item.get("text_color")
            fg_color = _parse_hex_color(fg_hex, default=(17, 24, 39))

            # Kontrast güvenlik kontrolü: Eğer zemin çok koyu ve fg siyahsa beyaza çevir
            bg_luminance = 0.299 * bg_color[0] + 0.587 * bg_color[1] + 0.114 * bg_color[2]
            if bg_luminance < 90 and fg_color == (17, 24, 39):
                fg_color = (255, 255, 255)

            is_bold = bool(item.get("is_bold", False))

            # Eski metin alanını zemin rengiyle temizle (hafif padding ile tam silme)
            pad_x = 2
            pad_y = 2
            draw.rectangle(
                [max(0, x0 - pad_x), max(0, y0 - pad_y), min(W, x1 + pad_x), min(H, y1 + pad_y)],
                fill=bg_color
            )

            box_w = max(x1 - x0, 20)
            box_h = max(y1 - y0, 15)

            # Kutunun içine tam sığacak ideal font boyutunu ve satır kaydırmayı hesapla
            font, wrapped_lines, line_h = _find_best_fitting_font(
                draw=draw,
                text=tr_txt,
                is_bold=is_bold,
                box_w=box_w,
                box_h=box_h
            )

            curr_y = y0 + 1
            for wl in wrapped_lines:
                draw.text((x0, curr_y), wl, fill=fg_color, font=font)
                curr_y += line_h

        # 3. Çevrilmiş görseli kaydet
        dir_name = os.path.dirname(image_path)
        base_name, _ = os.path.splitext(os.path.basename(image_path))
        out_path = os.path.join(dir_name, f"{base_name}_tr.png")
        im.save(out_path, format="PNG")
        return out_path

    except Exception:
        return image_path


def _find_best_fitting_font(
    draw: ImageDraw.ImageDraw,
    text: str,
    is_bold: bool,
    box_w: int,
    box_h: int,
    max_font_size: int = 24,
    min_font_size: int = 9
) -> Tuple[Any, List[str], int]:
    """
    Kutunun piksel sınırları (box_w, box_h) içine tam sığacak en büyük ve en okunaklı font boyutunu bulur.
    Metin satırlarını kelime bazlı kaydırarak kutu dışına taşmasını engeller.
    """
    for font_size in range(max_font_size, min_font_size - 1, -1):
        font = _get_font(is_bold=is_bold, size=font_size)
        raw_paragraphs = text.split("\n")
        all_lines = []
        for p in raw_paragraphs:
            all_lines.extend(_wrap_text_to_width(draw, p, font, box_w + 4))

        try:
            line_height = font.getbbox("Ay")[3] + 3
        except Exception:
            line_height = font_size + 3

        total_text_h = len(all_lines) * line_height
        if total_text_h <= box_h * 1.05:
            return font, all_lines, line_height

    # En küçük font boyutu ile güvenli dönüş
    font = _get_font(is_bold=is_bold, size=min_font_size)
    all_lines = []
    for p in text.split("\n"):
        all_lines.extend(_wrap_text_to_width(draw, p, font, box_w + 4))
    line_height = min_font_size + 3
    return font, all_lines, line_height



def _detect_and_translate_text_regions(
    image_path: str,
    provider: str,
    api_key: str,
    model_name: str,
    base_url: str = ""
) -> List[Dict[str, Any]]:
    """
    Gemini / LLM Vision modeline görseli göndererek tüm metin kutularının koordinatlarını,
    arka plan/yazı rengini ve akademik Türkçe çevirilerini JSON formatında alır.
    """
    prompt = """You are an expert academic translator and visual layout specialist.
Analyze this academic figure, chart, table, or diagram.
Detect every single English text label, title, subtitle, column heading, and explanatory note that should be translated into academic Turkish.
Do NOT translate single mathematical variable letters like X or Y if they are unchanged node symbols in a graph.
For EACH text element, provide:
1. "box_2d": [ymin, xmin, ymax, xmax] coordinates normalized from 0 to 1000.
2. "original_text": The exact English text.
3. "translated_text": The precise academic Turkish translation.
4. "text_color": Hex color of the text (e.g. #FFFFFF, #000000, #0088CC).
5. "is_bold": boolean (true if bold or title, false otherwise).

Return ONLY a valid JSON array of objects. Do not wrap in markdown or backticks.
Example output format:
[
  {"box_2d": [20, 15, 60, 180], "original_text": "FIGURE 1", "translated_text": "ŞEKİL 1", "text_color": "#FFFFFF", "is_bold": true}
]
If there is no text in the image, return []."""

    # Gemini modellerinde kota/durum dayanıklılığı için fallback listesi
    fallback_models = [model_name, "gemini-3.5-flash", "gemini-3.7-flash", "gemini-flash-lite-latest", "gemini-flash-latest"]
    # Tekrarları ayıkla ama sırayı koru
    seen = set()
    candidate_models = []
    for m in fallback_models:
        if m and m not in seen:
            candidate_models.append(m)
            seen.add(m)

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    mime_type = "image/png"
    if image_path.lower().endswith((".jpg", ".jpeg")):
        mime_type = "image/jpeg"

    if provider == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        for cand_model in candidate_models:
            try:
                response = client.models.generate_content(
                    model=cand_model,
                    contents=[
                        types.Part.from_bytes(data=img_bytes, mime_type=mime_type),
                        prompt
                    ]
                )
                raw_text = response.text or ""
                return _clean_and_parse_json(raw_text)
            except Exception:
                continue

    else:
        # OpenAI Uyumlu Vision sağlayıcısı
        import base64
        from openai import OpenAI
        b64_img = base64.b64encode(img_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64_img}"

        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = OpenAI(**client_kwargs)

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}}
                        ]
                    }
                ],
                temperature=0.1,
            )
            raw_text = response.choices[0].message.content or ""
            return _clean_and_parse_json(raw_text)
        except Exception:
            pass

    return []


def _clean_and_parse_json(raw_text: str) -> List[Dict[str, Any]]:
    """Model yanıtından JSON dizisini ayıklar ve listeye dönüştürür."""
    if not raw_text:
        return []
    clean = raw_text.strip()
    clean = re.sub(r"^```(?:json)?\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*```$", "", clean)

    # Dizi sınırlarını bul: '[' ve ']'
    start_idx = clean.find("[")
    end_idx = clean.rfind("]")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        clean = clean[start_idx:end_idx + 1]

    try:
        data = json.loads(clean)
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []
