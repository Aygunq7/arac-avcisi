import os
import re
import json
import time
import threading
import sqlite3
import hashlib
import smtplib
import unicodedata
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from urllib.parse import quote_plus, quote, urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

VERSION = "v19-arabam-liste-ve-tekil-sonuc"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR") or os.path.join(APP_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "arac_avcisi.sqlite3")
DEFAULT_INTERVAL = int(os.getenv("CHECK_INTERVAL_HOURS", "4"))
SCHEDULER_TICK_MINUTES = int(os.getenv("SCHEDULER_TICK_MINUTES", "15"))
ENABLE_READER = os.getenv("ENABLE_READER", "1") == "1"
JINA_API_KEY = os.getenv("JINA_API_KEY", "").strip()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
app.secret_key = os.getenv("SECRET_KEY", "arac-avcisi-v19")

@app.after_request
def no_cache(resp):
    # Eski PWA/service worker ve tarayıcı önbelleği yüzünden eski app.js çalışmasın.
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# -------------------------------------------------------------
# Hazır kataloglar
# -------------------------------------------------------------
CAR_CATALOG = {
    "Audi": ["A1", "A3", "A4", "A5", "A6", "Q2", "Q3", "Q5", "Q7"],
    "BMW": ["1 Serisi", "2 Serisi", "3 Serisi", "4 Serisi", "5 Serisi", "X1", "X2", "X3", "X5"],
    "Citroen": ["C3", "C3 Aircross", "C4", "C4 X", "C5 Aircross", "Berlingo"],
    "Dacia": ["Sandero", "Sandero Stepway", "Duster", "Jogger", "Lodgy", "Logan"],
    "Fiat": ["Egea", "Linea", "Panda", "500", "Doblo", "Fiorino", "Tipo"],
    "Ford": ["Fiesta", "Focus", "Mondeo", "Kuga", "Puma", "EcoSport", "Courier", "Connect"],
    "Honda": ["Civic", "City", "Jazz", "HR-V", "CR-V", "Accord"],
    "Hyundai": ["i10", "i20", "i30", "Accent", "Elantra", "Bayon", "Kona", "Tucson", "Santa Fe"],
    "Jeep": ["Renegade", "Compass", "Cherokee", "Grand Cherokee", "Avenger"],
    "Kia": ["Picanto", "Rio", "Ceed", "Stonic", "Sportage", "Sorento", "Niro"],
    "Mercedes-Benz": ["A Serisi", "B Serisi", "C Serisi", "E Serisi", "CLA", "GLA", "GLB", "GLC"],
    "Nissan": ["Micra", "Juke", "Qashqai", "X-Trail", "Navara"],
    "Opel": ["Corsa", "Astra", "Insignia", "Crossland", "Mokka", "Grandland", "Combo"],
    "Peugeot": ["208", "308", "301", "2008", "3008", "5008", "Partner", "Rifter"],
    "Renault": ["Clio", "Megane", "Taliant", "Symbol", "Fluence", "Captur", "Kadjar", "Austral", "Kangoo"],
    "Seat": ["Ibiza", "Leon", "Arona", "Ateca"],
    "Skoda": ["Fabia", "Scala", "Octavia", "Superb", "Kamiq", "Karoq", "Kodiaq"],
    "Toyota": ["Yaris", "Corolla", "C-HR", "Auris", "RAV4", "Hilux"],
    "Volkswagen": ["Polo", "Golf", "Passat", "Jetta", "T-Roc", "Tiguan", "Taigo", "Caddy", "Transporter"],
    "Volvo": ["S40", "S60", "S90", "V40", "XC40", "XC60", "XC90"],
}

PKG = ["Farketmez"]
CAR_PACKAGES = {
    "Volkswagen": {
        "Tiguan": PKG + ["1.4 TSI Comfortline", "1.4 TSI Highline", "1.4 TSI ACT DSG", "1.5 TSI Life", "1.5 TSI Elegance", "1.5 TSI R-Line", "2.0 TDI Comfortline", "2.0 TDI Highline", "2.0 TDI R-Line"],
        "Golf": PKG + ["1.0 TSI Life", "1.4 TSI Comfortline", "1.4 TSI Highline", "1.5 TSI Life", "1.5 eTSI Style", "1.5 eTSI R-Line"],
        "Passat": PKG + ["1.4 TSI Comfortline", "1.4 TSI Highline", "1.5 TSI Business", "1.5 TSI Elegance", "1.6 TDI Comfortline", "1.6 TDI Highline"],
        "Polo": PKG + ["1.0 MPI Trendline", "1.0 TSI Comfortline", "1.0 TSI Life", "1.0 TSI Style"],
    },
    "Honda": {"Civic": PKG + ["1.6 i-VTEC Elegance", "1.6 i-VTEC Executive", "1.6 Eco Elegance", "1.6 Eco Executive", "1.5 VTEC Turbo Elegance", "1.5 VTEC Turbo Executive+"]},
    "Ford": {"Kuga": PKG + ["1.5 EcoBoost Style", "1.5 EcoBoost Titanium", "1.5 EcoBoost ST-Line", "1.5 TDCi Titanium", "2.0 TDCi Titanium"], "Focus": PKG + ["Trend X", "Titanium", "ST-Line", "1.5 TDCi Titanium"]},
    "Jeep": {"Compass": PKG + ["1.3 e-Hybrid Limited", "1.3 e-Hybrid Summit", "1.4 MultiAir Limited", "1.6 Multijet Limited"], "Renegade": PKG + ["Longitude", "Limited", "Trailhawk"]},
    "Hyundai": {"Tucson": PKG + ["1.6 T-GDI Comfort", "1.6 T-GDI Elite", "1.6 CRDi Elite"], "Bayon": PKG + ["Jump", "Style", "Elite"], "i20": PKG + ["Jump", "Style", "Elite", "N Line"]},
    "Peugeot": {"3008": PKG + ["Active", "Allure", "GT", "GT Line", "1.5 BlueHDi Allure", "1.5 BlueHDi GT"], "2008": PKG + ["Active", "Allure", "GT"]},
    "Renault": {"Clio": PKG + ["Joy", "Touch", "Icon", "Equilibre", "Techno"], "Megane": PKG + ["Joy", "Touch", "Icon", "1.3 TCe Touch", "1.5 dCi Icon"]},
    "Toyota": {"Corolla": PKG + ["Vision", "Dream", "Flame", "Passion", "Hybrid Dream", "Hybrid Flame"], "C-HR": PKG + ["Dream", "Flame", "Passion", "Hybrid"]},
}

