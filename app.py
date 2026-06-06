import os
import re
import json
import time
import sqlite3
import threading
import traceback
import smtplib
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from html import unescape
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify, render_template, request, redirect

VERSION = "v22-db-temiz-baslatma"
APP_NAME = "Araç Avcısı"

DATA_DIR = os.getenv("DATA_DIR", "data") or "data"
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception:
    # Render Free plan veya eski /data ayarı sorun çıkarırsa uygulama düşmesin.
    DATA_DIR = "data"
    os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "arac_avcisi.sqlite3")

DEFAULT_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "4") or 4)
SCHEDULER_TICK_MINUTES = int(os.getenv("SCHEDULER_TICK_MINUTES", "15") or 15)
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") != "0"

REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "18") or 18)
JINA_TIMEOUT = int(os.getenv("JINA_TIMEOUT", "24") or 24)
MAX_ITEMS_PER_SOURCE = int(os.getenv("MAX_ITEMS_PER_SOURCE", "12") or 12)
MAX_TOTAL_ITEMS = int(os.getenv("MAX_TOTAL_ITEMS", "60") or 60)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "arac-avcisi-local-secret")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.7,en;q=0.6",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
})

BRANDS = {
    "Volkswagen": {
        "Tiguan": [
            "Farketmez",
            "1.4 TSI Comfortline",
            "1.4 TSI Highline",
            "1.4 TSI Trend & Fun",
            "1.4 TSI Sport & Style",
            "1.5 TSI Comfortline",
            "1.5 TSI Highline",
            "1.5 TSI R-Line",
            "2.0 TDI Comfortline",
            "2.0 TDI Highline",
        ],
        "Passat": ["Farketmez", "1.4 TSI Comfortline", "1.5 TSI Business", "1.6 TDI Comfortline", "2.0 TDI Highline"],
        "Golf": ["Farketmez", "1.0 TSI Comfortline", "1.2 TSI Comfortline", "1.4 TSI Highline", "1.6 TDI Comfortline"],
    },
    "Honda": {
        "Civic": ["Farketmez", "1.6 Eco Elegance", "1.6 Eco Executive", "1.6 i-VTEC Elegance", "1.5 VTEC Turbo"],
        "CR-V": ["Farketmez", "1.5 VTEC Turbo Executive", "2.0 i-VTEC Elegance"],
    },
    "Toyota": {
        "Corolla": ["Farketmez", "1.5 Vision", "1.5 Dream", "1.6 Flame", "1.6 Passion"],
        "C-HR": ["Farketmez", "1.8 Hybrid Flame", "1.8 Hybrid Passion"],
    },
    "Renault": {
        "Megane": ["Farketmez", "1.3 TCe Joy", "1.5 dCi Touch", "1.5 Blue dCi Icon"],
        "Clio": ["Farketmez", "1.0 TCe Joy", "1.0 TCe Touch", "1.5 dCi Icon"],
    },
    "Ford": {
        "Kuga": ["Farketmez", "1.5 EcoBoost Style", "1.5 EcoBoost Titanium", "1.5 EcoBlue Titanium"],
        "Focus": ["Farketmez", "1.5 TDCi Trend X", "1.5 EcoBlue Titanium"],
    },
    "Hyundai": {
        "Tucson": ["Farketmez", "1.6 T-GDI Elite", "1.6 CRDi Elite", "1.6 T-GDI N Line"],
        "i20": ["Farketmez", "1.4 MPI Jump", "1.4 MPI Style", "1.0 T-GDI Elite"],
    },
    "Kia": {
        "Sportage": ["Farketmez", "1.6 GDI Comfort", "1.6 T-GDI Prestige", "1.6 CRDi Elegance"],
    },
}

CITIES = ["Tüm Türkiye", "İstanbul", "Ankara", "İzmir", "Kocaeli", "Bursa", "Konya", "Eskişehir", "Sakarya", "Yalova", "Düzce", "Balıkesir", "Tokat", "Antalya", "Adana", "Kayseri", "Gaziantep"]
INTERVALS = [1, 2, 3, 4, 6, 8, 12, 24, 48, 72]
FUELS = ["Farketmez", "Benzin", "Dizel", "Benzin & LPG", "Hibrit", "Elektrik"]
TRANSMISSIONS = ["Farketmez", "Otomatik", "Yarı Otomatik", "Manuel"]

@dataclass
class Source:
    key: str
    name: str
    base: str
    search_mode: str = "direct_and_jina"

SOURCES = [
    Source("sahibinden", "Sahibinden", "https://www.sahibinden.com"),
    Source("arabam", "Arabam", "https://www.arabam.com"),
    Source("otoplus", "Otoplus", "https://www.otoplus.com"),
    Source("otokoc", "Otokoç 2. El", "https://www.otokocikinciel.com"),
    Source("vavacars", "VavaCars", "https://tr.vava.cars"),
    Source("arabasepeti", "Araba Sepeti", "https://www.arabasepeti.com"),
    Source("arabalar", "Arabalar.com", "https://www.arabalar.com.tr"),
    Source("letgo", "Letgo", "https://www.letgo.com"),
    Source("facebook", "Facebook Marketplace", "https://www.facebook.com"),
]
SOURCE_MAP = {s.key: s for s in SOURCES}

VEHICLE_CATEGORY = {
    ("Volkswagen", "Tiguan"): "suv",
    ("Ford", "Kuga"): "suv",
    ("Hyundai", "Tucson"): "suv",
    ("Kia", "Sportage"): "suv",
    ("Toyota", "C-HR"): "suv",
    ("Honda", "CR-V"): "suv",
}

BAD_TITLE_PARTS = [
    "filtrele", "arama", "favori arama", "araçları listeleniyor", "sonuç bulunamadı",
    "mobil uygulamalar", "anasayfa", "giriş yap", "üye ol", "çerez", "yardım",
    "hemen sat", "aracımı nasıl satarım", "karşılaştır", "favorilerimde", "gizle", "göster",
]

