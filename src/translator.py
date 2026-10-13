import time
import json
import requests
from typing import Optional, Tuple, Callable, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from google import genai
from google.genai import types

from src import database
from src.logger import logger

# Akademik Çeviri için Standart Sistem Talimatı (Prompt)
ACADEMIC_SYSTEM_PROMPT = (
    "You are an expert academic translator specializing in scholarly literature. "
    "Your task is to translate the given English academic text into formal, clear, and precise "
    "academic Turkish (akademik literatür Türkçesi).\n\n"
    "Strict Rules to Follow:\n"
    "1. Preserve all citations, reference numbers (e.g., [1], [2], [10-14], (Smith et al., 2024)), "
    "and footnotes exactly as they appear in the original text.\n"
    "2. Keep mathematical formulas, symbols ($x$, \\alpha, \\pm, etc.), units, and variable names unchanged.\n"
    "3. Translate scientific, engineering, medical, and specialized technical terms accurately according to established Turkish academic conventions.\n"
    "4. If a block contains bracketed tags such as '[Şekil/Tablo Verisi: ...]', translate the descriptive text inside while keeping the tag structure intact.\n"
    "5. Return ONLY the translated Turkish text. Do NOT add any conversational remarks, commentary, explanations, or prefixes like 'İşte çeviriniz:'."
)