CITIES = ["Tüm Türkiye", "Adana", "Ankara", "Antalya", "Balıkesir", "Bursa", "Eskişehir", "Gaziantep", "İstanbul", "İzmir", "Kayseri", "Kocaeli", "Konya", "Sakarya", "Tekirdağ", "Tokat", "Yalova", "Düzce"]
# İstersen liste genişletildi; bilinmeyen şehir yazılamadığı için link üretici bozulmaz.
CITIES += [c for c in ["Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Artvin", "Aydın", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Isparta", "Mersin", "Kars", "Kastamonu", "Kırklareli", "Kırşehir", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Rize", "Samsun", "Siirt", "Sinop", "Sivas", "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Karabük", "Kilis", "Osmaniye"] if c not in CITIES]

SOURCES = [
    {"key":"sahibinden", "name":"Sahibinden", "base":"https://www.sahibinden.com", "can_parse": True, "reader": True},
    {"key":"arabam", "name":"Arabam", "base":"https://www.arabam.com", "can_parse": True, "reader": True},
    {"key":"letgo", "name":"Letgo", "base":"https://www.letgo.com", "can_parse": False},
    {"key":"facebook", "name":"Facebook Marketplace", "base":"https://www.facebook.com", "can_parse": False},
    {"key":"vavacars", "name":"VavaCars", "base":"https://tr.vava.cars", "can_parse": True, "reader": True},
    {"key":"otoplus", "name":"Otoplus", "base":"https://www.otoplus.com", "can_parse": True, "reader": True},
    {"key":"otokoc", "name":"Otokoç 2. El", "base":"https://www.otokocikinciel.com", "can_parse": True, "reader": True},
    {"key":"arabasepeti", "name":"Araba Sepeti", "base":"https://www.arabasepeti.com", "can_parse": True, "reader": True},
    {"key":"arabalar", "name":"Arabalar.com", "base":"https://www.arabalar.com.tr", "can_parse": True, "reader": True},
]
SOURCE_MAP = {s["key"]: s for s in SOURCES}
SUV_MODELS = {"Tiguan", "T-Roc", "Taigo", "Kuga", "Puma", "EcoSport", "HR-V", "CR-V", "Tucson", "Bayon", "Kona", "Qashqai", "Juke", "X-Trail", "3008", "2008", "5008", "Compass", "Renegade", "Avenger", "Sportage", "Stonic", "Karoq", "Kodiaq", "C-HR", "RAV4", "X1", "X2", "X3", "X5", "GLA", "GLB", "GLC", "XC40", "XC60", "XC90", "Duster", "C3 Aircross", "C5 Aircross", "Mokka", "Grandland", "Crossland"}

# -------------------------------------------------------------
# Yardımcılar
# -------------------------------------------------------------
def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def tr_norm(s):
    s = str(s or "").strip().lower()
    trans = str.maketrans("çğıöşüİı", "cgiosuii")
    s = s.translate(trans)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip()

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", tr_norm(s)).strip("-")

def as_int(v):
    if v is None or v == "":
        return None
    try:
        return int(re.sub(r"\D", "", str(v)))
    except Exception:
        return None

def money(v):
    try:
        return f"{int(v):,}".replace(",", ".") + " TL"
    except Exception:
        return ""

def parse_price(text):
    t = str(text or "")
    pats = [r"(\d{1,3}(?:[\.\s]\d{3})+|\d{6,9})\s*(?:TL|₺|TRY)", r"(?:TL|₺)\s*(\d{1,3}(?:[\.\s]\d{3})+|\d{6,9})"]
    for p in pats:
        m = re.search(p, t, re.I)
        if m:
            val = as_int(m.group(1))
            if val and 10000 <= val <= 100000000:
                return val
    return None

def parse_year(text):
    years = [int(x) for x in re.findall(r"\b(19[8-9]\d|20[0-3]\d)\b", str(text or ""))]
    years = [y for y in years if 1980 <= y <= datetime.now().year + 1]
    return years[0] if years else None

def parse_km(text):
    t = str(text or "")
    m = re.search(r"(\d{1,3}(?:[\.\s]\d{3})+|\d{4,7})\s*(?:km|KM|Km)", t)
    if m:
        val = as_int(m.group(1))
        if val is not None and 0 <= val <= 2000000:
            return val
    return None

def query_text(search):
    parts = [search.get("brand"), search.get("model")]
    pkg = search.get("package_name") or ""
    if pkg and pkg != "Farketmez":
        parts.append(pkg)
    city = search.get("city") or ""
    if city and city != "Tüm Türkiye":
        parts.append(city)
    return " ".join([str(p).strip() for p in parts if p]).strip()

def package_tokens(pkg):
    pkg = tr_norm(pkg or "")
    if not pkg or pkg == "farketmez":
        return []
    stop = {"tsi", "tdi", "tdci", "vtec", "ecoboost", "bmt", "act", "dsg", "edc", "cvt", "plus", "hp", "ps", "multiair", "multijet", "bluehdi", "tce", "dci", "mpi", "line"}
    toks = [x for x in re.split(r"[^a-z0-9]+", pkg) if len(x) > 1 and x not in stop]
    # Comfortline/Elegance/Highline gibi ana paket adları değerli.
    return toks[:6]

def identity_ok(text, search, loose=False):
    hay = tr_norm(text or "")
    b = tr_norm(search.get("brand"))
    m = tr_norm(search.get("model"))
    if b and b not in hay and slug(search.get("brand")) not in hay:
        return False
    if m and m not in hay and slug(search.get("model")) not in hay:
        return False
    toks = package_tokens(search.get("package_name"))
    if toks and not loose:
        return any(t in hay for t in toks)
    return True

