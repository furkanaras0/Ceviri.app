import sqlite3
import os
import json
from typing import Optional, List, Dict, Any
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
    """Veritabanı tablolarını (settings ve translations) oluşturur ve günceller."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. settings tablosu (BYOK API anahtarı ve tercihler için)
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

        # Eğer eski veritabanında image_paths kolonu yoksa ekle (Migration)
        cursor.execute("PRAGMA table_info(translations)")
        columns = [row["name"] for row in cursor.fetchall()]
        if "image_paths" not in columns:
            cursor.execute("ALTER TABLE translations ADD COLUMN image_paths TEXT")
        
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


def delete_setting(key: str, db_path: Optional[str] = None) -> None:
    """Belirtilen ayar anahtarını siler."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
        conn.commit()


# ==========================================
# Çeviriler (Translations) Fonksiyonları
# ==========================================

def save_translation(
    file_name: str,
    source_paragraph: str,
    translated_paragraph: str,
    image_paths: Optional[List[str]] = None,
    db_path: Optional[str] = None
) -> int:
    """
    Çevrilen bir paragrafı ve varsa ilişkili görsel yollarını anlık olarak veritabanına kaydeder (Fail-Safe).
    Oluşturulan kaydın id değerini döndürür.
    """
    img_json = json.dumps(image_paths) if image_paths else "[]"
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


def get_all_files(db_path: Optional[str] = None) -> List[str]:
    """Çevirisi yapılmış benzersiz dosya adlarının listesini döndürür."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT file_name FROM translations ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [row["file_name"] for row in rows]


def get_history_summary(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Geçmiş çeviriler ekranı için tüm dosyaların özet bilgilerini döndürür.
    (Dosya adı, toplam çevrilen paragraf sayısı, son işlem tarihi)
    """
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
