import sqlite3
import os
import json
import hashlib
from typing import Optional, List, Dict, Any, Tuple
from src.paths import get_app_dir

DEFAULT_DB_NAME = "translator_data.db"


def get_db_path(db_name: str = DEFAULT_DB_NAME) -> str:
    """Veritabanının data/ klasöründe bulunmasını sağlar ve yolunu döndürür."""
    base_dir = get_app_dir()
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, db_name)


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Yeni bir SQLite bağlantısı oluşturur ve satırları sözlük benzeri erişilebilir yapar."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Veritabanı tablolarını (settings, translations, translation_cache, glossary) oluşturur ve günceller."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # 1. settings tablosu (BYOK API anahtarı ve tercihler)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # 2. translations tablosu (anlık çeviri ve fail-safe için)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                source_paragraph TEXT NOT NULL,
                translated_paragraph TEXT NOT NULL,
                image_paths TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Migration: image_paths kolonu
        cursor.execute("PRAGMA table_info(translations)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "image_paths" not in columns:
            cursor.execute("ALTER TABLE translations ADD COLUMN image_paths TEXT")

        # 3. translation_cache tablosu (Paragraf düzeyinde SHA-256 önbellek)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS translation_cache (
                text_hash TEXT PRIMARY KEY,
                source_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                model_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. glossary tablosu (Özel Akademik Terim Sözlüğü)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS glossary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term_en TEXT NOT NULL UNIQUE COLLATE NOCASE,
                term_tr TEXT NOT NULL,
                category TEXT DEFAULT 'Genel',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()


# ==========================================
# Ayarlar (Settings) Fonksiyonları
# ==========================================

def get_setting(key: str, default: Optional[str] = None, db_path: Optional[str] = None) -> Optional[str]:
    """Belirtilen anahtara ait değeri döndürür. Bulunamazsa default değerini döndürür."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row["value"]
        return default


def set_setting(key: str, value: str, db_path: Optional[str] = None) -> None:
    """Ayar değerini kaydeder veya günceller (Upsert)."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """, (key, value))
        conn.commit()


# ==========================================
# Çeviri Kayıtları (Translations) Fonksiyonları
# ==========================================

def save_translation(
    file_name: str,
    source_paragraph: str,
    translated_paragraph: str,
    image_paths: Optional[List[str]] = None,
    db_path: Optional[str] = None
) -> int:
    """Tek bir çeviri kaydını SQLite veritabanına ekler."""
    img_json = json.dumps(image_paths or [], ensure_ascii=False)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO translations (file_name, source_paragraph, translated_paragraph, image_paths)
            VALUES (?, ?, ?, ?)
        """, (file_name, source_paragraph, translated_paragraph, img_json))
        conn.commit()
        return cursor.lastrowid


def get_translations_by_file(file_name: str, db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Belirli bir dosya için kaydedilmiş tüm çevirileri kronolojik sırayla döndürür."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, file_name, source_paragraph, translated_paragraph, image_paths, created_at
            FROM translations
            WHERE file_name = ?
            ORDER BY id ASC
        """, (file_name,))
        rows = cursor.fetchall()

        result = []
        for r in rows:
            item = dict(r)
            try:
                item["image_paths"] = json.loads(item.get("image_paths") or "[]")
            except Exception:
                item["image_paths"] = []
            result.append(item)
        return result


def clear_translations_for_file(file_name: str, db_path: Optional[str] = None) -> int:
    """Belirtilen dosyaya ait tüm çeviri kayıtlarını siler."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM translations WHERE file_name = ?", (file_name,))
        conn.commit()
        return cursor.rowcount


def get_history_summary(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Tüm kayıtlı dosyaların özet bilgilerini döndürür."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                file_name,
                COUNT(id) as total_paragraphs,
                MAX(created_at) as last_updated
            FROM translations
            GROUP BY file_name
            ORDER BY last_updated DESC
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


# ==========================================
# Önbellek (SHA-256 Translation Cache)
# ==========================================

def calculate_text_hash(text: str) -> str:
    """Metnin boşlukları normalize edilmiş SHA-256 özetini üretir."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_cached_translation(text: str, model_name: Optional[str] = None, db_path: Optional[str] = None) -> Optional[str]:
    """Daha önce çevrilmiş paragraf varsa önbellekten döndürür."""
    h = calculate_text_hash(text)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        if model_name:
            cursor.execute("SELECT translated_text FROM translation_cache WHERE text_hash = ? AND model_name = ?", (h, model_name))
        else:
            cursor.execute("SELECT translated_text FROM translation_cache WHERE text_hash = ?", (h,))
        row = cursor.fetchone()
        if row:
            return row["translated_text"]
        return None


def set_cached_translation(text: str, translated: str, model_name: str, db_path: Optional[str] = None) -> None:
    """Çevrilen paragrafı önbelleğe kaydeder."""
    h = calculate_text_hash(text)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO translation_cache (text_hash, source_text, translated_text, model_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(text_hash) DO UPDATE SET translated_text = excluded.translated_text, model_name = excluded.model_name
        """, (h, text.strip(), translated.strip(), model_name))
        conn.commit()


def get_cache_count(db_path: Optional[str] = None) -> int:
    """Önbelleğe kaydedilmiş toplam benzersiz paragraf sayısını döndürür."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM translation_cache")
        row = cursor.fetchone()
        return row["cnt"] if row else 0


def clear_cache(db_path: Optional[str] = None) -> int:
    """Tüm çeviri önbelleğini temizler."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM translation_cache")
        conn.commit()
        return cursor.rowcount


# ==========================================
# Özel Akademik Terim Sözlüğü (Glossary)
# ==========================================

def get_all_glossary_terms(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Tüm kayıtlı sözlük terimlerini listeler."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, term_en, term_tr, category, created_at FROM glossary ORDER BY term_en ASC")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]


def add_glossary_term(term_en: str, term_tr: str, category: str = "Genel", db_path: Optional[str] = None) -> bool:
    """Yeni bir terim ekler veya varsa günceller."""
    en = term_en.strip()
    tr = term_tr.strip()
    if not en or not tr:
        return False
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO glossary (term_en, term_tr, category)
            VALUES (?, ?, ?)
            ON CONFLICT(term_en) DO UPDATE SET term_tr = excluded.term_tr, category = excluded.category
        """, (en, tr, category.strip() or "Genel"))
        conn.commit()
        return True


def delete_glossary_term(term_id: int, db_path: Optional[str] = None) -> bool:
    """ID'ye göre sözlük terimini siler."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM glossary WHERE id = ?", (term_id,))
        conn.commit()
        return cursor.rowcount > 0


def format_glossary_for_prompt(db_path: Optional[str] = None) -> str:
    """LLM sistem talimatı için terim listesini formatlar."""
    terms = get_all_glossary_terms(db_path)
    if not terms:
        return ""

    lines = ["Mandatory Academic Terminology Glossary (Translate these exact terms as specified):"]
    for t in terms:
        lines.append(f"- '{t['term_en']}' -> '{t['term_tr']}'")
    return "\n".join(lines)