def passes_filters(item, search, loose=False):
    raw = " ".join([str(item.get(k) or "") for k in ["title", "raw_text", "url", "city"]])
    if not identity_ok(raw, search, loose=loose):
        return False
    gear = tr_norm(search.get("gear"))
    h = tr_norm(raw)
    if gear and gear != "farketmez":
        if "otomatik" in gear and "manuel" in h and not any(x in h for x in ["otomatik", "dsg", "edc", "cvt", "yari otomatik"]):
            return False
        if "manuel" in gear and any(x in h for x in ["otomatik", "dsg", "edc", "cvt", "yari otomatik"]):
            return False
    fuel = tr_norm(search.get("fuel"))
    if fuel and fuel != "farketmez" and fuel not in h and not loose:
        if not (fuel == "benzin" and "benzin" in h):
            return False
    pmin, pmax = as_int(search.get("price_min")), as_int(search.get("price_max"))
    ymin, ymax = as_int(search.get("year_min")), as_int(search.get("year_max"))
    kmmax = as_int(search.get("km_max"))
    price = as_int(item.get("price"))
    if pmin and price is not None and price < pmin: return False
    if pmax and price is not None and price > pmax: return False
    if (pmin or pmax) and price is None and not loose: return False
    year = as_int(item.get("year"))
    if ymin and year is not None and year < ymin: return False
    if ymax and year is not None and year > ymax: return False
    if (ymin or ymax) and year is None and not loose: return False
    km = as_int(item.get("km"))
    if kmmax and km is not None and km > kmmax: return False
    if kmmax and km is None and not loose: return False
    city = search.get("city") or ""
    if city and city != "Tüm Türkiye":
        item_city = tr_norm(item.get("city") or raw)
        if tr_norm(city) not in item_city and not loose:
            return False
    return True

def item_key(url, title=""):
    if url:
        return hashlib.sha1(url.encode("utf-8", errors="ignore")).hexdigest()
    return hashlib.sha1((title or "").encode("utf-8", errors="ignore")).hexdigest()

# -------------------------------------------------------------
# URL üretimi
# -------------------------------------------------------------
def category(search):
    return "arazi-suv-pick-up" if search.get("model") in SUV_MODELS else "otomobil"

def fuel_seg(search):
    f = tr_norm(search.get("fuel"))
    if f in ["benzin", "benzinli"]: return "benzin"
    if f in ["dizel"]: return "dizel"
    if "lpg" in f: return "benzin-lpg"
    if "hibrit" in f: return "hibrit"
    if "elektrik" in f: return "elektrikli"
    return ""

def gear_seg(search):
    g = tr_norm(search.get("gear"))
    if "otomatik" in g: return "otomatik"
    if "manuel" in g: return "manuel"
    return ""

def full_slug(search, include_city=False, include_fuel=False, include_gear=False):
    parts = [slug(search.get("brand")), slug(search.get("model"))]
    pkg = search.get("package_name") or ""
    if pkg and pkg != "Farketmez": parts.append(slug(pkg))
    if include_city and (search.get("city") or "") != "Tüm Türkiye": parts.append(slug(search.get("city")))
    if include_fuel and fuel_seg(search): parts.append(fuel_seg(search))
    if include_gear and gear_seg(search): parts.append(gear_seg(search))
    return "-".join([p for p in parts if p])

def build_url(source_key, search):
    q = quote_plus(query_text(search))
    city = search.get("city") or "Tüm Türkiye"
    params = {}
    if as_int(search.get("price_min")): params["price_min"] = as_int(search.get("price_min"))
    if as_int(search.get("price_max")): params["price_max"] = as_int(search.get("price_max"))
    if as_int(search.get("year_min")): params["year_min"] = as_int(search.get("year_min"))
    if as_int(search.get("year_max")): params["year_max"] = as_int(search.get("year_max"))
    if as_int(search.get("km_max")): params["km_max"] = as_int(search.get("km_max"))
    if source_key == "sahibinden":
        base = f"https://www.sahibinden.com/vasita?query_text={q}&sorting=date_desc"
        # Sahibinden'in yaygın araç parametreleri. Değişirse ana query yine çalışır.
        sp = {}
        if as_int(search.get("price_min")): sp["price_min"] = as_int(search.get("price_min"))
        if as_int(search.get("price_max")): sp["price_max"] = as_int(search.get("price_max"))
        if as_int(search.get("year_min")): sp["a5_min"] = as_int(search.get("year_min"))
        if as_int(search.get("year_max")): sp["a5_max"] = as_int(search.get("year_max"))
        if as_int(search.get("km_max")): sp["a4_max"] = as_int(search.get("km_max"))
        return base + ("&" + urlencode(sp) if sp else "")
    if source_key == "arabam":
        path = full_slug(search, include_city=(city != "Tüm Türkiye"), include_fuel=True, include_gear=True)
        return f"https://www.arabam.com/ikinci-el/{category(search)}/{path}" + ("?" + urlencode(params) if params else "")
    if source_key == "letgo":
        return f"https://www.letgo.com/tr-tr/q-{full_slug(search)}"
    if source_key == "facebook":
        return f"https://www.facebook.com/marketplace/search/?query={q}"
    if source_key == "vavacars":
        return f"https://tr.vava.cars/cars-for-you?search={q}"
    if source_key == "otoplus":
        return f"https://www.otoplus.com/{slug(search.get('brand'))}/{slug(search.get('model'))}"
    if source_key == "otokoc":
        return f"https://www.otokocikinciel.com/ikinci-el-{slug(search.get('brand'))}-{slug(search.get('model'))}"
    if source_key == "arabasepeti":
        return f"https://www.arabasepeti.com/ikinci-el-araclar?search={q}"
    if source_key == "arabalar":
        return f"https://www.arabalar.com.tr/ikinci-el?kelime={q}"
    return ""