# ------------------------- DB -------------------------

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []


def add_column_if_missing(con, table, col, coldef):
    cols = table_columns(con, table)
    if col not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coldef}")


def init_db():
    with db() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS watches(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                package TEXT DEFAULT 'Farketmez',
                city TEXT DEFAULT 'Tüm Türkiye',
                min_year INTEGER,
                max_year INTEGER,
                max_km INTEGER,
                min_price INTEGER,
                max_price INTEGER,
                fuel TEXT DEFAULT 'Farketmez',
                transmission TEXT DEFAULT 'Farketmez',
                sources TEXT DEFAULT '[]',
                interval_hours INTEGER DEFAULT 4,
                active INTEGER DEFAULT 1,
                email TEXT,
                telegram_chat_id TEXT,
                created_at TEXT,
                updated_at TEXT,
                last_checked_at TEXT,
                next_check_at TEXT,
                last_status TEXT DEFAULT '',
                last_seen_count INTEGER DEFAULT 0,
                last_new_count INTEGER DEFAULT 0,
                last_drop_count INTEGER DEFAULT 0,
                checking INTEGER DEFAULT 0
            )
        """)
        # migrations for older DBs
        for col, coldef in {
            "name": "TEXT", "package": "TEXT DEFAULT 'Farketmez'", "city": "TEXT DEFAULT 'Tüm Türkiye'",
            "min_year": "INTEGER", "max_year": "INTEGER", "max_km": "INTEGER", "min_price": "INTEGER", "max_price": "INTEGER",
            "fuel": "TEXT DEFAULT 'Farketmez'", "transmission": "TEXT DEFAULT 'Farketmez'", "sources": "TEXT DEFAULT '[]'",
            "interval_hours": "INTEGER DEFAULT 4", "active": "INTEGER DEFAULT 1", "email": "TEXT", "telegram_chat_id": "TEXT",
            "created_at": "TEXT", "updated_at": "TEXT", "last_checked_at": "TEXT", "next_check_at": "TEXT", "last_status": "TEXT DEFAULT ''",
            "last_seen_count": "INTEGER DEFAULT 0", "last_new_count": "INTEGER DEFAULT 0", "last_drop_count": "INTEGER DEFAULT 0", "checking": "INTEGER DEFAULT 0",
        }.items():
            add_column_if_missing(con, "watches", col, coldef)

        con.execute("""
            CREATE TABLE IF NOT EXISTS items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                title TEXT,
                price INTEGER,
                year INTEGER,
                km INTEGER,
                city TEXT,
                url TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                first_seen_at TEXT,
                last_seen_at TEXT,
                price_last INTEGER,
                is_active INTEGER DEFAULT 1,
                UNIQUE(watch_id, fingerprint)
            )
        """)
        for col, coldef in {
            "price_last": "INTEGER", "is_active": "INTEGER DEFAULT 1", "city": "TEXT", "year": "INTEGER", "km": "INTEGER",
        }.items():
            add_column_if_missing(con, "items", col, coldef)

        con.execute("""
            CREATE TABLE IF NOT EXISTS events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id INTEGER,
                event_type TEXT,
                source TEXT,
                title TEXT,
                price_old INTEGER,
                price_new INTEGER,
                url TEXT,
                created_at TEXT
            )
        """)
        con.commit()
        cleanup_bad_items(con)


def cleanup_bad_items(con=None):
    close = False
    if con is None:
        con = db(); close = True
    bad_like = ["%filtrele%", "%araçları listeleniyor%", "%sonuç bulunamadı%", "%aracımı nasıl satarım%", "%favori arama%"]
    for pat in bad_like:
        con.execute("DELETE FROM items WHERE lower(title) LIKE lower(?)", (pat,))
    # Remove obvious category URLs that were stored as fake listing items
    con.execute("DELETE FROM items WHERE source='otoplus' AND url NOT LIKE '%/ilan/%' AND title IN ('Volkswagen TIGUAN','VOLKSWAGEN TIGUAN','Filtrele')")
    con.commit()
    if close:
        con.close()


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

# ------------------------- Normalization -------------------------

def tr_lower(s: str) -> str:
    if not s:
        return ""
    return str(s).translate(str.maketrans("IİŞĞÜÖÇÂÎÛ", "ıişğüöçâîû")).lower()


def ascii_slug(s: str) -> str:
    s = tr_lower(s)
    repl = {"ı":"i", "ğ":"g", "ü":"u", "ş":"s", "ö":"o", "ç":"c", "â":"a", "î":"i", "û":"u", "&":" ", "+":" ", ".":" ", "/":" ", "-":" "}
    for k, v in repl.items():
        s = s.replace(k, v)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


def clean_text(s: str) -> str:
    s = unescape(s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def to_int(s) -> Optional[int]:
    if s is None:
        return None
    if isinstance(s, int):
        return s
    raw = str(s)
    # 1.650.000 TL -> 1650000, 98.202 km -> 98202
    nums = re.findall(r"\d+", raw)
    if not nums:
        return None
    val = int("".join(nums))
    return val


def price_to_int(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{5,9})\s*(?:TL|₺|TRY)", text, flags=re.I)
    if not m:
        return None
    return to_int(m.group(1))


def km_to_int(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{1,6})\s*(?:km|KM|Km)", text)
    if not m:
        return None
    return to_int(m.group(1))


def year_to_int(text: str) -> Optional[int]:
    if not text:
        return None
    # Prefer model years around car range
    years = [int(x) for x in re.findall(r"\b(19[8-9]\d|20[0-2]\d|2026)\b", text)]
    if not years:
        return None
    # most listings put year first. choose plausible newest not current date if multiple
    for y in years:
        if 1980 <= y <= 2026:
            return y
    return years[0]


def make_query(w: Dict) -> str:
    parts = [w.get("brand"), w.get("model")]
    pkg = w.get("package") or ""
    if pkg and pkg != "Farketmez":
        parts.append(pkg)
    city = w.get("city") or ""
    if city and city != "Tüm Türkiye":
        parts.append(city)
    if w.get("fuel") and w.get("fuel") != "Farketmez":
        parts.append(w.get("fuel"))
    if w.get("transmission") and w.get("transmission") != "Farketmez":
        parts.append(w.get("transmission"))
    return " ".join([p for p in parts if p]).strip()


def title_matches_watch(title: str, w: Dict) -> bool:
    if not title:
        return False
    low = tr_lower(title)
    brand = tr_lower(w.get("brand", ""))
    model = tr_lower(w.get("model", ""))
    if brand and brand not in low:
        # VW/Volkswagen tolerance
        if brand == "volkswagen" and not re.search(r"\b(vw|volkswagen)\b", low):
            return False
    if model and model not in low:
        return False
    pkg = tr_lower(w.get("package", ""))
    if pkg and pkg != "farketmez":
        # Match important tokens only; avoid insisting on every engine token
        tokens = [t for t in re.split(r"[^a-z0-9çğıöşü]+", pkg) if len(t) >= 3]
        key_tokens = tokens[-2:] if len(tokens) > 2 else tokens
        if key_tokens and not any(t in low for t in key_tokens):
            return False
    return True


def looks_bad_title(title: str) -> bool:
    low = tr_lower(title)
    if len(low) < 8:
        return True
    return any(p in low for p in BAD_TITLE_PARTS)


def apply_filters(item: Dict, w: Dict) -> bool:
    # Always require title to match; prevents site menus from becoming fake cars
    if not title_matches_watch(item.get("title", ""), w):
        return False
    if looks_bad_title(item.get("title", "")):
        return False
    # If value is present, it must pass. If missing, allow because search snippets can omit it.
    try:
        if item.get("price") is not None:
            if w.get("min_price") and item["price"] < int(w["min_price"]): return False
            if w.get("max_price") and item["price"] > int(w["max_price"]): return False
        if item.get("year") is not None:
            if w.get("min_year") and item["year"] < int(w["min_year"]): return False
            if w.get("max_year") and item["year"] > int(w["max_year"]): return False
        if item.get("km") is not None:
            if w.get("max_km") and item["km"] > int(w["max_km"]): return False
    except Exception:
        return False
    return True

# ------------------------- URL builders -------------------------

def is_suv(w: Dict) -> bool:
    return VEHICLE_CATEGORY.get((w.get("brand"), w.get("model"))) == "suv"


def arabam_category_path(w: Dict) -> str:
    base_cat = "arazi-suv-pick-up" if is_suv(w) else "otomobil"
    slug = "-".join([ascii_slug(w.get("brand", "")), ascii_slug(w.get("model", ""))])
    pkg = w.get("package") or ""
    if pkg and pkg != "Farketmez":
        slug += "-" + ascii_slug(pkg)
    return f"/ikinci-el/{base_cat}/{slug}"


def sahibinden_category_path(w: Dict) -> str:
    cat = "arazi-suv-pickup" if is_suv(w) else "otomobil"
    slug = "-".join([ascii_slug(w.get("brand", "")), ascii_slug(w.get("model", ""))])
    pkg = w.get("package") or ""
    if pkg and pkg != "Farketmez":
        slug += "-" + ascii_slug(pkg)
    path = f"/{cat}-{slug}"
    trans = tr_lower(w.get("transmission", ""))
    if "otomatik" in trans and "yarı" not in trans and "yari" not in trans:
        path += "/otomatik"
    elif "manuel" in trans:
        path += "/manuel"
    return path


def otoplus_path(w: Dict) -> str:
    brand = ascii_slug(w.get("brand", ""))
    model = ascii_slug(w.get("model", ""))
    pkg = ascii_slug(w.get("package", "")) if w.get("package") and w.get("package") != "Farketmez" else ""
    if brand == "volkswagen" and model == "tiguan" and pkg:
        if "14-tsi-comfortline" in pkg or "1-4-tsi-comfortline" in pkg:
            return "/volkswagen/tiguan/tiguan-1.4-tsi-bmt-125-comfortline"
        if "highline" in pkg:
            return "/volkswagen/tiguan/tiguan-1.4-tsi-act-bmt-150-dsg-highline"
    return f"/{brand}/{model}"


def direct_url(source_key: str, w: Dict) -> str:
    q = make_query(w)
    city = w.get("city")
    params = {}
    if w.get("min_price"): params["price_min"] = str(w.get("min_price"))
    if w.get("max_price"): params["price_max"] = str(w.get("max_price"))
    if w.get("min_year"): params["year_min"] = str(w.get("min_year"))
    if w.get("max_year"): params["year_max"] = str(w.get("max_year"))
    if w.get("max_km"): params["km_max"] = str(w.get("max_km"))

    if source_key == "sahibinden":
        # Sahibinden's exact hidden filter ids differ by category; use correct category path plus general params.
        p = sahibinden_category_path(w)
        sbp = {"query_text": q}
        if w.get("min_price"): sbp["price_min"] = str(w.get("min_price"))
        if w.get("max_price"): sbp["price_max"] = str(w.get("max_price"))
        if w.get("min_year"): sbp["a5_min"] = str(w.get("min_year"))
        if w.get("max_year"): sbp["a5_max"] = str(w.get("max_year"))
        if w.get("max_km"): sbp["a4_max"] = str(w.get("max_km"))
        return "https://www.sahibinden.com" + p + "?" + urlencode(sbp)
    if source_key == "arabam":
        url = "https://www.arabam.com" + arabam_category_path(w)
        ap = {}
        if w.get("city") and w.get("city") != "Tüm Türkiye": ap["city"] = w.get("city")
        if w.get("min_price"): ap["priceMin"] = str(w.get("min_price"))
        if w.get("max_price"): ap["priceMax"] = str(w.get("max_price"))
        if w.get("min_year"): ap["modelYearMin"] = str(w.get("min_year"))
        if w.get("max_year"): ap["modelYearMax"] = str(w.get("max_year"))
        if w.get("max_km"): ap["kmMax"] = str(w.get("max_km"))
        return url + ("?" + urlencode(ap) if ap else "")
    if source_key == "otoplus":
        url = "https://www.otoplus.com" + otoplus_path(w)
        op = {}
        if w.get("max_price"): op["price_max"] = str(w.get("max_price"))
        if w.get("min_year"): op["year_min"] = str(w.get("min_year"))
        if w.get("max_km"): op["km_max"] = str(w.get("max_km"))
        return url + ("?" + urlencode(op) if op else "")
    if source_key == "otokoc":
        return f"https://www.otokocikinciel.com/ikinci-el-{ascii_slug(w.get('brand',''))}-{ascii_slug(w.get('model',''))}?q={quote(q)}"
    if source_key == "vavacars":
        return f"https://tr.vava.cars/ikinci-el-araba?search={quote(q)}"
    if source_key == "arabasepeti":
        return f"https://www.arabasepeti.com/arama?search={quote(q)}"
    if source_key == "arabalar":
        return f"https://www.arabalar.com.tr/arama?search={quote(q)}"
    if source_key == "letgo":
        return f"https://www.letgo.com/tr-tr/arama?q={quote(q)}"
    if source_key == "facebook":
        return f"https://www.facebook.com/marketplace/search/?query={quote(q)}"
    return "https://www.google.com/search?q=" + quote(q)


def jina_site_query(source_key: str, w: Dict) -> str:
    q = make_query(w)
    # Keep the query compact; adding every numeric filter makes search engines return zero too often.
    year_part = f" {w.get('min_year')}" if w.get("min_year") else ""
    price_part = f" {w.get('max_price')} TL" if w.get("max_price") else ""
    site_map = {
        "sahibinden": "site:sahibinden.com/ilan/vasita",
        "arabam": "site:arabam.com/ilan",
        "otoplus": "site:otoplus.com volkswagen tiguan OR ilan",
        "otokoc": "site:otokocikinciel.com/ilan",
        "vavacars": "site:tr.vava.cars",
        "arabasepeti": "site:arabasepeti.com/ilan",
        "arabalar": "site:arabalar.com.tr/ilan",
        "letgo": "site:letgo.com",
        "facebook": "site:facebook.com/marketplace",
    }
    return f"{site_map.get(source_key, '')} {q}{year_part}{price_part} ikinci el".strip()

# ------------------------- Fetching / parsing -------------------------

def fetch_url(url: str) -> Tuple[int, str, str]:
    try:
        r = SESSION.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        text = r.text or ""
        return r.status_code, text, r.url
    except Exception as e:
        return 0, f"ERROR: {type(e).__name__}: {e}", url


def fetch_reader(url: str) -> Tuple[int, str]:
    try:
        rr = SESSION.get("https://r.jina.ai/" + url, timeout=JINA_TIMEOUT, headers={"Accept": "text/plain"})
        return rr.status_code, rr.text or ""
    except Exception as e:
        return 0, f"ERROR: {type(e).__name__}: {e}"


def fetch_jina_search(query: str) -> Tuple[int, str]:
    try:
        url = "https://s.jina.ai/" + quote(query)
        r = SESSION.get(url, timeout=JINA_TIMEOUT, headers={"Accept": "text/plain"})
        return r.status_code, r.text or ""
    except Exception as e:
        return 0, f"ERROR: {type(e).__name__}: {e}"


def extract_city(text: str) -> Optional[str]:
    if not text:
        return None
    low = tr_lower(text)
    for c in CITIES:
        if c != "Tüm Türkiye" and tr_lower(c) in low:
            return c
    # common pattern: price + date + city district
    return None


def canonical_url(url: str) -> str:
    if not url:
        return ""
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        return url
    # remove known tracking params
    q = []
    for kv in parsed.query.split("&") if parsed.query else []:
        if kv and not kv.lower().startswith(("utm_", "fbclid", "gclid")):
            q.append(kv)
    return parsed._replace(query="&".join(q), fragment="").geturl()


def fingerprint_for(source: str, url: str, title: str) -> str:
    cu = canonical_url(url)
    # Listing URLs are best fingerprint; category/search URLs need title too.
    if "/ilan/" in cu or "sahibinden.com/ilan" in cu:
        return f"{source}:{cu}"
    return f"{source}:{cu}:{ascii_slug(title)[:80]}"


def make_item(source_key: str, title: str, url: str, block: str = "") -> Dict:
    text = clean_text((title or "") + " " + (block or ""))
    return {
        "source": source_key,
        "title": clean_text(title)[:180],
        "price": price_to_int(text),
        "year": year_to_int(text),
        "km": km_to_int(text),
        "city": extract_city(text),
        "url": canonical_url(url),
    }


def parse_html_links(source_key: str, html: str, final_url: str, w: Dict) -> List[Dict]:
    items = []
    if not html or html.startswith("ERROR:"):
        return items
    soup = BeautifulSoup(html, "html.parser")
    base = f"{urlparse(final_url).scheme}://{urlparse(final_url).netloc}"
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        text = clean_text(a.get_text(" "))
        if not text or looks_bad_title(text):
            continue
        url = urljoin(base, href)
        # Require candidate listing-ish URLs OR strong title match with enough metadata around it.
        parent = a.find_parent()
        block = clean_text(parent.get_text(" ") if parent else text)
        listing_like = any(x in url for x in ["/ilan/", "/ikinci-el/", "/arac/", "/vasita-"]) or title_matches_watch(text, w)
        if not listing_like:
            continue
        item = make_item(source_key, text, url, block)
        if apply_filters(item, w):
            items.append(item)
    return items


def parse_reader_markdown(source_key: str, md: str, page_url: str, w: Dict) -> List[Dict]:
    if not md or md.startswith("ERROR:"):
        return []
    lines = [clean_text(l) for l in md.splitlines() if clean_text(l)]
    items: List[Dict] = []

    # 1) markdown links around listing URLs
    link_pat = re.compile(r"\[([^\]]{8,200})\]\((https?://[^\)]+)\)")
    for m in link_pat.finditer(md):
        title, url = clean_text(m.group(1)), m.group(2)
        around = md[max(0, m.start()-500):m.end()+700]
        if title_matches_watch(title, w):
            item = make_item(source_key, title, url, around)
            if apply_filters(item, w):
                items.append(item)

    # 2) source-specific block extraction from markdown/text
    joined = "\n".join(lines)
    brand_model = f"{w.get('brand','')} {w.get('model','')}".strip()
    package = w.get("package") if w.get("package") != "Farketmez" else ""

    # Otoplus pattern: Volkswagen TIGUAN2017 \n ## TIGUAN 1.4... \n 1.650.000 TL \n ### 98.202 KM
    if source_key == "otoplus":
        blocks = re.split(r"(?=\b(?:Volkswagen|Honda|Toyota|Renault|Ford|Hyundai|Kia)\b)", joined, flags=re.I)
        for b in blocks:
            if not title_matches_watch(b[:300], w):
                continue
            if not price_to_int(b):
                continue
            title_line = None
            for line in b.splitlines():
                line = line.strip("# ")
                if title_matches_watch(line, w) and not looks_bad_title(line):
                    title_line = line
                    break
            if not title_line:
                title_line = brand_model + (" " + package if package else "")
            item = make_item(source_key, title_line, page_url, b)
            # Otoplus category page isn't an individual ad. Keep only if it is real enough: price, year, km and package in title/block.
            if item.get("price") and item.get("year") and item.get("km") and apply_filters(item, w):
                items.append(item)

    # Arabam and Sahibinden reader output often has blocks starting with model name and then title/year/km/price/city.
    if source_key in ("arabam", "sahibinden"):
        # Break on repeated brand/model headings.
        pattern = re.escape(w.get("brand", "")) + r"\s+" + re.escape(w.get("model", ""))
        chunks = re.split(r"(?=" + pattern + r")", joined, flags=re.I)
        for b in chunks:
            if len(b) < 40 or not title_matches_watch(b[:350], w):
                continue
            if not price_to_int(b):
                continue
            # find title after first heading
            candidate_lines = [l.strip("# •*- ") for l in b.splitlines() if l.strip()]
            title_line = None
            for line in candidate_lines[:8]:
                if title_matches_watch(line, w) and not looks_bad_title(line):
                    title_line = line
                    break
            if not title_line:
                title_line = brand_model + (" " + package if package else "")
            # Use page_url as fallback, but if block has a URL use it
            url_match = re.search(r"https?://[^\s\)]+", b)
            url = url_match.group(0) if url_match else page_url
            item = make_item(source_key, title_line, url, b)
            if apply_filters(item, w):
                items.append(item)

    # 3) generic: lines with price and title match nearby
    for i, line in enumerate(lines):
        if price_to_int(line) or title_matches_watch(line, w):
            block = "\n".join(lines[max(0, i-5): i+10])
            if not price_to_int(block):
                continue
            if not title_matches_watch(block, w):
                continue
            # Don't create fake item if no useful metadata and page URL is just search homepage
            title = None
            for l in lines[max(0, i-5): i+5]:
                if title_matches_watch(l, w) and not looks_bad_title(l):
                    title = l.strip("# •*- ")
                    break
            if not title:
                continue
            item = make_item(source_key, title, page_url, block)
            if apply_filters(item, w):
                items.append(item)

    return dedupe_items(items)[:MAX_ITEMS_PER_SOURCE]


def parse_jina_search_results(source_key: str, md: str, w: Dict) -> List[Dict]:
    if not md or md.startswith("ERROR:"):
        return []
    items = []
    # Jina search often returns blocks with Title / URL Source / Description or markdown links.
    block_pat = re.compile(r"Title:\s*(.*?)\nURL Source:\s*(https?://\S+)(.*?)(?=\nTitle:|\Z)", re.S | re.I)
    for m in block_pat.finditer(md):
        title = clean_text(m.group(1))
        url = m.group(2).strip()
        block = clean_text(m.group(3))
        if not title_matches_watch(title + " " + block, w):
            continue
        # Must belong to target domain
        host = urlparse(url).netloc.lower()
        src = SOURCE_MAP.get(source_key)
        if src and urlparse(src.base).netloc.replace("www.", "") not in host.replace("www.", ""):
            continue
        item = make_item(source_key, title, url, block)
        if apply_filters(item, w):
            items.append(item)

    link_pat = re.compile(r"\[([^\]]{8,180})\]\((https?://[^\)]+)\)")
    for m in link_pat.finditer(md):
        title = clean_text(m.group(1))
        url = m.group(2)
        if not title_matches_watch(title, w):
            continue
        src = SOURCE_MAP.get(source_key)
        if src and urlparse(src.base).netloc.replace("www.", "") not in urlparse(url).netloc.replace("www.", ""):
            continue
        around = md[max(0, m.start()-300):m.end()+600]
        item = make_item(source_key, title, url, around)
        if apply_filters(item, w):
            items.append(item)

    return dedupe_items(items)[:MAX_ITEMS_PER_SOURCE]


def dedupe_items(items: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for it in items:
        url = canonical_url(it.get("url", ""))
        title = clean_text(it.get("title", ""))
        if not url or not title:
            continue
        fp = (url.split("?")[0], ascii_slug(title)[:60])
        if fp in seen:
            continue
        seen.add(fp)
        out.append(it)
    return out


def scan_source(source_key: str, w: Dict) -> Tuple[List[Dict], str]:
    status_parts = []
    items: List[Dict] = []
    url = direct_url(source_key, w)

    code, html, final_url = fetch_url(url)
    status_parts.append(f"HTTP {code}")
    if code == 200 and html:
        parsed = parse_html_links(source_key, html, final_url, w)
        if parsed:
            items.extend(parsed)
            status_parts.append(f"html liste {len(parsed)}")
        else:
            status_parts.append("html liste yok")
    elif code in (403, 429, 400, 401):
        status_parts.append("doğrudan engel")

    # Reader fallback for direct URL. It often works when raw HTML is JS-heavy.
    if len(items) < 2:
        rc, md = fetch_reader(url)
        if rc == 200 and md:
            parsed = parse_reader_markdown(source_key, md, url, w)
            status_parts.append(f"reader ok {len(parsed)}")
            items.extend(parsed)
        else:
            status_parts.append(f"reader {rc}")

    # Search fallback through Jina Search. This is intentionally used only when direct/readers are empty-ish.
    if len(items) < 2:
        query = jina_site_query(source_key, w)
        sc, smd = fetch_jina_search(query)
        if sc == 200 and smd:
            parsed = parse_jina_search_results(source_key, smd, w)
            status_parts.append(f"jina arama {len(parsed)}")
            items.extend(parsed)
        else:
            status_parts.append(f"jina arama {sc}")

    items = dedupe_items([i for i in items if apply_filters(i, w)])[:MAX_ITEMS_PER_SOURCE]
    return items, " / ".join(status_parts)

# ------------------------- Notifications -------------------------

def send_telegram(chat_id: str, text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID", "")
    if not token or not chat_id:
        return False, "Telegram ayarı yok"
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": text[:3900]}, timeout=12)
        return r.status_code == 200, f"Telegram {r.status_code}"
    except Exception as e:
        return False, str(e)


def send_mail(to_addr: str, subject: str, body: str):
    if not to_addr:
        return False, "mail yok"
    host = os.getenv("SMTP_HOST", "")
    port = int(os.getenv("SMTP_PORT", "587") or 587)
    user = os.getenv("SMTP_USER", "")
    pwd = os.getenv("SMTP_PASS", "")
    from_addr = os.getenv("MAIL_FROM", user)
    if not host or not user or not pwd:
        return False, "SMTP ayarı yok"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(user, pwd)
            smtp.send_message(msg)
        return True, "mail ok"
    except Exception as e:
        return False, str(e)

# ------------------------- Watch checking -------------------------

def row_to_watch(r: sqlite3.Row) -> Dict:
    d = dict(r)
    try:
        d["sources"] = json.loads(d.get("sources") or "[]")
    except Exception:
        d["sources"] = []
    for k in ["min_year", "max_year", "max_km", "min_price", "max_price", "interval_hours"]:
        if d.get(k) is not None:
            try: d[k] = int(d[k])
            except Exception: pass
    return d


def get_watch(watch_id: int) -> Optional[Dict]:
    with db() as con:
        r = con.execute("SELECT * FROM watches WHERE id=?", (watch_id,)).fetchone()
        return row_to_watch(r) if r else None


def save_check_results(watch: Dict, items: List[Dict], status_text: str):
    watch_id = int(watch["id"])
    now = now_iso()
    new_count = 0
    drop_count = 0
    events = []
    with db() as con:
        cleanup_bad_items(con)
        for item in items:
            title = clean_text(item.get("title") or "")
            url = canonical_url(item.get("url") or "")
            if not title or not url:
                continue
            fp = fingerprint_for(item.get("source"), url, title)
            existing = con.execute("SELECT * FROM items WHERE watch_id=? AND fingerprint=?", (watch_id, fp)).fetchone()
            price = item.get("price")
            if existing:
                old_price = existing["price_last"] or existing["price"]
                if price and old_price and price < old_price:
                    drop_count += 1
                    events.append(("price_drop", item.get("source"), title, old_price, price, url, now))
                con.execute("""
                    UPDATE items SET title=?, price=?, year=?, km=?, city=?, url=?, last_seen_at=?, price_last=?, is_active=1
                    WHERE id=?
                """, (title, price, item.get("year"), item.get("km"), item.get("city"), url, now, price or old_price, existing["id"]))
            else:
                new_count += 1
                events.append(("new", item.get("source"), title, None, price, url, now))
                con.execute("""
                    INSERT INTO items(watch_id, source, title, price, year, km, city, url, fingerprint, first_seen_at, last_seen_at, price_last, is_active)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1)
                """, (watch_id, item.get("source"), title, price, item.get("year"), item.get("km"), item.get("city"), url, fp, now, now, price))
        for ev in events:
            con.execute("INSERT INTO events(watch_id,event_type,source,title,price_old,price_new,url,created_at) VALUES(?,?,?,?,?,?,?,?)", (watch_id, *ev))
        total = con.execute("SELECT COUNT(*) FROM items WHERE watch_id=? AND is_active=1", (watch_id,)).fetchone()[0]
        interval = int(watch.get("interval_hours") or DEFAULT_INTERVAL_HOURS)
        next_time = (datetime.now(timezone.utc) + timedelta(hours=interval)).replace(microsecond=0).isoformat()
        con.execute("""
            UPDATE watches SET last_checked_at=?, next_check_at=?, last_status=?, last_seen_count=?, last_new_count=?, last_drop_count=?, checking=0, updated_at=?
            WHERE id=?
        """, (now, next_time, status_text[:1200], total, new_count, drop_count, now, watch_id))
        con.commit()

    # Notify only after first check if watch already had a last_checked_at.
    if (new_count or drop_count) and watch.get("last_checked_at"):
        lines = [f"Araç Avcısı: {watch.get('brand')} {watch.get('model')} için güncelleme"]
        for ev in events[:8]:
            evtype, src, title, old, newp, url, _t = ev
            if evtype == "price_drop":
                lines.append(f"Fiyat düştü: {title} | {old} -> {newp} TL | {url}")
            else:
                lines.append(f"Yeni ilan: {title} | {newp or 'Fiyat yok'} | {url}")
        body = "\n".join(lines)
        send_telegram(watch.get("telegram_chat_id"), body)
        send_mail(watch.get("email"), "Araç Avcısı bildirimi", body)


def run_check(watch_id: int):
    watch = get_watch(watch_id)
    if not watch:
        return
    with db() as con:
        con.execute("UPDATE watches SET checking=1, last_status=? WHERE id=?", ("Kontrol başladı...", watch_id))
        con.commit()
    try:
        sources = watch.get("sources") or [s.key for s in SOURCES]
        all_items = []
        status = []
        for sk in sources:
            if sk not in SOURCE_MAP:
                continue
            try:
                items, st = scan_source(sk, watch)
                all_items.extend(items)
                status.append(f"{SOURCE_MAP[sk].name}: {st} / liste {len(items)}")
            except Exception as e:
                status.append(f"{SOURCE_MAP.get(sk, Source(sk, sk, '')).name}: hata {type(e).__name__}: {e}")
        all_items = dedupe_items(all_items)[:MAX_TOTAL_ITEMS]
        save_check_results(watch, all_items, "Kontrol tamamlandı. " + " ; ".join(status))
    except Exception as e:
        err = f"Kontrol hatası: {type(e).__name__}: {e}\n{traceback.format_exc()[-600:]}"
        with db() as con:
            con.execute("UPDATE watches SET checking=0, last_status=?, updated_at=? WHERE id=?", (err[:1200], now_iso(), watch_id))
            con.commit()


def start_check_thread(watch_id: int):
    t = threading.Thread(target=run_check, args=(watch_id,), daemon=True)
    t.start()

_scheduler_started = False

def scheduler_loop():
    time.sleep(5)
    while True:
        try:
            now = datetime.now(timezone.utc)
            due_ids = []
            with db() as con:
                rows = con.execute("SELECT id,next_check_at,checking FROM watches WHERE active=1").fetchall()
                for r in rows:
                    if r["checking"]:
                        continue
                    nt = parse_iso(r["next_check_at"])
                    if nt and nt <= now:
                        due_ids.append(int(r["id"]))
            for wid in due_ids[:5]:
                start_check_thread(wid)
        except Exception:
            pass
        time.sleep(max(60, SCHEDULER_TICK_MINUTES * 60))


def start_scheduler_once():
    global _scheduler_started
    if _scheduler_started or not ENABLE_SCHEDULER:
        return
    _scheduler_started = True
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()

# ------------------------- Flask routes -------------------------

@app.route("/")
def index():
    return render_template("index.html", version=VERSION)

@app.route("/reset-cache")
def reset_cache():
    return render_template("reset_cache.html", version=VERSION)

@app.route("/health")
def health():
    return jsonify(ok=True, version=VERSION, time=now_iso(), default_interval_hours=DEFAULT_INTERVAL_HOURS, scheduler_tick_minutes=SCHEDULER_TICK_MINUTES, db=os.path.basename(DB_PATH))

@app.route("/api/options")
def api_options():
    return jsonify({
        "ok": True,
        "version": VERSION,
        "brands": BRANDS,
        "cities": CITIES,
        "sources": [s.__dict__ for s in SOURCES],
        "intervals": INTERVALS,
        "fuels": FUELS,
        "transmissions": TRANSMISSIONS,
    })

@app.route("/api/watches", methods=["GET"])
def api_watches():
    with db() as con:
        rows = con.execute("SELECT * FROM watches ORDER BY id DESC").fetchall()
        watches = []
        for r in rows:
            w = row_to_watch(r)
            w["items_count"] = con.execute("SELECT COUNT(*) FROM items WHERE watch_id=? AND is_active=1", (w["id"],)).fetchone()[0]
            watches.append(w)
        events = [dict(x) for x in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 20").fetchall()]
    return jsonify(ok=True, watches=watches, events=events)


def normalize_payload(data: Dict) -> Dict:
    def intval(k):
        v = data.get(k)
        if v in (None, "", "None"):
            return None
        try: return int(str(v).replace(".", "").replace(",", ""))
        except Exception: return None
    brand = data.get("brand") or "Volkswagen"
    model = data.get("model") or "Tiguan"
    pkg = data.get("package") or "Farketmez"
    name = clean_text(data.get("name") or f"{brand} {model} {pkg if pkg != 'Farketmez' else ''}")
    sources = data.get("sources") or [s.key for s in SOURCES]
    if isinstance(sources, str):
        try: sources = json.loads(sources)
        except Exception: sources = [x.strip() for x in sources.split(",") if x.strip()]
    sources = [s for s in sources if s in SOURCE_MAP]
    if not sources:
        sources = [s.key for s in SOURCES]
    interval = intval("interval_hours") or DEFAULT_INTERVAL_HOURS
    if interval not in INTERVALS:
        interval = DEFAULT_INTERVAL_HOURS
    return {
        "name": name, "brand": brand, "model": model, "package": pkg,
        "city": data.get("city") or "Tüm Türkiye", "min_year": intval("min_year"), "max_year": intval("max_year"),
        "max_km": intval("max_km"), "min_price": intval("min_price"), "max_price": intval("max_price"),
        "fuel": data.get("fuel") or "Farketmez", "transmission": data.get("transmission") or "Farketmez",
        "sources": sources, "interval_hours": interval,
        "email": clean_text(data.get("email") or ""), "telegram_chat_id": clean_text(data.get("telegram_chat_id") or ""),
    }

@app.route("/api/watches", methods=["POST"])
def api_create_watch():
    data = request.get_json(force=True, silent=True) or {}
    w = normalize_payload(data)
    now = now_iso()
    try:
        with db() as con:
            # don't duplicate exact same active watch; return existing
            existing = con.execute("""
                SELECT id FROM watches WHERE active=1 AND brand=? AND model=? AND package=? AND city=? AND min_year IS ? AND max_year IS ? AND max_km IS ? AND min_price IS ? AND max_price IS ? AND transmission=?
                ORDER BY id DESC LIMIT 1
            """, (w["brand"], w["model"], w["package"], w["city"], w["min_year"], w["max_year"], w["max_km"], w["min_price"], w["max_price"], w["transmission"])).fetchone()
            if existing:
                wid = int(existing["id"])
            else:
                con.execute("""
                    INSERT INTO watches(name,brand,model,package,city,min_year,max_year,max_km,min_price,max_price,fuel,transmission,sources,interval_hours,active,email,telegram_chat_id,created_at,updated_at,last_status,next_check_at,checking)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)
                """, (w["name"], w["brand"], w["model"], w["package"], w["city"], w["min_year"], w["max_year"], w["max_km"], w["min_price"], w["max_price"], w["fuel"], w["transmission"], json.dumps(w["sources"]), w["interval_hours"], 1, w["email"], w["telegram_chat_id"], now, now, "Takip kaydedildi. Başlangıç araması arkada çalışıyor.", now))
                wid = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            con.commit()
        start_check_thread(wid)
        return jsonify(ok=True, id=wid, message="Takip kaydedildi. Başlangıç araması arkada çalışıyor.")
    except Exception as e:
        return jsonify(ok=False, error=f"Kayıt hatası: {type(e).__name__}: {e}"), 500

@app.route("/api/watches/<int:watch_id>/check", methods=["POST"])
def api_check(watch_id):
    if not get_watch(watch_id):
        return jsonify(ok=False, error="Takip bulunamadı"), 404
    start_check_thread(watch_id)
    return jsonify(ok=True, message="Kontrol başlatıldı")

@app.route("/api/watches/<int:watch_id>/items")
def api_items(watch_id):
    with db() as con:
        rows = con.execute("SELECT * FROM items WHERE watch_id=? AND is_active=1 ORDER BY price IS NULL, price ASC, id DESC LIMIT 100", (watch_id,)).fetchall()
    return jsonify(ok=True, items=[dict(r) for r in rows])

@app.route("/api/watches/<int:watch_id>/toggle", methods=["POST"])
def api_toggle(watch_id):
    with db() as con:
        r = con.execute("SELECT active FROM watches WHERE id=?", (watch_id,)).fetchone()
        if not r: return jsonify(ok=False, error="Takip bulunamadı"), 404
        newv = 0 if r["active"] else 1
        con.execute("UPDATE watches SET active=?, updated_at=? WHERE id=?", (newv, now_iso(), watch_id))
        con.commit()
    return jsonify(ok=True, active=newv)

@app.route("/api/watches/<int:watch_id>/interval", methods=["POST"])
def api_interval(watch_id):
    data = request.get_json(force=True, silent=True) or {}
    try: interval = int(data.get("interval_hours"))
    except Exception: interval = DEFAULT_INTERVAL_HOURS
    if interval not in INTERVALS:
        return jsonify(ok=False, error="Geçersiz süre"), 400
    next_time = (datetime.now(timezone.utc) + timedelta(hours=interval)).replace(microsecond=0).isoformat()
    with db() as con:
        con.execute("UPDATE watches SET interval_hours=?, next_check_at=?, updated_at=? WHERE id=?", (interval, next_time, now_iso(), watch_id))
        con.commit()
    return jsonify(ok=True, interval_hours=interval)

@app.route("/api/watches/<int:watch_id>", methods=["DELETE"])
def api_delete(watch_id):
    with db() as con:
        con.execute("DELETE FROM events WHERE watch_id=?", (watch_id,))
        con.execute("DELETE FROM items WHERE watch_id=?", (watch_id,))
        con.execute("DELETE FROM watches WHERE id=?", (watch_id,))
        con.commit()
    return jsonify(ok=True)

@app.route("/api/debug/clear-items", methods=["POST"])
def api_clear_items():
    data = request.get_json(force=True, silent=True) or {}
    wid = data.get("watch_id")
    with db() as con:
        if wid:
            con.execute("DELETE FROM items WHERE watch_id=?", (int(wid),))
        else:
            con.execute("DELETE FROM items")
        con.commit()
    return jsonify(ok=True)

@app.route("/api/watches/<int:watch_id>/open/<source_key>")
def api_open_source(watch_id, source_key):
    w = get_watch(watch_id)
    if not w or source_key not in SOURCE_MAP:
        return redirect("/")
    return redirect(direct_url(source_key, w), code=302)

def boot_init_db():
    """Eski/veri klasöründen gelen bozuk SQLite şemasında uygulama çökmesin."""
    try:
        init_db()
    except Exception:
        traceback.print_exc()
        try:
            if os.path.exists(DB_PATH):
                backup = DB_PATH + ".bozuk_yedek_" + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
                os.replace(DB_PATH, backup)
        except Exception:
            traceback.print_exc()
        # Yeni, temiz veritabanı oluştur.
        init_db()

# Init once on import
boot_init_db()
start_scheduler_once()

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=True)
