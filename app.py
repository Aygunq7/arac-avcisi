import os
import re
import json
import time
import sqlite3
import threading
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlencode

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, redirect, jsonify, url_for
from apscheduler.schedulers.background import BackgroundScheduler

VERSION = "v31-akilli-filtre-sonuc-var"
DATA_DIR = os.getenv("DATA_DIR", "data")
DB_PATH = os.path.join(DATA_DIR, "arac_avcisi.db")
DEFAULT_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "4") or 4)
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "8") or 8)
MAX_ITEMS_PER_SOURCE = int(os.getenv("MAX_ITEMS_PER_SOURCE", "12") or 12)

os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "arac-avcisi-v31")

BRANDS = {
    "Volkswagen": {
        "models": ["Tiguan", "Passat", "Golf", "Polo", "Jetta", "T-Roc", "T-Cross", "Touareg", "Arteon"],
        "packages": ["Farketmez", "1.4 TSI Comfortline", "1.4 TSI Highline", "1.4 TSI Trendline", "1.5 TSI Comfortline", "1.5 TSI Elegance", "1.5 TSI R-Line", "2.0 TDI Comfortline", "2.0 TDI Highline", "2.0 TDI R-Line"]
    },
    "Honda": {
        "models": ["Civic", "CR-V", "HR-V", "Jazz", "City", "Accord"],
        "packages": ["Farketmez", "1.6 Eco Elegance", "1.6 Eco Executive", "1.6 i-VTEC Elegance", "1.6 i-VTEC Executive", "1.5 VTEC Turbo Elegance", "1.5 VTEC Turbo Executive"]
    },
    "Toyota": {
        "models": ["Corolla", "C-HR", "Yaris", "Auris", "RAV4", "Camry"],
        "packages": ["Farketmez", "Vision", "Dream", "Flame", "Passion", "Advance", "Premium"]
    },
    "Renault": {
        "models": ["Clio", "Megane", "Taliant", "Captur", "Kadjar", "Fluence", "Symbol"],
        "packages": ["Farketmez", "Joy", "Touch", "Icon", "Business", "Sport Tourer", "Extreme"]
    },
    "Fiat": {
        "models": ["Egea", "Linea", "Punto", "Doblo", "Fiorino", "500", "Panda"],
        "packages": ["Farketmez", "Easy", "Urban", "Lounge", "Cross", "Mirror", "Pop"]
    },
    "Hyundai": {
        "models": ["i20", "i30", "Accent Blue", "Elantra", "Tucson", "Bayon", "Kona", "Santa Fe"],
        "packages": ["Farketmez", "Jump", "Style", "Elite", "Prime", "Smart", "N Line"]
    },
    "Ford": {
        "models": ["Focus", "Fiesta", "Kuga", "Puma", "Mondeo", "EcoSport", "Tourneo Courier", "Transit Custom"],
        "packages": ["Farketmez", "Trend", "Titanium", "Style", "ST-Line", "Trend X", "Vignale"]
    },
    "Peugeot": {
        "models": ["208", "308", "3008", "5008", "2008", "508", "Partner"],
        "packages": ["Farketmez", "Active", "Allure", "GT", "GT Line", "Access", "Prime"]
    },
    "Opel": {
        "models": ["Astra", "Corsa", "Insignia", "Mokka", "Crossland", "Grandland", "Vectra"],
        "packages": ["Farketmez", "Enjoy", "Essentia", "Edition", "Elegance", "Ultimate", "Cosmo", "Dynamic"]
    },
    "BMW": {
        "models": ["1 Serisi", "2 Serisi", "3 Serisi", "4 Serisi", "5 Serisi", "X1", "X3", "X5"],
        "packages": ["Farketmez", "Comfort", "Luxury Line", "M Sport", "Sport Line", "Executive"]
    },
    "Mercedes-Benz": {
        "models": ["A Serisi", "B Serisi", "C Serisi", "E Serisi", "CLA", "GLA", "GLC", "Vito"],
        "packages": ["Farketmez", "AMG", "Avantgarde", "Exclusive", "Style", "Progressive"]
    },
    "Audi": {
        "models": ["A3", "A4", "A5", "A6", "Q2", "Q3", "Q5", "Q7"],
        "packages": ["Farketmez", "Attraction", "Ambition", "Sport Line", "Design Line", "S Line", "Advanced"]
    },
    "Nissan": {"models": ["Qashqai", "Juke", "Micra", "X-Trail", "Navara"], "packages": ["Farketmez", "Visia", "Tekna", "Platinum", "Skypack", "Designpack"]},
    "Dacia": {"models": ["Duster", "Sandero", "Logan", "Jogger", "Lodgy"], "packages": ["Farketmez", "Ambiance", "Laureate", "Comfort", "Prestige", "Journey", "Extreme"]},
    "Citroen": {"models": ["C3", "C4", "C5 Aircross", "C-Elysee", "Berlingo"], "packages": ["Farketmez", "Feel", "Shine", "Live", "Confort", "Exclusive"]},
    "Skoda": {"models": ["Octavia", "Superb", "Fabia", "Kamiq", "Karoq", "Kodiaq", "Scala"], "packages": ["Farketmez", "Ambition", "Style", "Prestige", "Elite", "Sportline"]},
    "Seat": {"models": ["Leon", "Ibiza", "Ateca", "Arona", "Toledo"], "packages": ["Farketmez", "Reference", "Style", "FR", "Xcellence"]},
    "Kia": {"models": ["Sportage", "Ceed", "Rio", "Cerato", "Stonic", "Picanto", "Sorento"], "packages": ["Farketmez", "Cool", "Concept", "Prestige", "Elegance", "Premium"]},
}