# -------------------------------------------------------------
# Veritabanı
# -------------------------------------------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def ensure_column(conn, table, column, decl):
    """Eski Render veritabanlarını yeni sürüme taşır.
    CREATE TABLE IF NOT EXISTS eski tabloya yeni kolon eklemez; bu yüzden
    önceki sürümlerde POST /api/searches çöküyordu.
    """
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db():
    conn = db(); c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS searches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        brand TEXT NOT NULL,
        model TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_id INTEGER NOT NULL,
        source_key TEXT NOT NULL,
        source_name TEXT NOT NULL,
        item_key TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT NOT NULL,
        first_seen_at TEXT NOT NULL,
        last_seen_at TEXT NOT NULL,
        UNIQUE(search_id, source_key, item_key)
    );
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        search_id INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # searches tablosu eski sürümlerden gelirse eksik kolonları ekle.
    search_cols = {
        "package_name": "TEXT DEFAULT 'Farketmez'",
        "city": "TEXT DEFAULT 'Tüm Türkiye'",
        "year_min": "INTEGER",
        "year_max": "INTEGER",
        "price_min": "INTEGER",
        "price_max": "INTEGER",
        "km_max": "INTEGER",
        "fuel": "TEXT DEFAULT 'Farketmez'",
        "gear": "TEXT DEFAULT 'Farketmez'",
        "sources_json": "TEXT DEFAULT '[]'",
        "email_to": "TEXT",
        "telegram_chat_id": "TEXT",
        "check_interval_hours": "INTEGER DEFAULT 4",
        "baseline_done": "INTEGER DEFAULT 0",
        "active": "INTEGER DEFAULT 1",
        "last_checked_at": "TEXT",
        "last_status": "TEXT"
    }
    for col, decl in search_cols.items():
        ensure_column(conn, "searches", col, decl)

    item_cols = {
        "city": "TEXT",
        "year": "INTEGER",
        "km": "INTEGER",
        "first_price": "INTEGER",
        "current_price": "INTEGER",
        "lowest_price": "INTEGER",
        "last_notified_price": "INTEGER"
    }
    for col, decl in item_cols.items():
        ensure_column(conn, "items", col, decl)

    event_cols = {
        "item_id": "INTEGER",
        "old_price": "INTEGER",
        "new_price": "INTEGER",
        "source_name": "TEXT",
        "url": "TEXT",
        "notification_status": "TEXT"
    }
    for col, decl in event_cols.items():
        ensure_column(conn, "events", col, decl)

    # Eski kayıtlardaki boş değerleri yeni varsayılanlara çek.
    c.execute("UPDATE searches SET sources_json='[]' WHERE sources_json IS NULL OR sources_json='' ")
    c.execute("UPDATE searches SET package_name='Farketmez' WHERE package_name IS NULL OR package_name='' ")
    c.execute("UPDATE searches SET city='Tüm Türkiye' WHERE city IS NULL OR city='' ")
    c.execute("UPDATE searches SET fuel='Farketmez' WHERE fuel IS NULL OR fuel='' ")
    c.execute("UPDATE searches SET gear='Farketmez' WHERE gear IS NULL OR gear='' ")
    c.execute("UPDATE searches SET check_interval_hours=4 WHERE check_interval_hours IS NULL OR check_interval_hours<1 ")
    c.execute("UPDATE searches SET active=1 WHERE active IS NULL ")
    c.execute("UPDATE searches SET baseline_done=0 WHERE baseline_done IS NULL ")
    conn.commit(); conn.close()

def row_to_search(r):
    d = dict(r)
    try: d["sources"] = json.loads(d.get("sources_json") or "[]")
    except Exception: d["sources"] = []
    d["package_name"] = d.get("package_name") or "Farketmez"
    d["interval_hours"] = d.get("check_interval_hours") or DEFAULT_INTERVAL
    d["open_urls"] = {k: build_url(k, d) for k in d["sources"] if k in SOURCE_MAP}
    return d

# -------------------------------------------------------------
# Bildirimler
# -------------------------------------------------------------
def notify(text, search=None):
    statuses = []
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = (search or {}).get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if token and chat:
        try:
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat, "text": text, "disable_web_page_preview": True}, timeout=15)
            statuses.append("telegram ok")
        except Exception as e:
            statuses.append(f"telegram hata: {e.__class__.__name__}")
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    email_to = (search or {}).get("email_to") or os.getenv("MAIL_TO", "").strip()
    if smtp_host and email_to:
        try:
            msg = MIMEText(text, "plain", "utf-8")
            msg["Subject"] = "Araç Avcısı bildirimi"
            msg["From"] = os.getenv("MAIL_FROM") or os.getenv("SMTP_USER")
            msg["To"] = email_to
            with smtplib.SMTP(smtp_host, int(os.getenv("SMTP_PORT", "587")), timeout=20) as s:
                s.starttls()
                if os.getenv("SMTP_USER"):
                    s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
                s.send_message(msg)
            statuses.append("mail ok")
        except Exception as e:
            statuses.append(f"mail hata: {e.__class__.__name__}")
    return "; ".join(statuses) or "bildirim kapalı"

# -------------------------------------------------------------
# Fetch + parse
# -------------------------------------------------------------
def headers():
    return {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept-Language":"tr-TR,tr;q=0.9,en;q=0.8", "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}

def reader_fetch(url):
    if not ENABLE_READER:
        return None, "reader kapalı"
    rurl = "https://r.jina.ai/" + url
    h = {"User-Agent":"AraçAvcisi/1.0", "Accept":"text/plain, text/markdown, */*"}
    if JINA_API_KEY:
        h["Authorization"] = f"Bearer {JINA_API_KEY}"
    try:
        r = requests.get(rurl, headers=h, timeout=40)
        if r.status_code < 400 and r.text:
            return r.text, f"reader ok"
        return None, f"reader HTTP {r.status_code}"
    except Exception as e:
        return None, f"reader hata {e.__class__.__name__}"