DEFAULT_GEMINI_MODELS = [
    "gemini-flash-latest",
    "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


class TranslationEngine:
    def __init__(
        self,
        provider: str = "gemini",
        api_key: str = "",
        model_name: str = "gemini-flash-latest",
        base_url: Optional[str] = None
    ):
        self.provider = provider.lower().strip()
        self.api_key = api_key.strip()
        self.model_name = model_name.strip()
        self.base_url = (base_url or "").strip()

    def get_system_prompt_with_glossary(self) -> str:
        """Sözlükteki özel terimleri sistem talimatına ekler."""
        glossary_text = database.format_glossary_for_prompt()
        if glossary_text:
            return f"{ACADEMIC_SYSTEM_PROMPT}\n\n{glossary_text}"
        return ACADEMIC_SYSTEM_PROMPT

    def translate_single_chunk(
        self,
        text: str,
        max_retries: int = 4,
        base_delay: float = 2.0,
        use_cache: bool = True
    ) -> Tuple[str, bool]:
        """
        Tek bir metin bloğunu çevirir.
        Dönüş: (translated_text, is_cached)
        """
        if not text or not text.strip():
            return "", False

        # 1. Önbellek Kontrolü (SHA-256)
        if use_cache:
            cached = database.get_cached_translation(text, self.model_name)
            if cached:
                return cached, True

        last_error = None
        for attempt in range(max_retries):
            try:
                if self.provider == "gemini":
                    translated = self._call_gemini(text)
                elif self.provider in ["openai", "openai_compatible", "custom"]:
                    translated = self._call_openai_compatible(text)
                else:
                    raise ValueError(f"Desteklenmeyen sağlayıcı: {self.provider}")

                # Önbelleğe kaydet
                if use_cache and translated:
                    database.set_cached_translation(text, translated, self.model_name)

                return translated, False

            except Exception as e:
                last_error = e
                err_str = str(e).lower()
                is_rate_limit = "429" in err_str or "resource_exhausted" in err_str or "quota" in err_str or "too many requests" in err_str

                if attempt < max_retries - 1:
                    wait_time = base_delay * (2 ** attempt)
                    if is_rate_limit:
                        wait_time += 2.0
                    time.sleep(wait_time)
                else:
                    break

        raise RuntimeError(f"Çeviri başarısız oldu ({max_retries} deneme yapıldı). Hata: {last_error}")

    def _call_gemini(self, text: str) -> str:
        """Google GenAI SDK kullanarak Gemini modellerini çağırır."""
        client = genai.Client(api_key=self.api_key)
        system_instruction = self.get_system_prompt_with_glossary()
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.1,
        )

        candidate_models = [self.model_name, "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-3.5-flash", "gemini-3.7-flash"]
        models_to_try = []
        for m in candidate_models:
            if m and m not in models_to_try:
                models_to_try.append(m)

        last_e = None
        for m in models_to_try:
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=text,
                    config=config,
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                last_e = e
                continue

        raise last_e or ValueError("Gemini API'den boş yanıt döndü.")

    def translate_scanned_page(self, image_path: str, max_retries: int = 4, base_delay: float = 2.0) -> List[Dict[str, str]]:
        """
        Vektörel çizim veya taranmış bir sayfa görselini multimodal yapay zeka ile okur,
        akademik sırayla paragrafları çıkarıp Türkçeye çevirir.
        """
        with open(image_path, "rb") as f:
            img_bytes = f.read()

        glossary_note = database.format_glossary_for_prompt()
        prompt = (
            "You are an expert academic translator specializing in scholarly literature.\n"
            "Read the academic text from this page image in correct academic reading order.\n"
            "Translate each section or paragraph into formal academic Turkish (literatür Türkçesi).\n"
            "Strict Rules:\n"
            "1. Preserve citations ([1], [2], names, dates) and math symbols.\n"
            "2. If an item is a Figure, Diagram, Chart, or Table, provide its outer visual bounding box coordinates: 'figure_box': [ymin, xmin, ymax, xmax] normalized from 0 to 1000 so the visual diagram can be cleanly cropped.\n"
            f"{glossary_note}\n"
            "3. Return ONLY a valid JSON array of objects in this exact format:\n"
            "[\n"
            '  {"source": "Original English text...", "translated": "Türkçe akademik çevirisi...", "figure_box": [ymin, xmin, ymax, xmax]}\n'
            "]\n"
            "Do not include any explanation or markdown formatting outside of the JSON array."
        )

        last_error = None
        candidate_models = [self.model_name, "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-3.5-flash", "gemini-3.7-flash"]
        models_to_try = []
        for m in candidate_models:
            if m and m not in models_to_try:
                models_to_try.append(m)

        for attempt in range(max_retries):
            for active_model in models_to_try:
                try:
                    client = genai.Client(api_key=self.api_key)
                    response = client.models.generate_content(
                        model=active_model,
                        contents=[
                            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                            prompt
                        ],
                        config=types.GenerateContentConfig(temperature=0.1)
                    )
                    if response and response.text:
                        clean_txt = response.text.strip()
                        if clean_txt.startswith("```json"):
                            clean_txt = clean_txt[7:]
                        if clean_txt.startswith("```"):
                            clean_txt = clean_txt[3:]
                        if clean_txt.endswith("```"):
                            clean_txt = clean_txt[:-3]
                        clean_txt = clean_txt.strip()

                        start_idx = clean_txt.find("[")
                        end_idx = clean_txt.rfind("]")
                        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                            clean_txt = clean_txt[start_idx:end_idx + 1]

                        data = json.loads(clean_txt)
                        if isinstance(data, list):
                            return data
                        elif isinstance(data, dict):
                            return [data]
                except Exception as e:
                    last_error = e
                    continue

            if attempt < max_retries - 1:
                time.sleep(base_delay * (2 ** attempt))

        raise RuntimeError(f"Sayfa görseli çevrilemedi: {last_error}")

    def _call_openai_compatible(self, text: str) -> str:
        """OpenAI uyumlu REST uç noktalarını çağırır."""
        url = self.base_url.rstrip("/") if self.base_url else "https://api.openai.com/v1"
        if not url.endswith("/chat/completions"):
            url = f"{url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        system_instruction = self.get_system_prompt_with_glossary()
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": text},
            ],
            "temperature": 0.1,
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code != 200:
            raise RuntimeError(f"API Hatası [{resp.status_code}]: {resp.text}")

        data = resp.json()
        translated_text = data["choices"][0]["message"]["content"]
        return translated_text.strip()

    def test_connection(self) -> Tuple[bool, str]:
        """API anahtarını ve model erişimini test eder."""
        test_text = "This is a test of the academic translation system."
        try:
            result, _ = self.translate_single_chunk(test_text, max_retries=2, base_delay=1.0, use_cache=False)
            if result:
                return True, "Bağlantı başarılı! Model yanıt verdi."
            return False, "API boş yanıt döndürdü."
        except Exception as e:
            return False, f"Bağlantı hatası: {str(e)}"


def test_api_credentials(
    provider: str,
    api_key: str,
    model_name: str,
    base_url: Optional[str] = None
) -> Tuple[bool, str]:
    engine = TranslationEngine(
        provider=provider,
        api_key=api_key,
        model_name=model_name,
        base_url=base_url
    )
    return engine.test_connection()