CITIES = ["Tüm Türkiye", "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın", "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük", "Kilis", "Osmaniye", "Düzce"]
SOURCES = [
    ("arabam", "Arabam"),
    ("sahibinden", "Sahibinden"),
    ("otoplus", "Otoplus"),
    ("otokoc", "Otokoç 2. El"),
    ("vavacars", "VavaCars"),
    ("arabasepeti", "Araba Sepeti"),
    ("arabalar", "Arabalar.com"),
    ("letgo", "Letgo"),
    ("facebook", "Facebook Marketplace"),
]
FUEL_OPTIONS = ["Farketmez", "Benzin", "Dizel", "LPG", "Benzin & LPG", "Hibrit", "Elektrik"]
GEAR_OPTIONS = ["Farketmez", "Otomatik", "Yarı Otomatik", "Manuel"]
INTERVALS = [1,2,3,4,6,8,12,24,48,72]


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con



TRACK_COLUMNS = {
    "name": "TEXT", "brand": "TEXT", "model": "TEXT", "trim": "TEXT", "city": "TEXT",
    "year_min": "INTEGER", "year_max": "INTEGER", "km_max": "INTEGER",
    "price_min": "INTEGER", "price_max": "INTEGER",
    "fuel": "TEXT DEFAULT 'Farketmez'", "gear": "TEXT DEFAULT 'Farketmez'", "sources": "TEXT DEFAULT '[]'",
    "interval_hours": "INTEGER DEFAULT 4", "notify_email": "TEXT DEFAULT ''", "telegram_chat_id": "TEXT DEFAULT ''",
    "filter_mode": "TEXT DEFAULT 'dengeli'", "active": "INTEGER DEFAULT 1", "created_at": "TEXT", "updated_at": "TEXT",
    "last_check_at": "TEXT", "last_status": "TEXT DEFAULT ''", "item_count": "INTEGER DEFAULT 0"
}
LISTING_COLUMNS = {
    "track_id": "INTEGER", "source": "TEXT", "title": "TEXT", "price": "INTEGER",
    "year": "INTEGER", "km": "INTEGER", "city": "TEXT", "url": "TEXT", "uid": "TEXT",
    "first_seen": "TEXT", "last_seen": "TEXT", "raw": "TEXT DEFAULT ''"
}
EVENT_COLUMNS = {
    "track_id": "INTEGER", "type": "TEXT", "source": "TEXT", "title": "TEXT", "price_old": "INTEGER",
    "price_new": "INTEGER", "url": "TEXT", "created_at": "TEXT", "notify_status": "TEXT DEFAULT ''"
}