def clean_title(t):
    t = re.sub(r"\s+", " ", str(t or "")).strip(" -|•")
    bad = ["filtrele", "arama", "sonuc bulunamadi", "sonuç bulunamadı", "cerez", "gizlilik", "uygulama", "fiyat", "kilometre", "model yili", "model yılı", "siralama", "sıralama", "anasayfa"]
    if tr_norm(t) in bad or any(b == tr_norm(t) for b in bad) or len(t) < 8:
        return ""
    return t[:220]

def extract_city_text(text):
    nt = tr_norm(text)
    for c in CITIES:
        if c != "Tüm Türkiye" and tr_norm(c) in nt:
            return c
    return None

def real_listing_url(key, url):
    p = urlparse(url).path.lower()
    q = urlparse(url).query.lower()
    # Sadece gerçek ilan detay linkleri kabul edilir.
    # Marka/model arama sayfaları veya filtre sayfaları ilan gibi listeye düşmesin.
    if key == "sahibinden":
        return "/ilan/" in p
    if key == "arabam":
        return "/ilan/" in p
    if key == "letgo":
        return "/item/" in p or "/ilan/" in p
    if key == "otoplus":
        # Otoplus kategori URL'leri şu tiptedir: /volkswagen/tiguan/...
        # Bunlar ilan değildir. Sadece açık detay kalıplarını kabul ediyoruz.
        return any(x in p for x in ["/arac/", "/arac-detay", "/detay/", "/detail/"])
    if key == "otokoc":
        return any(x in p for x in ["arac-detay", "/detay/", "ikinci-el-arac/"]) and not p.rstrip("/").startswith("/ikinci-el-")
    if key == "vavacars":
        return any(x in p for x in ["/car/", "/detail/", "/arac/"])
    if key == "arabasepeti":
        return any(x in p for x in ["/ilan/", "/detay", "/arac/"])
    if key == "arabalar":
        return any(x in p for x in ["/ilan/", "/detay", "/arac/"])
    return any(x in p for x in ["/ilan/", "/detay", "/detail", "/arac/"])

def synthetic_url(final_url, source_key, signature):
    # Arabam gibi bazı liste sayfaları Reader metninde ilan detay linkini vermiyor.
    # Bu durumda kullanıcıyı doğru filtrelenmiş liste sayfasına götüren tekil bir bağlantı üretiyoruz.
    h = hashlib.sha1((source_key + "|" + signature).encode("utf-8", errors="ignore")).hexdigest()[:12]
    return final_url.split("#")[0] + f"#{source_key}-{h}"

def item_from_text(source, title, url, text, search, loose=False):
    title = clean_title(title) or clean_title(text.split("\n")[0] if text else "")
    if not title or not url:
        return None
    item = {"source_key": source["key"], "source_name": source["name"], "title": title, "url": url, "price": parse_price(text), "year": parse_year(text), "km": parse_km(text), "city": extract_city_text(text), "raw_text": text[:2500]}
    if passes_filters(item, search, loose=loose):
        return item
    return None

def parse_html(source, html, search, final_url):
    soup = BeautifulSoup(html or "", "html.parser")
    out, seen = [], set()
    key = source["key"]
    # İlan linki olan blokları yakala. Sahte kategori/filtre metnini almıyoruz.
    for a in soup.find_all("a", href=True):
        full = urljoin(source["base"], a.get("href", "")).split("#")[0]
        if urlparse(full).netloc.replace("www.", "").split(":")[0] != urlparse(source["base"]).netloc.replace("www.", "").split(":")[0]:
            continue
        if not real_listing_url(key, full):
            continue
        parent = a
        for _ in range(4):
            if parent.parent: parent = parent.parent
        text = parent.get_text("\n", strip=True)
        title = a.get_text(" ", strip=True) or (text.split("\n")[0] if text else "")
        item = item_from_text(source, title, full, text, search, loose=False)
        if item:
            k = item_key(item["url"], item["title"])
            if k not in seen:
                seen.add(k); out.append(item)
        if len(out) >= 50: break
    # Gerçek ilan linki yoksa metinden sentetik ilan üretmiyoruz.
    # Önceki sürümlerde "Filtrele" gibi sayfa metinleri araç sanılıyordu.
    return dedupe_items(out)


def parse_arabam_reader_text(source, text, search, final_url):
    """Arabam liste sayfasının Reader çıktısından gerçek araç satırlarını toplar.
    Arabam sayfası çoğu zaman HTML içinde doğrudan ilan linki vermiyor;
    fakat liste metninde yıl, km, fiyat ve şehir satırları var.
    Bu fonksiyon sadece bu alanlar birlikte varsa kayıt üretir.
    """
    raw_lines = [re.sub(r"\s+", " ", x).strip() for x in (text or "").splitlines()]
    lines = [x for x in raw_lines if x and x not in ["#", "##", "###"]]
    out, seen = [], set()
    brand_model = tr_norm(f"{search.get('brand')} {search.get('model')}")
    # Arama başlığı: Volkswagen Tiguan 1.4 TSI Comfortline
    # Sonrasında ilan başlığı + yıl + km + renk + fiyat + tarih + şehir gelir.
    for i, line in enumerate(lines):
        nline = tr_norm(line)
        if not brand_model or not nline.startswith(brand_model):
            continue
        if any(x in nline for x in ["fiyatlari", "fiyatları", "ikinci el", "populer", "sahibinden volkswagen modelleri"]):
            continue
        window_lines = lines[i:i+12]
        window = "\n".join(window_lines)
        price = parse_price(window)
        year = parse_year(window)
        km = parse_km(window)
        if not (price and year and km is not None):
            continue
        # Başlık, marka/model satırından sonraki ilk anlamlı satırdır.
        title = ""
        for cand in lines[i+1:i+7]:
            cn = tr_norm(cand)
            # Fiyat, saf yıl, saf km, renk/tarih/aksiyon satırları başlık değildir.
            if parse_price(cand):
                continue
            if re.fullmatch(r"(19[8-9]\d|20[0-3]\d)", cand.strip()):
                continue
            if re.fullmatch(r"\d{1,3}(?:[\.\s]\d{3})+", cand.strip()):
                continue
            if re.search(r"haziran|ocak|şubat|subat|mart|nisan|mayıs|mayis|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik", cn):
                continue
            if cn in ["goster", "göster", "karsilastir", "karşılaştır", "beyaz", "siyah", "gri", "kirmizi", "kırmızı", "bej", "mavi", "lacivert", "kahverengi"]:
                continue
            if len(cand) >= 8:
                title = cand
                break
        if not title:
            title = line
        city = extract_city_text(window)
        signature = f"{title}|{price}|{year}|{km}|{city or ''}"
        item = {
            "source_key": source["key"],
            "source_name": source["name"],
            "title": clean_title(title),
            "url": synthetic_url(final_url, "arabam", signature),
            "price": price,
            "year": year,
            "km": km,
            "city": city,
            "raw_text": window[:2500]
        }
        if not item["title"]:
            continue
        # Reader listesinde bazen şehir eksik olabilir; ancak fiyat/yıl/km varsa ve marka-model-paket uyuyorsa kabul et.
        if passes_filters(item, search, loose=False):
            k = hashlib.sha1(signature.encode("utf-8", errors="ignore")).hexdigest()
            if k not in seen:
                seen.add(k); out.append(item)
        if len(out) >= 40:
            break
    return out

def dedupe_items(items):
    out, seen = [], set()
    for item in items or []:
        sig = "|".join([
            tr_norm(item.get("source_key")),
            tr_norm(item.get("title")),
            str(as_int(item.get("price")) or ""),
            str(as_int(item.get("year")) or ""),
            str(as_int(item.get("km")) or ""),
            tr_norm(item.get("city") or "")
        ])
        if sig in seen:
            continue
        seen.add(sig); out.append(item)
    return out

def parse_reader_text(source, text, search, final_url):
    if source.get("key") == "arabam":
        return parse_arabam_reader_text(source, text, search, final_url)
    out, seen = [], set()
    key = source["key"]
    # Markdown linkleri önce.
    md = re.compile(r"\[([^\]]{3,220})\]\((https?://[^)\s]+)\)")
    for m in md.finditer(text or ""):
        title, url = m.group(1), m.group(2).rstrip(".")
        host_ok = urlparse(source["base"]).netloc.replace("www.", "") in urlparse(url).netloc.replace("www.", "")
        if not host_ok or not real_listing_url(key, url):
            continue
        window = text[max(0, m.start()-700):m.end()+1000]
        item = item_from_text(source, title, url, window, search, loose=(key=="sahibinden"))
        if item:
            k = item_key(item["url"], item["title"])
            if k not in seen:
                seen.add(k); out.append(item)
        if len(out) >= 50: break
    # Reader metninden URL olmadan sentetik ilan üretmiyoruz.
    # Gerçek ilan linki yoksa liste boş kalır, sahte kayıt oluşmaz.
    return dedupe_items(out)

def fetch_source(source, search):
    url = build_url(source["key"], search)
    if not source.get("can_parse"):
        return [], {"source": source["name"], "url": url, "status": "Bu kaynak uygulama içi liste vermiyor, siteyi aç butonu hazır", "status_code": None}
    try:
        r = requests.get(url, headers=headers(), timeout=35, allow_redirects=True)
        status = f"HTTP {r.status_code}"
        if r.status_code < 400:
            items = parse_html(source, r.text, search, r.url or url)
            if items:
                return items, {"source": source["name"], "url": url, "status": f"{status} / liste: {len(items)}", "status_code": r.status_code}
            if source.get("reader"):
                txt, rs = reader_fetch(url)
                if txt:
                    items = parse_reader_text(source, txt, search, url)
                    if items:
                        return items, {"source": source["name"], "url": url, "status": f"{status} / reader liste: {len(items)}", "status_code": r.status_code}
                return [], {"source": source["name"], "url": url, "status": f"{status} / liste yok / {rs}", "status_code": r.status_code}
            return [], {"source": source["name"], "url": url, "status": f"{status} / liste yok", "status_code": r.status_code}
        # 429/403 gibi durumlarda sadece reader dene; gizli giriş/proxy yok.
        if source.get("reader"):
            txt, rs = reader_fetch(url)
            if txt:
                items = parse_reader_text(source, txt, search, url)
                if items:
                    return items, {"source": source["name"], "url": url, "status": f"{status} / reader liste: {len(items)}", "status_code": r.status_code}
            return [], {"source": source["name"], "url": url, "status": f"{status} / {rs}", "status_code": r.status_code}
        return [], {"source": source["name"], "url": url, "status": status, "status_code": r.status_code}
    except Exception as e:
        return [], {"source": source["name"], "url": url, "status": f"Hata: {e.__class__.__name__}", "status_code": None}