def ensure_columns(con, table, columns):
    """Eski sürümlerden kalan SQLite tablolarını çökmeden yeni sürüme yükseltir."""
    try:
        existing = {r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, ddl in columns.items():
            if name not in existing:
                con.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
        con.commit()
    except Exception:
        # Migration hatası uygulamayı durdurmasın. Gerekirse reset-db endpointi kullanılabilir.
        con.rollback()
        raise

def backup_broken_db(reason=""):
    try:
        if os.path.exists(DB_PATH):
            bak = DB_PATH + ".broken." + str(int(time.time()))
            os.rename(DB_PATH, bak)
            return bak
    except Exception:
        return None
    return None

def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    con = db()
    cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS tracks(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, brand TEXT, model TEXT, trim TEXT, city TEXT,
        year_min INTEGER, year_max INTEGER, km_max INTEGER,
        price_min INTEGER, price_max INTEGER,
        fuel TEXT, gear TEXT, sources TEXT,
        interval_hours INTEGER DEFAULT 4,
        notify_email TEXT, telegram_chat_id TEXT,
        filter_mode TEXT DEFAULT 'dengeli', active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT,
        last_check_at TEXT, last_status TEXT DEFAULT '', item_count INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS listings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER, source TEXT, title TEXT, price INTEGER,
        year INTEGER, km INTEGER, city TEXT, url TEXT, uid TEXT,
        first_seen TEXT, last_seen TEXT, raw TEXT DEFAULT '', UNIQUE(track_id, uid)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER, type TEXT, source TEXT, title TEXT, price_old INTEGER,
        price_new INTEGER, url TEXT, created_at TEXT, notify_status TEXT DEFAULT ''
    )""")
    # Eski deployment'lardan kalan tablo şemaları varsa eksik kolonları tamamla.
    ensure_columns(con, "tracks", TRACK_COLUMNS)
    ensure_columns(con, "listings", LISTING_COLUMNS)
    ensure_columns(con, "events", EVENT_COLUMNS)
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_listings_track_uid ON listings(track_id, uid)")
    con.commit()
    con.close()


def as_int(v, default=None):
    try:
        if v is None or str(v).strip() == "":
            return default
        return int(re.sub(r"[^0-9]", "", str(v)))
    except Exception:
        return default


def slug_tr(text):
    text = (text or "").strip().lower()
    tr = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    text = text.translate(tr)
    text = text.replace("&", " ").replace("+", " ")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")


def query_terms(t):
    parts = [t.get("brand"), t.get("model")]
    if t.get("trim") and t.get("trim") != "Farketmez":
        parts.append(t.get("trim"))
    if t.get("city") and t.get("city") != "Tüm Türkiye":
        parts.append(t.get("city"))
    if t.get("gear") and t.get("gear") != "Farketmez":
        parts.append(t.get("gear"))
    return " ".join([p for p in parts if p])


# Hangi kaynaklardan uygulama içine otomatik ilan alınacağı.
# Letgo/Facebook gibi sayfalar çoğu zaman resim/CDN veya alakasız ürün linki döndürdüğü için
# artık uygulama içinde listeye alınmaz; sadece ilgili sitede arama butonu açılır.
AUTO_LIST_SOURCES = {"arabam", "sahibinden", "otoplus", "otokoc", "vavacars", "arabasepeti", "arabalar"}
OPEN_ONLY_SOURCES = {"letgo", "facebook"}

CITY_SLUGS = {slug_tr(c): c for c in CITIES if c != "Tüm Türkiye"}

SUV_MODELS = {"tiguan", "qashqai", "duster", "kuga", "3008", "5008", "2008", "tucson", "sportage", "rav4", "c-hr", "x1", "x3", "x5", "q2", "q3", "q5", "q7", "cr-v", "hr-v", "bayon", "kona", "mokka", "crossland", "grandland", "karoq", "kodiaq", "kamiq", "ateca", "arona", "compass"}

def vehicle_category_slug(t):
    model = slug_tr(t.get("model") or "")
    if model in SUV_MODELS:
        return "arazi-suv-pick-up"
    return "otomobil"

def sahibinden_category_slug(t):
    model = slug_tr(t.get("model") or "")
    if model in SUV_MODELS:
        return "arazi-suv-pickup"
    return "otomobil"

def build_filter_query(t):
    qs = {}
    if t.get("price_min"): qs["price_min"] = t.get("price_min")
    if t.get("price_max"): qs["price_max"] = t.get("price_max")
    if t.get("year_min"): qs["year_min"] = t.get("year_min")
    if t.get("year_max"): qs["year_max"] = t.get("year_max")
    if t.get("km_max"): qs["km_max"] = t.get("km_max")
    if t.get("gear") and t.get("gear") != "Farketmez": qs["gear"] = t.get("gear")
    if t.get("fuel") and t.get("fuel") != "Farketmez": qs["fuel"] = t.get("fuel")
    return qs

def sahibinden_query_params(t):
    # Sahibinden açık parametrelerin bir kısmı kategoriye göre değişebilir. Bu yüzden aç butonunda
    # daha güvenli olan genel arama kullanılır; direkt okuma için yaygın filtreler eklenir.
    qs = {"query_text": query_terms(t)}
    if t.get("price_min"): qs["price_min"] = t.get("price_min")
    if t.get("price_max"): qs["price_max"] = t.get("price_max")
    if t.get("km_max"): qs["a4_max"] = t.get("km_max")
    if t.get("year_min"): qs["a5_min"] = t.get("year_min")
    if t.get("year_max"): qs["a5_max"] = t.get("year_max")
    return qs

def normalize_url(url):
    if not url:
        return ""
    url = url.strip().split()[0].rstrip('.,;"\'')
    return url.split("#")[0]


def list_url(source, t):
    brand = t.get("brand") or ""
    model = t.get("model") or ""
    trim = t.get("trim") or ""
    city = t.get("city") or ""
    q = query_terms(t)
    b = slug_tr(brand)
    m = slug_tr(model)
    tm = slug_tr(trim if trim != "Farketmez" else "")
    city_slug = slug_tr(city if city != "Tüm Türkiye" else "")
    category = vehicle_category_slug(t)
    qs = build_filter_query(t)
    add = ("?" + urlencode(qs)) if qs else ""

    if source == "arabam":
        path = f"{b}-{m}" + (f"-{tm}" if tm else "")
        return f"https://www.arabam.com/ikinci-el/{category}/{path}{add}"

    if source == "sahibinden":
        # Kategori URL'leri sık bozulduğu için kullanıcıyı daha güvenli genel aramaya yönlendir.
        # Otomatik okuyucu arka planda yine /ilan/ linklerini yakalamaya çalışır.
        return "https://www.sahibinden.com/arama?" + urlencode(sahibinden_query_params(t))

    if source == "otoplus":
        # Otoplus'ta bazı marka/model yolları kategori sayfası döndürür; listeye sahte ilan almayız.
        path = f"{b}/{m}" + (f"/{m}-{tm}" if tm else "")
        return f"https://www.otoplus.com/{path}{add}"

    if source == "otokoc":
        return f"https://www.otokocikinciel.com/ikinci-el-{b}-{m}{add}"

    if source == "vavacars":
        return f"https://tr.vava.cars/ikinci-el-araba?search={quote_plus(q)}"

    if source == "arabasepeti":
        return f"https://www.arabasepeti.com/ikinci-el?search={quote_plus(q)}"

    if source == "arabalar":
        return f"https://www.arabalar.com.tr/ikinci-el/{b}-{m}{add}"

    if source == "letgo":
        return f"https://www.letgo.com/arama?q={quote_plus(q + ' otomobil')}"

    if source == "facebook":
        return f"https://www.facebook.com/marketplace/search/?query={quote_plus(q + ' araba')}"

    return "https://www.google.com/search?q=" + quote_plus(q)

def is_detail_url(source, url):
    url = normalize_url(url)
    if not url or not url.startswith("http"):
        return False
    u = url.lower()
    if any(x in u for x in ["javascript:", "#", "/search", "arama?", "filtre", "kategori", "assets", "/files/", "image", "img", ".jpg", ".jpeg", ".png", ".webp", ".svg"]):
        return False

    # Her site için mümkün olduğunca gerçek ilan sayfası şartı.
    if source == "sahibinden":
        return "sahibinden.com/ilan/" in u
    if source == "arabam":
        return "arabam.com/ilan/" in u
    if source == "letgo":
        return "letgo.com/item/" in u and "imvm.letgo" not in u
    if source == "facebook":
        return "facebook.com/marketplace/item/" in u
    if source == "vavacars":
        return ("tr.vava.cars" in u and ("/ikinci-el-araba/" in u or "/buy-car/" in u or "/car/" in u))
    if source == "otoplus":
        # Kategori/filtre sayfası değil, genelde uzun ve ilan benzeri yol olsun.
        return "otoplus.com" in u and ("/arac/" in u or "/ikinci-el/" in u or "/ilan/" in u) and bool(re.search(r"\d{4}|\d{5,}", u))
    if source == "otokoc":
        return "otokocikinciel.com" in u and ("/ikinci-el/" in u or bool(re.search(r"/\d{5,}", u)))
    if source == "arabasepeti":
        return "arabasepeti.com" in u and ("/ilan/" in u or "/arac/" in u or bool(re.search(r"\d{5,}", u)))
    if source == "arabalar":
        return "arabalar.com" in u and ("/ilan/" in u or "/satilik/" in u or bool(re.search(r"\d{5,}", u)))
    return False

def clean_title(s):
    s = BeautifulSoup(s or "", "html.parser").get_text(" ")
    s = re.sub(r"\s+", " ", s).strip(" -•|\n\t")
    return s[:160]


def bad_title(title):
    t = (title or "").lower()
    bads = ["filtre", "çerez", "giriş", "üye", "sonuç bulunamadı", "araçları listeleniyor", "arama", "anasayfa", "kategori", "model seç", "marka seç"]
    return len(t) < 8 or any(b in t for b in bads)


def text_for_parsing(text):
    """URL, script kırıntısı ve form filtresi değerleri sayısal filtreleri kandırmasın."""
    text = BeautifulSoup(text or "", "html.parser").get_text(" ")
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"(?:price|km|year|a4|a5)[_-]?(?:min|max)?=\d+", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_price(text):
    clean = text_for_parsing(text).lower()
    # Sadece TL/₺ yanında geçen değerleri fiyat say. 2018, 110000 km gibi sayıları fiyat sanma.
    matches = re.findall(r"(?<!\d)((?:\d{1,3}(?:[\.\s]\d{3}){1,4})|\d{6,9})\s*(?:tl|₺)", clean)
    if not matches:
        return None
    vals = [as_int(m) for m in matches]
    vals = [v for v in vals if v and 50000 <= v <= 50000000]
    return vals[0] if vals else None


def parse_year(text):
    clean = text_for_parsing(text)
    # Önce model yılı / yıl çevresindeki değeri yakala.
    m = re.search(r"(?:model\s*yılı|model\s*yili|yıl|yili|yılı)\D{0,20}(19[8-9]\d|20[0-3]\d)", clean, re.I)
    if m:
        return int(m.group(1))
    years = [int(x) for x in re.findall(r"\b(19[8-9]\d|20[0-3]\d)\b", clean)]
    # Aynı blokta birden fazla tarih varsa ilk gerçek ilan satırı genelde ilk değeri verir.
    return years[0] if years else None


def parse_km(text):
    clean = text_for_parsing(text).lower()
    m = re.search(r"((?:\d{1,3}(?:[\.\s]\d{3}){1,3})|\d{4,7})\s*(?:km|kilometre)", clean)
    if m:
        v = as_int(m.group(1))
        return v if v is not None and 0 <= v < 1000000 else None
    return None



def filter_mode(t):
    return (t.get("filter_mode") or "dengeli").lower()


def fuel_state(item, t):
    wanted = (t.get("fuel") or "Farketmez").lower()
    if wanted == "farketmez":
        return "match"
    blob = slug_tr(" ".join(str(item.get(k) or "") for k in ["title", "url", "raw"]))
    fuel_map = {
        "benzin": ["benzin", "gasoline", "petrol"],
        "dizel": ["dizel", "diesel"],
        "lpg": ["lpg", "otogaz"],
        "benzin & lpg": ["benzin-lpg", "benzin-ve-lpg", "lpg"],
        "hibrit": ["hibrit", "hybrid"],
        "elektrik": ["elektrik", "electric"]
    }
    all_known = {w for vals in fuel_map.values() for w in vals}
    wanted_keys = fuel_map.get(wanted, [wanted])
    if any(slug_tr(k) in blob for k in wanted_keys):
        return "match"
    if any(slug_tr(k) in blob for k in all_known):
        return "mismatch"
    return "unknown"


def fuel_ok(item, t):
    st = fuel_state(item, t)
    return st == "match" or (st == "unknown" and filter_mode(t) != "kesin")


def gear_state(item, t):
    wanted = (t.get("gear") or "Farketmez").lower()
    if wanted == "farketmez":
        return "match"
    blob = slug_tr(" ".join(str(item.get(k) or "") for k in ["title", "url", "raw"]))
    auto_words = ["otomatik", "automatic", "dsg", "edc", "cvt", "tiptronic", "stronic", "s-tronic", "powershift", "auto", "at", "bva"]
    semi_words = ["yari-otomatik", "yarı-otomatik", "semi-automatic", "dsg", "edc", "cvt"]
    manual_words = ["manuel", "manual", "duz-vites", "düz-vites", "duz", "mt"]
    has_manual = any(slug_tr(w) in blob for w in manual_words)
    has_auto = any(slug_tr(w) in blob for w in auto_words + semi_words)
    if "manuel" in wanted:
        if has_manual and not has_auto:
            return "match"
        if has_auto:
            return "mismatch"
        return "unknown"
    if "yar" in wanted:
        if any(slug_tr(w) in blob for w in semi_words) and not has_manual:
            return "match"
        if has_manual:
            return "mismatch"
        return "unknown"
    if "otomatik" in wanted:
        if has_auto and not has_manual:
            return "match"
        if has_manual:
            return "mismatch"
        return "unknown"
    return "match"


def gear_ok(item, t):
    st = gear_state(item, t)
    return st == "match" or (st == "unknown" and filter_mode(t) != "kesin")


def filter_reason(item, t):
    """İlanın takip filtresine uyup uymadığını nedenleriyle döndürür.
    Kullanıcı bir filtre girdiyse o bilgi okunmak zorunda. Okunamayan ilan listeye girmez.
    """
    blob = f"{item.get('title','')} {item.get('url','')} {item.get('raw','')}".lower()
    slug_blob = slug_tr(blob)
    brand_slug = slug_tr(t.get("brand"))
    model_slug = slug_tr(t.get("model"))
    if brand_slug and brand_slug not in slug_blob:
        return False, "marka eşleşmedi"
    if model_slug and model_slug not in slug_blob:
        return False, "model eşleşmedi"

    strict = filter_mode(t) == "kesin"
    trim = t.get("trim") or ""
    if trim and trim != "Farketmez":
        tokens = [slug_tr(x) for x in re.split(r"\s+", trim) if len(x) > 1]
        important = [x for x in tokens if x not in ["bmt", "eco", "i", "ve", "and"]]
        if important:
            missing = [x for x in important if x not in slug_blob]
            # Dengeli modda paket bilgisi okunamazsa ilanı tamamen çöpe atma.
            # Ama açıkça başka paket görünürse yine elenir.
            known_packages = ["comfortline", "highline", "trendline", "elegance", "executive", "r-line", "joy", "touch", "icon", "style", "elite", "premium"]
            visible_pkg = any(p in slug_blob for p in known_packages)
            if len(missing) == len(important) and (strict or visible_pkg):
                return False, "paket/motor eşleşmedi"

    if not gear_ok(item, t):
        return False, "vites uymadı" if filter_mode(t) != "kesin" else "vites uymadı veya okunamadı"
    if not fuel_ok(item, t):
        return False, "yakıt uymadı" if filter_mode(t) != "kesin" else "yakıt uymadı veya okunamadı"

    price = item.get("price")
    if t.get("price_min") or t.get("price_max"):
        if price is None:
            if strict:
                return False, "fiyat okunamadı"
        else:
            if t.get("price_min") and price < t["price_min"]:
                return False, "fiyat düşük"
            if t.get("price_max") and price > t["price_max"]:
                return False, "fiyat yüksek"

    year = item.get("year")
    if t.get("year_min") or t.get("year_max"):
        if year is None:
            if strict:
                return False, "yıl okunamadı"
        else:
            if t.get("year_min") and year < t["year_min"]:
                return False, "yıl düşük"
            if t.get("year_max") and year > t["year_max"]:
                return False, "yıl yüksek"

    km = item.get("km")
    if t.get("km_max"):
        if km is None:
            if strict:
                return False, "km okunamadı"
        else:
            if km > t["km_max"]:
                return False, "km yüksek"

    city = t.get("city")
    if city and city != "Tüm Türkiye":
        if not item.get("city"):
            if strict:
                return False, "şehir okunamadı"
        elif slug_tr(city) not in slug_tr(item.get("city")):
            return False, "şehir uymadı"
    return True, "uygun"


def passes_filters(item, t):
    return filter_reason(item, t)[0]


def listing_row_passes(row, t):
    item = dict(row)
    item.setdefault("raw", "")
    return passes_filters(item, t)


def cleanup_invalid_listings(con, t):
    """Eski sürümlerden kalan filtre dışı ilanları temizler."""
    try:
        rows = con.execute("SELECT * FROM listings WHERE track_id=?", (t["id"],)).fetchall()
        bad_ids = []
        for r in rows:
            if not listing_row_passes(r, t):
                bad_ids.append(r["id"])
        if bad_ids:
            con.executemany("DELETE FROM listings WHERE id=?", [(x,) for x in bad_ids])
            con.commit()
        return len(bad_ids)
    except Exception:
        return 0

def fetch(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    return r.status_code, r.text, r.url


def reader_url(url):
    return "https://r.jina.ai/http://r.jina.ai/http://example.com" if False else "https://r.jina.ai/http://" + re.sub(r"^https?://", "", url)


def search_url(source, t):
    domain = {
        "sahibinden": "sahibinden.com/ilan",
        "arabam": "arabam.com/ilan",
        "otoplus": "otoplus.com",
        "otokoc": "otokocikinciel.com",
        "vavacars": "tr.vava.cars",
        "arabasepeti": "arabasepeti.com",
        "arabalar": "arabalar.com.tr",
        "letgo": "letgo.com",
        "facebook": "facebook.com/marketplace",
    }.get(source, "")
    q = f"site:{domain} {query_terms(t)} ikinci el fiyat km yıl"
    return "https://s.jina.ai/" + quote_plus(q)


def parse_html_items(source, html, base_url, t):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a.get("href") or ""
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(base_url, href)
        text = clean_title(a.get_text(" "))
        parent_text = clean_title(a.find_parent().get_text(" ") if a.find_parent() else text)
        blob = parent_text or text
        if not is_detail_url(source, href):
            continue
        title = text if len(text) >= 8 else clean_title(blob[:120])
        if bad_title(title):
            continue
        item = {
            "source": source,
            "title": title,
            "url": href.split("?")[0],
            "price": parse_price(blob),
            "year": parse_year(blob),
            "km": parse_km(blob),
            "city": extract_city(blob),
            "raw": blob,
        }
        if item["url"] in seen:
            continue
        if passes_filters(item, t):
            seen.add(item["url"])
            items.append(item)
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break
    return items


def parse_text_items(source, text, t):
    items = []
    seen = set()
    # Markdown link format: [title](url)
    for title, url in re.findall(r"\[([^\]]{8,180})\]\((https?://[^\)\s]+)\)", text):
        title = clean_title(title)
        if not is_detail_url(source, url) or bad_title(title):
            continue
        around = title + " " + text[max(0, text.find(url)-250): text.find(url)+250]
        item = {"source": source, "title": title, "url": url.split("?")[0], "price": parse_price(around), "year": parse_year(around), "km": parse_km(around), "city": extract_city(around), "raw": around}
        if item["url"] not in seen and passes_filters(item, t):
            seen.add(item["url"]); items.append(item)
        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break
    # raw urls
    if len(items) < 3:
        for url in re.findall(r"https?://[^\s\)\]]+", text):
            url = url.rstrip('.,;"\'')
            if not is_detail_url(source, url) or url in seen:
                continue
            pos = text.find(url)
            around = text[max(0,pos-260):pos+260]
            title = guess_title_from_text(around, t)
            if bad_title(title):
                continue
            item = {"source": source, "title": title, "url": url.split("?")[0], "price": parse_price(around), "year": parse_year(around), "km": parse_km(around), "city": extract_city(around), "raw": around}
            if passes_filters(item, t):
                seen.add(url); items.append(item)
            if len(items) >= MAX_ITEMS_PER_SOURCE:
                break
    return items


def guess_title_from_text(txt, t):
    # içerikten marka model geçen kısa satır yakala
    lines = [clean_title(x) for x in txt.splitlines()]
    for line in lines:
        if slug_tr(t.get("brand")) in slug_tr(line) and slug_tr(t.get("model")) in slug_tr(line):
            return line[:140]
    return f"{t.get('brand')} {t.get('model')} {t.get('trim') if t.get('trim')!='Farketmez' else ''}".strip()


def extract_city(text):
    s = slug_tr(text)
    for c in CITIES:
        if c == "Tüm Türkiye": continue
        if slug_tr(c) in s:
            return c
    return None


def source_check(source, t):
    status = []
    items = []
    rejected = {}
    url = list_url(source, t)

    if source in OPEN_ONLY_SOURCES:
        return [], "Bu kaynak uygulama içinde güvenilir ilan listesi vermiyor; sitede aç butonu kullanılır", url

    try:
        code, html, final_url = fetch(url)
        status.append(f"HTTP {code}")
        if code == 200:
            html_items = parse_html_items(source, html, final_url, t)
            status.append(f"html {len(html_items)}")
            items.extend(html_items)
        elif code in (400, 403, 410, 429):
            status.append("doğrudan engel")
    except Exception as e:
        status.append(f"site hata: {type(e).__name__}")

    # Reader fallback: sadece gerçek ilan linki yakalarsa listeye alır.
    if len(items) < 2:
        try:
            rurl = reader_url(url)
            code, txt, _ = fetch(rurl)
            if code == 200:
                ri = parse_text_items(source, txt, t)
                status.append(f"reader {len(ri)}")
                items.extend(ri)
            else:
                status.append(f"reader {code}")
        except Exception as e:
            status.append(f"reader hata: {type(e).__name__}")

    # Search fallback: Letgo/Facebook kapalı; diğerlerinde sadece gerçek ilan URL'si yakalanır.
    if len(items) < 2:
        try:
            surl = search_url(source, t)
            code, txt, _ = fetch(surl)
            if code == 200:
                si = parse_text_items(source, txt, t)
                status.append(f"arama {len(si)}")
                items.extend(si)
            else:
                status.append(f"arama {code}")
        except Exception as e:
            status.append(f"arama hata: {type(e).__name__}")

    out = []
    seen = set()
    for it in items:
        it["url"] = normalize_url(it.get("url"))
        if not is_detail_url(source, it.get("url")):
            rejected["gerçek ilan linki değil"] = rejected.get("gerçek ilan linki değil", 0) + 1
            continue
        if bad_title(it.get("title")):
            rejected["başlık geçersiz"] = rejected.get("başlık geçersiz", 0) + 1
            continue
        ok, reason = filter_reason(it, t)
        if not ok:
            rejected[reason] = rejected.get(reason, 0) + 1
            continue
        uid = make_uid(it)
        if uid in seen:
            rejected["tekrar"] = rejected.get("tekrar", 0) + 1
            continue
        it["uid"] = uid
        seen.add(uid)
        out.append(it)
        if len(out) >= MAX_ITEMS_PER_SOURCE:
            break
    if rejected:
        status.append("elenen " + ", ".join(f"{k}:{v}" for k,v in sorted(rejected.items())))
    return out, " / ".join(status), url

def make_uid(item):
    u = (item.get("url") or "").split("?")[0].rstrip("/")
    return re.sub(r"^https?://(www\.)?", "", u).lower()


def row_to_track(row):
    d = dict(row)
    try:
        d["sources"] = json.loads(d.get("sources") or "[]")
    except Exception:
        d["sources"] = []
    if not d.get("filter_mode"):
        d["filter_mode"] = "dengeli"
    return d


def check_track(track_id, notify=True):
    con = db()
    row = con.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        con.close(); return
    t = row_to_track(row)
    cleaned_before = cleanup_invalid_listings(con, t)
    statuses = []
    if cleaned_before:
        statuses.append(f"eski filtre dışı ilan temizlendi:{cleaned_before}")
    total_seen = 0
    new_count = 0
    drop_count = 0
    for source in t["sources"]:
        try:
            found, st, _ = source_check(source, t)
        except Exception as e:
            found = []
            st = f"kaynak hatası: {type(e).__name__}: {str(e)[:160]}"
        statuses.append(f"{source}: {st} / liste {len(found)}")
        total_seen += len(found)
        for item in found:
            item["uid"] = item.get("uid") or make_uid(item)
            old = con.execute("SELECT * FROM listings WHERE track_id=? AND uid=?", (track_id, item["uid"])).fetchone()
            if not old:
                con.execute("""INSERT OR IGNORE INTO listings(track_id, source, title, price, year, km, city, url, uid, first_seen, last_seen, raw)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (track_id, source, item.get("title"), item.get("price"), item.get("year"), item.get("km"), item.get("city"), item.get("url"), item["uid"], now_iso(), now_iso(), item.get("raw", "")))
                con.execute("INSERT INTO events(track_id,type,source,title,price_new,url,created_at) VALUES(?,?,?,?,?,?,?)", (track_id,"new",source,item.get("title"),item.get("price"),item.get("url"),now_iso()))
                new_count += 1
                if notify:
                    send_notification(t, "Yeni ilan", item, None, item.get("price"))
            else:
                old_price = old["price"]
                new_price = item.get("price")
                if old_price and new_price and new_price < old_price:
                    con.execute("UPDATE listings SET price=?, year=?, km=?, city=?, title=?, url=?, raw=?, last_seen=? WHERE id=?", (new_price,item.get("year"),item.get("km"),item.get("city"),item.get("title"),item.get("url"),item.get("raw", ""),now_iso(),old["id"]))
                    con.execute("INSERT INTO events(track_id,type,source,title,price_old,price_new,url,created_at) VALUES(?,?,?,?,?,?,?,?)", (track_id,"price_drop",source,item.get("title"),old_price,new_price,item.get("url"),now_iso()))
                    drop_count += 1
                    if notify:
                        send_notification(t, "Fiyat düştü", item, old_price, new_price)
                else:
                    con.execute("UPDATE listings SET last_seen=? WHERE id=?", (now_iso(), old["id"]))
    cleanup_invalid_listings(con, t)
    count = con.execute("SELECT COUNT(*) c FROM listings WHERE track_id=?", (track_id,)).fetchone()["c"]
    con.execute("UPDATE tracks SET last_check_at=?, last_status=?, item_count=?, updated_at=? WHERE id=?", (now_iso(), f"Kontrol tamamlandı. Görülen: {total_seen}, yeni: {new_count}, fiyat düşen: {drop_count} | " + " ; ".join(statuses), count, now_iso(), track_id))
    con.commit(); con.close()


def money(v):
    if not v: return "Fiyat yok"
    return f"{v:,.0f} TL".replace(",", ".")


def send_notification(track, subject, item, old_price=None, new_price=None):
    link = item.get("url") or ""
    text = f"🚗 {subject}\n{item.get('title')}\nKaynak: {item.get('source')}\nFiyat: {money(new_price)}"
    if old_price:
        text += f"\nEski fiyat: {money(old_price)}"
    text += f"\nLink: {link}"
    statuses = []
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = track.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")
    if token and chat_id:
        try:
            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False}, timeout=12)
            statuses.append(f"telegram {r.status_code}")
        except Exception as e:
            statuses.append(f"telegram hata {type(e).__name__}")
    email_to = track.get("notify_email") or os.getenv("DEFAULT_NOTIFY_EMAIL")
    if email_to and os.getenv("SMTP_HOST") and os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"):
        try:
            msg = MIMEText(text, "plain", "utf-8")
            msg["Subject"] = Header(subject, "utf-8")
            msg["From"] = os.getenv("MAIL_FROM") or os.getenv("SMTP_USER")
            msg["To"] = email_to
            with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
                s.starttls()
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
                s.sendmail(msg["From"], [email_to], msg.as_string())
            statuses.append("mail ok")
        except Exception as e:
            statuses.append(f"mail hata {type(e).__name__}")
    return "; ".join(statuses) or "bildirim ayarı yok"