# -------------------------------------------------------------
# Arama motoru
# -------------------------------------------------------------
def run_search(search_id):
    conn = db()
    row = conn.execute("SELECT * FROM searches WHERE id=?", (search_id,)).fetchone()
    if not row:
        conn.close(); return {"ok": False, "error": "Takip bulunamadı"}
    search = row_to_search(row)
    baseline = not bool(search.get("baseline_done"))
    seen_total = new_total = drop_total = 0
    logs = []
    for key in search.get("sources", []):
        source = SOURCE_MAP.get(key)
        if not source: continue
        items, log = fetch_source(source, search)
        logs.append(log)
        for item in items:
            seen_total += 1
            ik = item_key(item.get("url"), item.get("title"))
            old = conn.execute("SELECT * FROM items WHERE search_id=? AND source_key=? AND item_key=?", (search_id, key, ik)).fetchone()
            price = as_int(item.get("price"))
            if old is None:
                cur = conn.execute("""INSERT OR IGNORE INTO items(search_id,source_key,source_name,item_key,title,url,city,year,km,first_price,current_price,lowest_price,first_seen_at,last_seen_at,last_notified_price)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (search_id, key, source["name"], ik, item.get("title") or "İlan", item.get("url"), item.get("city"), item.get("year"), item.get("km"), price, price, price, now_iso(), now_iso(), price))
                if not baseline and search.get("baseline_done"):
                    new_total += 1
                    text = f"Yeni araç bulundu\n{search.get('brand')} {search.get('model')}\n{source['name']}: {item.get('title')}\n{money(price)}\n{item.get('url')}"
                    ns = notify(text, search)
                    conn.execute("INSERT INTO events(search_id,item_id,event_type,title,new_price,source_name,url,created_at,notification_status) VALUES(?,?,?,?,?,?,?,?,?)", (search_id, cur.lastrowid, "new", item.get("title"), price, source["name"], item.get("url"), now_iso(), ns))
            else:
                old_price = as_int(old["current_price"])
                lowest = min([x for x in [as_int(old["lowest_price"]), price] if x is not None], default=price)
                conn.execute("UPDATE items SET title=?, url=?, city=?, year=?, km=?, current_price=?, lowest_price=?, last_seen_at=? WHERE id=?", (item.get("title"), item.get("url"), item.get("city"), item.get("year"), item.get("km"), price, lowest, now_iso(), old["id"]))
                if price is not None and old_price is not None and price < old_price and not baseline and search.get("baseline_done"):
                    drop_total += 1
                    text = f"Fiyat düştü\n{source['name']}: {item.get('title')}\nEski: {money(old_price)}\nYeni: {money(price)}\n{item.get('url')}"
                    ns = notify(text, search)
                    conn.execute("INSERT INTO events(search_id,item_id,event_type,title,old_price,new_price,source_name,url,created_at,notification_status) VALUES(?,?,?,?,?,?,?,?,?,?)", (search_id, old["id"], "price_drop", item.get("title"), old_price, price, source["name"], item.get("url"), now_iso(), ns))
    status = f"Kontrol tamamlandı. Görülen: {seen_total}, yeni: {new_total}, fiyat düşen: {drop_total} | " + " ; ".join([f"{l['source']}: {l['status']}" for l in logs])
    conn.execute("UPDATE searches SET last_checked_at=?, last_status=?, baseline_done=1 WHERE id=?", (now_iso(), status, search_id))
    conn.commit(); conn.close()
    return {"ok": True, "seen": seen_total, "new": new_total, "price_drop": drop_total, "logs": logs, "status": status}

def scheduler_tick():
    conn = db(); rows = conn.execute("SELECT * FROM searches WHERE active=1").fetchall(); conn.close()
    for r in rows:
        s = row_to_search(r)
        last = s.get("last_checked_at")
        due = True
        if last:
            try:
                dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                due = datetime.now(timezone.utc) >= dt + timedelta(hours=int(s.get("check_interval_hours") or DEFAULT_INTERVAL))
            except Exception:
                due = True
        if due:
            try: run_search(s["id"])
            except Exception: pass

def safe_run_search(search_id):
    try:
        return run_search(search_id)
    except Exception as e:
        # Takip kaydı asla kaybolmasın. Arama motoru patlarsa durum satırına yaz.
        try:
            conn = db()
            conn.execute("UPDATE searches SET last_checked_at=?, last_status=? WHERE id=?", (now_iso(), f"Arama hatası: {e.__class__.__name__}: {e}", search_id))
            conn.commit(); conn.close()
        except Exception:
            pass
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def queue_initial_run(search_id):
    t = threading.Thread(target=safe_run_search, args=(search_id,), daemon=True)
    t.start()

# -------------------------------------------------------------
# Routes
# -------------------------------------------------------------
@app.route("/reset-cache")
def reset_cache():
    # Bu sayfa eski mobil PWA/service worker kaydını temizler ve yeni sürüme yönlendirir.
    return """<!doctype html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Önbellek temizleniyor</title><style>body{font-family:system-ui;background:#0b1220;color:#eaf2ff;padding:32px} .box{max-width:620px;margin:auto;background:#151d2b;border:1px solid #2b374a;border-radius:20px;padding:24px}</style></head><body><div class='box'><h1>Araç Avcısı temizleniyor</h1><p>Eski uygulama önbelleği siliniyor. Birkaç saniye içinde yeni sürüm açılacak.</p></div><script>(async()=>{try{if('serviceWorker' in navigator){const regs=await navigator.serviceWorker.getRegistrations(); await Promise.all(regs.map(r=>r.unregister()));} if(window.caches){const keys=await caches.keys(); await Promise.all(keys.map(k=>caches.delete(k)));}}catch(e){} location.replace('/?v=19&cache=temiz');})();</script></body></html>"""

@app.route("/")
def index():
    return render_template("index.html", version=VERSION)

@app.route("/health")
def health():
    return jsonify({"ok": True, "version": VERSION, "time": now_iso(), "data_dir": DATA_DIR, "reader_enabled": ENABLE_READER})

@app.route("/api/options")
def api_options_legacy():
    # Eski mobil PWA önbellekte kalırsa tamamen kırılmasın diye eski isimlerle katalog döndürür.
    return jsonify({
        "brands": CAR_CATALOG,
        "packages": CAR_PACKAGES,
        "cities": CITIES,
        "sources": SOURCES,
        "default_interval_hours": DEFAULT_INTERVAL,
        "default_packages": ["Farketmez"]
    })

@app.route("/api/catalog")
def api_catalog():
    return jsonify({"brands": CAR_CATALOG, "packages": CAR_PACKAGES, "cities": CITIES, "sources": SOURCES, "default_interval_hours": DEFAULT_INTERVAL})

@app.route("/api/searches", methods=["GET", "POST"])
def api_searches():
    conn = db()
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        sources = data.get("sources") or [s["key"] for s in SOURCES]
        sources = [s for s in sources if s in SOURCE_MAP]
        if not sources:
            conn.close(); return jsonify({"ok": False, "error": "En az bir site seçmelisin."}), 400
        brand = (data.get("brand") or "").strip()
        model = (data.get("model") or "").strip()
        if not brand or not model:
            conn.close(); return jsonify({"ok": False, "error": "Marka ve model seçmelisin."}), 400
        name = (data.get("name") or f"{brand} {model}").strip()
        try:
            interval = max(1, min(int(data.get("check_interval_hours") or DEFAULT_INTERVAL), 168))
        except Exception:
            interval = DEFAULT_INTERVAL
        cur = conn.execute("""INSERT INTO searches(name,brand,model,package_name,city,year_min,year_max,price_min,price_max,km_max,fuel,gear,sources_json,email_to,telegram_chat_id,check_interval_hours,baseline_done,active,created_at,last_status)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,1,?,?)""", (name, brand, model, data.get("package_name") or "Farketmez", data.get("city") or "Tüm Türkiye", as_int(data.get("year_min")), as_int(data.get("year_max")), as_int(data.get("price_min")), as_int(data.get("price_max")), as_int(data.get("km_max")), data.get("fuel") or "Farketmez", data.get("gear") or "Farketmez", json.dumps(sources, ensure_ascii=False), data.get("email_to"), data.get("telegram_chat_id"), interval, now_iso(), "Takip kaydedildi. Başlangıç araması arkada çalışıyor..."))
        conn.commit(); sid = cur.lastrowid; conn.close()
        queue_initial_run(sid)  # Ağ/siteler yavaşlasa bile takip kaydı kaybolmaz.
        return jsonify({"ok": True, "id": sid, "queued": True, "message": "Takip kaydedildi. Başlangıç araması arkada çalışıyor."})
    rows = [row_to_search(r) for r in conn.execute("SELECT * FROM searches ORDER BY id DESC").fetchall()]
    conn.close(); return jsonify({"ok": True, "searches": rows})

@app.route("/api/searches/<int:sid>/run", methods=["POST"])
def api_run(sid):
    return jsonify(safe_run_search(sid))

@app.route("/api/searches/<int:sid>/toggle", methods=["POST"])
def api_toggle(sid):
    conn = db(); r = conn.execute("SELECT active FROM searches WHERE id=?", (sid,)).fetchone()
    if not r: conn.close(); return jsonify({"ok": False, "error":"Bulunamadı"}), 404
    active = 0 if r["active"] else 1
    conn.execute("UPDATE searches SET active=? WHERE id=?", (active, sid)); conn.commit(); conn.close()
    return jsonify({"ok": True, "active": active})

@app.route("/api/searches/<int:sid>/interval", methods=["POST"])
def api_interval(sid):
    data = request.get_json(force=True)
    interval = max(1, min(int(data.get("check_interval_hours") or DEFAULT_INTERVAL), 168))
    conn = db(); conn.execute("UPDATE searches SET check_interval_hours=? WHERE id=?", (interval, sid)); conn.commit(); conn.close()
    return jsonify({"ok": True, "interval": interval})

@app.route("/api/searches/<int:sid>", methods=["DELETE"])
def api_delete(sid):
    conn = db(); conn.execute("DELETE FROM items WHERE search_id=?", (sid,)); conn.execute("DELETE FROM events WHERE search_id=?", (sid,)); conn.execute("DELETE FROM searches WHERE id=?", (sid,)); conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/searches/<int:sid>/items")
def api_items(sid):
    conn = db(); rows = [dict(r) for r in conn.execute("SELECT * FROM items WHERE search_id=? ORDER BY last_seen_at DESC, current_price IS NULL, current_price ASC", (sid,)).fetchall()]; conn.close()
    for x in rows:
        x["price_text"] = money(x.get("current_price")) if x.get("current_price") else ""
        x["km_text"] = f"{int(x['km']):,}".replace(",", ".") + " km" if x.get("km") else ""
    return jsonify({"ok": True, "items": rows})

@app.route("/api/events")
def api_events():
    conn = db()
    rows = [dict(r) for r in conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 50").fetchall()]
    conn.close()
    return jsonify({"ok": True, "events": rows})

@app.route("/api/searches/<int:sid>/links")
def api_links(sid):
    conn = db(); r = conn.execute("SELECT * FROM searches WHERE id=?", (sid,)).fetchone(); conn.close()
    if not r: return jsonify({"ok": False}), 404
    s = row_to_search(r)
    links = [{"key": k, "name": SOURCE_MAP[k]["name"], "url": build_url(k, s)} for k in s.get("sources", []) if k in SOURCE_MAP]
    return jsonify({"ok": True, "links": links})

_scheduler = None
_booted = False


def cleanup_old_fake_items():
    bad = ["filtrele", "garantili 2. el", "garantili ikinci el", "araclari listeleniyor", "araçları listeleniyor", "sonuc bulunamadi", "sonuç bulunamadı", "model yılı", "kilometre", "sıralama"]
    conn = db()
    rows = conn.execute("SELECT id,title,url,source_key FROM items").fetchall()
    seen = set()
    for r in rows:
        t = tr_norm(r["title"] or "")
        u = r["url"] or ""
        src = r["source_key"] or ""
        bad_url = False
        # Otoplus kategori arama linkleri eski sürümlerde ilan gibi kaydedilmişti.
        if src == "otoplus" and not real_listing_url("otoplus", u):
            bad_url = True
        if "#otoplus-" in u or "#reader-" in u:
            bad_url = True
        sig = (src, t, u.split("#")[0])
        duplicate = sig in seen
        seen.add(sig)
        if duplicate or any(b in t for b in bad) or bad_url:
            conn.execute("DELETE FROM items WHERE id=?", (r["id"],))
    conn.commit(); conn.close()

def boot():
    global _scheduler, _booted
    if _booted: return
    init_db()
    cleanup_old_fake_items()
    if os.getenv("ENABLE_SCHEDULER", "1") == "1":
        _scheduler = BackgroundScheduler(daemon=True)
        _scheduler.add_job(scheduler_tick, "interval", minutes=SCHEDULER_TICK_MINUTES, id="tick", replace_existing=True)
        _scheduler.start()
    _booted = True

boot()

if __name__ == "__main__":
    app.run(host=os.getenv("APP_HOST", "0.0.0.0"), port=int(os.getenv("PORT", "5050")), debug=False)