def background_check(track_id):
    def run():
        try:
            check_track(track_id, notify=True)
        except Exception as e:
            con = db(); con.execute("UPDATE tracks SET last_status=?, updated_at=? WHERE id=?", (f"Kontrol hatası: {type(e).__name__}: {e}", now_iso(), track_id)); con.commit(); con.close()
    threading.Thread(target=run, daemon=True).start()


@app.route("/")
def index():
    init_db()
    con = db()
    tracks = [row_to_track(r) for r in con.execute("SELECT * FROM tracks ORDER BY id DESC").fetchall()]
    listings = {}
    for t in tracks:
        cleanup_invalid_listings(con, t)
        rows = con.execute("SELECT * FROM listings WHERE track_id=? ORDER BY first_seen DESC LIMIT 80", (t["id"],)).fetchall()
        listings[t["id"]] = [dict(x) for x in rows if listing_row_passes(x, t)]
    events = [dict(x) for x in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 50").fetchall()]
    con.close()
    all_models = sorted(set(m for b in BRANDS.values() for m in b["models"]))
    all_packages = sorted(set(p for b in BRANDS.values() for p in b["packages"]))
    return render_template("index.html", version=VERSION, brands=BRANDS, cities=CITIES, sources=SOURCES, fuel_options=FUEL_OPTIONS, gear_options=GEAR_OPTIONS, intervals=INTERVALS, tracks=tracks, listings=listings, events=events, all_models=all_models, all_packages=all_packages)


@app.route("/create", methods=["POST"])
def create():
    try:
        init_db()
        f = request.form
        brand = (f.get("brand_custom") or f.get("brand") or "").strip()
        model = (f.get("model_custom") or f.get("model") or "").strip()
        trim = (f.get("trim_custom") or f.get("trim") or "Farketmez").strip() or "Farketmez"
        if not brand or not model:
            return redirect(url_for("index", error="Marka ve model seçilmedi"))
        name = (f.get("name") or f"{brand} {model} {trim if trim!='Farketmez' else ''}".strip()).strip()
        sources = f.getlist("sources") or ["arabam"]
        data = (
            name, brand, model, trim, f.get("city") or "Tüm Türkiye", as_int(f.get("year_min")), as_int(f.get("year_max")), as_int(f.get("km_max")), as_int(f.get("price_min")), as_int(f.get("price_max")), f.get("fuel") or "Farketmez", f.get("gear") or "Farketmez", json.dumps(sources, ensure_ascii=False), as_int(f.get("interval_hours"), DEFAULT_INTERVAL_HOURS), f.get("notify_email") or "", f.get("telegram_chat_id") or "", f.get("filter_mode") or "dengeli", 1, now_iso(), now_iso()
        )
        con = db(); cur = con.cursor()
        cur.execute("""INSERT INTO tracks(name,brand,model,trim,city,year_min,year_max,km_max,price_min,price_max,fuel,gear,sources,interval_hours,notify_email,telegram_chat_id,filter_mode,active,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", data)
        tid = cur.lastrowid
        con.commit(); con.close()
        background_check(tid)
        return redirect(url_for("index"))
    except sqlite3.OperationalError as e:
        # Eski tablo şeması yüzünden /create 500 vermesin. Şemayı yükseltip bir kez daha dene.
        try:
            init_db()
            f = request.form
            brand = (f.get("brand_custom") or f.get("brand") or "").strip()
            model = (f.get("model_custom") or f.get("model") or "").strip()
            trim = (f.get("trim_custom") or f.get("trim") or "Farketmez").strip() or "Farketmez"
            name = (f.get("name") or f"{brand} {model} {trim if trim!='Farketmez' else ''}".strip()).strip()
            sources = f.getlist("sources") or ["arabam"]
            data = (name, brand, model, trim, f.get("city") or "Tüm Türkiye", as_int(f.get("year_min")), as_int(f.get("year_max")), as_int(f.get("km_max")), as_int(f.get("price_min")), as_int(f.get("price_max")), f.get("fuel") or "Farketmez", f.get("gear") or "Farketmez", json.dumps(sources, ensure_ascii=False), as_int(f.get("interval_hours"), DEFAULT_INTERVAL_HOURS), f.get("notify_email") or "", f.get("telegram_chat_id") or "", f.get("filter_mode") or "dengeli", 1, now_iso(), now_iso())
            con = db(); cur = con.cursor()
            cur.execute("""INSERT INTO tracks(name,brand,model,trim,city,year_min,year_max,km_max,price_min,price_max,fuel,gear,sources,interval_hours,notify_email,telegram_chat_id,filter_mode,active,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", data)
            tid = cur.lastrowid
            con.commit(); con.close()
            background_check(tid)
            return redirect(url_for("index"))
        except Exception as e2:
            return f"Takip oluşturulamadı. Veritabanı uyumsuzluğu olabilir. Önce /reset-db?key=temizle çalıştırıp tekrar dene.<br><pre>{type(e).__name__}: {e}\n{type(e2).__name__}: {e2}</pre>", 200
    except Exception as e:
        return f"Takip oluşturulamadı. Hata yakalandı, uygulama çökmedi.<br><pre>{type(e).__name__}: {e}</pre><br><a href='/'>Geri dön</a>", 200


@app.route("/open-url/<int:track_id>/<source>")
def open_url(track_id, source):
    con = db()
    row = con.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    con.close()
    if not row:
        return redirect(url_for("index"))
    t = row_to_track(row)
    return redirect(list_url(source, t))


@app.route("/check/<int:track_id>", methods=["POST", "GET"])
def check(track_id):
    # Beyaz 500 ekranını bitirmek için kontrolü web isteği içinde değil, arka planda başlatıyoruz.
    # Kaynaklardan biri patlarsa takip kartındaki durum alanına yazılır, sayfa çökmez.
    try:
        con = db()
        con.execute("UPDATE tracks SET last_status=?, updated_at=? WHERE id=?", ("Kontrol başlatıldı. 30-90 saniye sonra Yenile'ye bas.", now_iso(), track_id))
        con.commit(); con.close()
    except Exception:
        pass
    background_check(track_id)
    return redirect(url_for("index", v="31", checking=track_id))


@app.route("/delete/<int:track_id>", methods=["POST"])
def delete(track_id):
    con = db(); con.execute("DELETE FROM events WHERE track_id=?", (track_id,)); con.execute("DELETE FROM listings WHERE track_id=?", (track_id,)); con.execute("DELETE FROM tracks WHERE id=?", (track_id,)); con.commit(); con.close()
    return redirect(url_for("index"))


@app.route("/toggle/<int:track_id>", methods=["POST"])
def toggle(track_id):
    con = db(); row = con.execute("SELECT active FROM tracks WHERE id=?", (track_id,)).fetchone()
    if row:
        con.execute("UPDATE tracks SET active=? WHERE id=?", (0 if row["active"] else 1, track_id)); con.commit()
    con.close(); return redirect(url_for("index"))


@app.route("/test-notify", methods=["POST"])
def test_notify():
    fake_track = {"notify_email": request.form.get("notify_email") or os.getenv("DEFAULT_NOTIFY_EMAIL"), "telegram_chat_id": request.form.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")}
    fake_item = {"title":"Araç Avcısı test bildirimi", "source":"test", "price":1234567, "url": request.url_root}
    status = send_notification(fake_track, "Araç Avcısı test", fake_item, None, 1234567)
    return render_template("notify_result.html", status=status, version=VERSION)


@app.route("/health")
def health():
    return jsonify(ok=True, version=VERSION, time=now_iso(), data_dir=DATA_DIR)


@app.route("/reset-cache")
def reset_cache():
    return """<!doctype html><meta charset='utf-8'><script>
    if('serviceWorker' in navigator){navigator.serviceWorker.getRegistrations().then(rs=>rs.forEach(r=>r.unregister()))}
    caches && caches.keys().then(keys=>keys.forEach(k=>caches.delete(k))).finally(()=>location.href='/?v=31&t='+Date.now());
    </script><h2>Önbellek temizleniyor...</h2><a href='/?v=31'>Aç</a>"""


@app.route("/reset-db")
def reset_db():
    if request.args.get("key") != "temizle":
        return "key gerekli: /reset-db?key=temizle", 403
    try:
        if os.path.exists(DB_PATH):
            os.rename(DB_PATH, DB_PATH + ".bak." + str(int(time.time())))
    except Exception:
        pass
    init_db()
    return "Veritabanı temizlendi. / adresine dön."


def scheduler_tick():
    try:
        con = db(); rows = con.execute("SELECT * FROM tracks WHERE active=1").fetchall(); con.close()
        for row in rows:
            t = row_to_track(row)
            last = t.get("last_check_at")
            due = True
            if last:
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    due = (datetime.now(timezone.utc) - last_dt).total_seconds() >= (t.get("interval_hours") or DEFAULT_INTERVAL_HOURS) * 3600
                except Exception:
                    due = True
            if due:
                check_track(t["id"], notify=True)
    except Exception:
        pass


init_db()
if ENABLE_SCHEDULER:
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scheduler_tick, "interval", minutes=15, id="tick", replace_existing=True)
    scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5050")), debug=False)
