import os
import re
import json
import time
import sqlite3
import hashlib
import smtplib
import unicodedata
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from urllib.parse import quote_plus, urljoin, urlparse, parse_qs, unquote

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.getenv("DATA_DIR") or os.path.join(APP_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "arac_avcisi.sqlite3")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.secret_key = os.getenv("SECRET_KEY", "arac-avcisi-secret")

DEFAULT_CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "4"))
SCHEDULER_TICK_MINUTES = int(os.getenv("SCHEDULER_TICK_MINUTES", "15"))

# Hazır araç kataloğu. Listeyi static/app.js de API üzerinden okur.
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

# Model bazlı hazır paket/motor listesi. Kullanıcı paket yazmaz, listeden seçer.
DEFAULT_PACKAGES = ["Farketmez"]
CAR_PACKAGES = {
    "Volkswagen": {
        "Tiguan": ["Farketmez", "1.4 TSI Comfortline", "1.4 TSI Highline", "1.4 TSI ACT DSG", "1.5 TSI Life", "1.5 TSI Elegance", "1.5 TSI R-Line", "2.0 TDI Comfortline", "2.0 TDI Highline", "2.0 TDI R-Line"],
        "Golf": ["Farketmez", "1.0 TSI Life", "1.0 eTSI Life", "1.4 TSI Comfortline", "1.4 TSI Highline", "1.5 TSI Life", "1.5 eTSI Style", "1.5 eTSI R-Line"],
        "Passat": ["Farketmez", "1.4 TSI Comfortline", "1.4 TSI Highline", "1.5 TSI Business", "1.5 TSI Elegance", "1.6 TDI Comfortline", "1.6 TDI Highline"],
        "Polo": ["Farketmez", "1.0 MPI Trendline", "1.0 TSI Comfortline", "1.0 TSI Life", "1.0 TSI Style"],
        "T-Roc": ["Farketmez", "1.5 TSI Life", "1.5 TSI Style", "1.5 TSI R-Line"],
    },
    "Honda": {
        "Civic": ["Farketmez", "1.6 i-VTEC Elegance", "1.6 i-VTEC Executive", "1.6 Eco Elegance", "1.6 Eco Executive", "1.5 VTEC Turbo Elegance", "1.5 VTEC Turbo Executive+"],
        "City": ["Farketmez", "1.5 Executive", "1.5 Elegance"],
        "HR-V": ["Farketmez", "Elegance", "Advance", "Style"],
        "CR-V": ["Farketmez", "Elegance", "Executive", "Executive+"],
    },
    "Ford": {
        "Kuga": ["Farketmez", "1.5 EcoBoost Style", "1.5 EcoBoost Titanium", "1.5 EcoBoost ST-Line", "1.5 TDCi Titanium", "2.0 TDCi Titanium"],
        "Focus": ["Farketmez", "Trend X", "Titanium", "ST-Line", "1.5 TDCi Titanium", "1.5 EcoBoost Titanium"],
        "Puma": ["Farketmez", "Style", "Titanium", "ST-Line", "ST-Line X"],
    },
    "Jeep": {
        "Compass": ["Farketmez", "1.3 e-Hybrid Limited", "1.3 e-Hybrid Summit", "1.4 MultiAir Limited", "1.4 MultiAir Longitude", "1.6 Multijet Limited", "1.6 Multijet Longitude"],
        "Renegade": ["Farketmez", "Longitude", "Limited", "Trailhawk", "1.3 e-Hybrid Limited"],
        "Avenger": ["Farketmez", "Longitude", "Altitude", "Summit"],
    },
    "Hyundai": {
        "Tucson": ["Farketmez", "1.6 T-GDI Comfort", "1.6 T-GDI Elite", "1.6 T-GDI Elite Plus", "1.6 CRDi Elite", "1.6 CRDi Elite Plus"],
        "Bayon": ["Farketmez", "Jump", "Style", "Elite"],
        "i20": ["Farketmez", "Jump", "Style", "Elite", "N Line"],
        "Kona": ["Farketmez", "Style", "Elite", "N Line"],
    },
    "Peugeot": {
        "3008": ["Farketmez", "Active", "Allure", "Allure Selection", "GT", "GT Line", "1.5 BlueHDi Allure", "1.5 BlueHDi GT"],
        "2008": ["Farketmez", "Active", "Allure", "GT", "GT Line"],
        "308": ["Farketmez", "Active", "Allure", "GT", "GT Line"],
        "5008": ["Farketmez", "Allure", "GT", "GT Line"],
    },
    "Citroen": {
        "C5 Aircross": ["Farketmez", "Feel", "Feel Bold", "Shine", "Shine Bold"],
        "C4": ["Farketmez", "Feel", "Feel Bold", "Shine", "Shine Bold"],
        "C4 X": ["Farketmez", "Feel", "Feel Bold", "Shine", "Shine Bold"],
        "C3 Aircross": ["Farketmez", "Feel", "Shine"],
    },
    "Renault": {
        "Megane": ["Farketmez", "Joy", "Touch", "Icon", "1.3 TCe Joy", "1.3 TCe Touch", "1.5 dCi Touch", "1.5 dCi Icon"],
        "Clio": ["Farketmez", "Joy", "Touch", "Icon", "Equilibre", "Techno", "1.0 TCe Joy", "1.0 TCe Touch"],
        "Captur": ["Farketmez", "Touch", "Icon", "Icon EDC", "Techno"],
        "Kadjar": ["Farketmez", "Touch", "Icon", "1.5 dCi Icon"],
    },
    "Toyota": {
        "Corolla": ["Farketmez", "Vision", "Dream", "Flame", "Passion", "Hybrid Dream", "Hybrid Flame", "Hybrid Passion"],
        "C-HR": ["Farketmez", "Dream", "Flame", "Passion", "Hybrid Dream", "Hybrid Flame", "Hybrid Passion"],
        "Yaris": ["Farketmez", "Dream", "Flame", "Passion", "Hybrid Dream", "Hybrid Flame"],
        "RAV4": ["Farketmez", "Hybrid Flame", "Hybrid Passion", "Hybrid Passion X-Pack"],
    },
    "BMW": {
        "3 Serisi": ["Farketmez", "316i Comfort", "316i Luxury", "318i Edition M Sport", "320i ED Luxury", "320i ED M Sport", "320d xDrive M Sport"],
        "5 Serisi": ["Farketmez", "520i Luxury Line", "520i M Sport", "520d Luxury Line", "520d M Sport"],
        "X1": ["Farketmez", "sDrive18i X Line", "sDrive18i M Sport", "sDrive18d X Line"],
        "X3": ["Farketmez", "xDrive20i X Line", "xDrive20i M Sport", "xDrive20d M Sport"],
    },
    "Mercedes-Benz": {
        "C Serisi": ["Farketmez", "C180 AMG", "C180 Avantgarde", "C200 AMG", "C200d AMG", "C220d AMG"],
        "A Serisi": ["Farketmez", "A180 Style", "A180 Progressive", "A180 AMG", "A200 AMG"],
        "GLA": ["Farketmez", "GLA 180 Style", "GLA 200 AMG", "GLA 200 Progressive"],
        "GLC": ["Farketmez", "GLC 250 4Matic AMG", "GLC 300 AMG", "GLC 220d AMG"],
    },
    "Skoda": {
        "Octavia": ["Farketmez", "Optimal", "Ambition", "Style", "Premium", "1.0 TSI e-Tec", "1.5 TSI Style"],
        "Superb": ["Farketmez", "Prestige", "Premium", "L&K", "1.5 TSI Prestige", "1.5 TSI Premium"],
        "Karoq": ["Farketmez", "Elite", "Prestige", "Sportline"],
        "Kodiaq": ["Farketmez", "Elite", "Prestige", "Sportline", "L&K"],
    },
    "Opel": {
        "Astra": ["Farketmez", "Edition", "Elegance", "GS Line", "Ultimate"],
        "Mokka": ["Farketmez", "Elegance", "GS Line", "Ultimate"],
        "Grandland": ["Farketmez", "Edition", "Elegance", "GS Line", "Ultimate"],
        "Corsa": ["Farketmez", "Edition", "Elegance", "GS Line", "Ultimate"],
    },
    "Kia": {
        "Sportage": ["Farketmez", "Cool", "Elegance", "Prestige", "GT-Line", "1.6 T-GDI Elegance", "1.6 CRDi Prestige"],
        "Stonic": ["Farketmez", "Cool", "Elegance", "Prestige"],
        "Ceed": ["Farketmez", "Cool", "Elegance", "Prestige", "GT-Line"],
    },
    "Nissan": {
        "Qashqai": ["Farketmez", "Visia", "Tekna", "Skypack", "Platinum", "1.3 DIG-T Tekna", "1.5 dCi Tekna"],
        "Juke": ["Farketmez", "Tekna", "Platinum", "N-Design"],
        "X-Trail": ["Farketmez", "Designpack", "Skypack", "Platinum"],
    },
}

CITIES = [
    "Tüm Türkiye", "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya", "Artvin", "Aydın",
    "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum",
    "Denizli", "Diyarbakır", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun", "Gümüşhane",
    "Hakkari", "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir", "Kars", "Kastamonu", "Kayseri", "Kırklareli",
    "Kırşehir", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Tekirdağ",
    "Tokat", "Trabzon", "Tunceli", "Şanlıurfa", "Uşak", "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt",
    "Karaman", "Kırıkkale", "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük", "Kilis",
    "Osmaniye", "Düzce"
]

# Kaynaklar hazır gelir. Kullanıcı link yazmaz, sadece seçer.
# mode alanı uygulamanın o kaynak için nasıl davranacağını belirler:
# - direct: normal public sayfa isteği
# - guarded: engel ihtimali yüksek, düşük istek + bekleme + yedek arama
SOURCE_DEFS = [
    {
        "key": "sahibinden", "name": "Sahibinden", "base": "https://www.sahibinden.com",
        "template": "https://www.sahibinden.com/otomobil?query_text={q}",
        "open_template": "https://www.sahibinden.com/otomobil?query_text={q}",
        "mode": "guarded", "backup": True,
        "note": "Özel mod: 429/403 gelirse bekleme + Bing yedek arama + Sahibinden’de aç butonu."
    },
    {
        "key": "arabam", "name": "Arabam", "base": "https://www.arabam.com",
        "template": "https://www.arabam.com/ikinci-el/otomobil?searchText={q}",
        "open_template": "https://www.arabam.com/ikinci-el/otomobil?searchText={q}",
        "mode": "direct", "backup": False,
    },
    {
        "key": "letgo", "name": "Letgo", "base": "https://www.letgo.com",
        "template": "https://www.letgo.com/tr-tr/otomobil?q={q}",
        "open_template": "https://www.letgo.com/tr-tr/otomobil?q={q}",
        "mode": "direct", "backup": False,
    },
    {
        "key": "facebook", "name": "Facebook Marketplace", "base": "https://www.facebook.com",
        "template": "https://www.facebook.com/marketplace/search/?query={q}",
        "open_template": "https://www.facebook.com/marketplace/search/?query={q}",
        "mode": "guarded", "backup": False,
        "note": "Facebook çoğunlukla giriş ister. Uygulama şifre saklamaz; tek tuşla Marketplace’te açar."
    },
    {
        "key": "vavacars", "name": "VavaCars", "base": "https://www.vavacars.com",
        "template": "https://www.vavacars.com/tr/ikinci-el-araba?search={q}",
        "open_template": "https://www.vavacars.com/tr/ikinci-el-araba?search={q}",
        "mode": "direct", "backup": False,
    },
    {
        "key": "otoplus", "name": "Otoplus", "base": "https://www.otoplus.com",
        "template": "https://www.otoplus.com/ikinci-el-araba?search={q}",
        "open_template": "https://www.otoplus.com/ikinci-el-araba?search={q}",
        "mode": "guarded", "backup": False,
    },
    {
        "key": "otokoc", "name": "Otokoç 2. El", "base": "https://www.otokocikinciel.com",
        "template": "https://www.otokocikinciel.com/ikinci-el-arac?search={q}",
        "open_template": "https://www.otokocikinciel.com/ikinci-el-arac?search={q}",
        "mode": "guarded", "backup": False,
    },
    {
        "key": "arabasepeti", "name": "Araba Sepeti", "base": "https://www.arabasepeti.com",
        "template": "https://www.arabasepeti.com/ikinci-el-araclar?search={q}",
        "open_template": "https://www.arabasepeti.com/ikinci-el-araclar?search={q}",
        "mode": "direct", "backup": False,
    },
    {
        "key": "arabalar", "name": "Arabalar.com", "base": "https://www.arabalar.com.tr",
        "template": "https://www.arabalar.com.tr/ikinci-el?kelime={q}",
        "open_template": "https://www.arabalar.com.tr/ikinci-el?kelime={q}",
        "mode": "guarded", "backup": False,
    },
]

BACKOFF_HOURS_BY_STATUS = {
    400: 12,
    401: 24,
    403: 48,
    404: 12,
    408: 4,
    429: 24,
    500: 6,
    502: 6,
    503: 6,
    504: 6,
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            model TEXT NOT NULL,
            package_name TEXT,
            city TEXT,
            year_min INTEGER,
            year_max INTEGER,
            price_min INTEGER,
            price_max INTEGER,
            km_max INTEGER,
            fuel TEXT,
            gear TEXT,
            sources_json TEXT NOT NULL,
            email_to TEXT,
            telegram_chat_id TEXT,
            check_interval_hours INTEGER DEFAULT 4,
            baseline_done INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            last_checked_at TEXT,
            last_status TEXT
        );

        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            source_key TEXT NOT NULL,
            source_name TEXT NOT NULL,
            item_key TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            city TEXT,
            year INTEGER,
            km INTEGER,
            first_price INTEGER,
            current_price INTEGER,
            lowest_price INTEGER,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            last_notified_price INTEGER,
            UNIQUE(search_id, source_key, item_key)
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            item_id INTEGER,
            event_type TEXT NOT NULL,
            title TEXT NOT NULL,
            old_price INTEGER,
            new_price INTEGER,
            source_name TEXT,
            url TEXT,
            created_at TEXT NOT NULL,
            notification_status TEXT
        );

        CREATE TABLE IF NOT EXISTS source_cooldowns (
            search_id INTEGER NOT NULL,
            source_key TEXT NOT NULL,
            next_try_at TEXT,
            last_status TEXT,
            fail_count INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL,
            PRIMARY KEY(search_id, source_key)
        );

        CREATE INDEX IF NOT EXISTS idx_search_active ON searches(active);
        CREATE INDEX IF NOT EXISTS idx_items_search ON items(search_id, source_key);
        """
    )
    # Eski veritabanında yeni kolon yoksa otomatik ekle.
    cols = [row[1] for row in cur.execute("PRAGMA table_info(searches)").fetchall()]
    if "check_interval_hours" not in cols:
        cur.execute("ALTER TABLE searches ADD COLUMN check_interval_hours INTEGER DEFAULT 4")
    if "package_name" not in cols:
        cur.execute("ALTER TABLE searches ADD COLUMN package_name TEXT")
    conn.commit()
    conn.close()


def safe_interval_hours(value, default=None):
    if default is None:
        default = DEFAULT_CHECK_INTERVAL_HOURS
    try:
        interval = int(value)
    except (TypeError, ValueError):
        interval = int(default)
    return max(1, min(interval, 168))


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def human_datetime(value):
    dt = parse_iso_datetime(value)
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(timezone(timedelta(hours=3)))
    return local.strftime("%d.%m.%Y %H:%M")


def source_is_in_cooldown(conn, search_id, source_key):
    row = conn.execute(
        "SELECT * FROM source_cooldowns WHERE search_id=? AND source_key=?",
        (search_id, source_key),
    ).fetchone()
    if not row or not row["next_try_at"]:
        return None
    next_try = parse_iso_datetime(row["next_try_at"])
    if not next_try:
        return None
    if next_try.tzinfo is None:
        next_try = next_try.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) < next_try:
        d = dict(row)
        d["human_next_try"] = human_datetime(row["next_try_at"])
        return d
    return None


def set_source_cooldown(conn, search_id, source_key, status_code=None, status_text=""):
    hours = BACKOFF_HOURS_BY_STATUS.get(int(status_code or 0), 6)
    row = conn.execute(
        "SELECT fail_count FROM source_cooldowns WHERE search_id=? AND source_key=?",
        (search_id, source_key),
    ).fetchone()
    fail_count = int(row["fail_count"] if row else 0) + 1
    # Arka arkaya hata geldikçe beklemeyi büyüt, ama 7 günü geçmesin.
    hours = min(hours * max(1, min(fail_count, 4)), 168)
    next_try_at = (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat(timespec="seconds")
    conn.execute(
        """INSERT INTO source_cooldowns(search_id,source_key,next_try_at,last_status,fail_count,updated_at)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(search_id, source_key) DO UPDATE SET
           next_try_at=excluded.next_try_at,
           last_status=excluded.last_status,
           fail_count=excluded.fail_count,
           updated_at=excluded.updated_at""",
        (search_id, source_key, next_try_at, status_text, fail_count, now_iso()),
    )
    return next_try_at


def clear_source_cooldown(conn, search_id, source_key):
    conn.execute("DELETE FROM source_cooldowns WHERE search_id=? AND source_key=?", (search_id, source_key))


def search_is_due(search):
    interval = safe_interval_hours(search.get("check_interval_hours"), DEFAULT_CHECK_INTERVAL_HOURS)
    last_checked = parse_iso_datetime(search.get("last_checked_at"))
    if last_checked is None:
        return True
    if last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= last_checked + timedelta(hours=interval)


def tr_slug(text):
    repl = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")
    text = text.translate(repl)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text


def normalize_text(text):
    if text is None:
        return ""
    t = text.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU"))
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", t).lower().strip()


def parse_int_num(raw):
    if not raw:
        return None
    digits = re.sub(r"[^0-9]", "", raw)
    if not digits:
        return None
    try:
        return int(digits)
    except ValueError:
        return None


def extract_price(text):
    # 1.235.000 TL, 1 235 000 TL, ₺1.235.000
    patterns = [
        r"(?:₺|TL|tl)\s*([0-9][0-9\.\s]{4,})",
        r"([0-9][0-9\.\s]{4,})\s*(?:TL|tl|₺)",
    ]
    candidates = []
    for p in patterns:
        for m in re.findall(p, text):
            n = parse_int_num(m)
            if n and 50_000 <= n <= 50_000_000:
                candidates.append(n)
    return min(candidates) if candidates else None


def extract_year(text):
    years = [int(y) for y in re.findall(r"\b(19[8-9][0-9]|20[0-3][0-9])\b", text)]
    if not years:
        return None
    return max(years)


def extract_km(text):
    m = re.search(r"([0-9][0-9\.\s]{2,})\s*(?:km|KM|Km)", text)
    return parse_int_num(m.group(1)) if m else None


def build_query_text(search):
    q_parts = [search["brand"], search["model"]]
    package_name = search.get("package_name") or "Farketmez"
    if package_name != "Farketmez":
        q_parts.append(package_name)
    if search.get("fuel") and search.get("fuel") != "Farketmez":
        q_parts.append(search.get("fuel"))
    if search.get("gear") and search.get("gear") != "Farketmez":
        q_parts.append(search.get("gear"))
    if search.get("city") and search.get("city") != "Tüm Türkiye":
        q_parts.append(search.get("city"))
    if search.get("year_min"):
        q_parts.append(str(search.get("year_min")))
    return " ".join([str(x) for x in q_parts if x])


def build_search_url(source_def, search, open_url=False):
    q = build_query_text(search)
    q_enc = quote_plus(q)
    template = source_def.get("open_template") if open_url else source_def.get("template")
    template = template or source_def["template"]
    return template.format(q=q_enc, brand=tr_slug(search["brand"]), model=tr_slug(search["model"]))


def build_backup_search_url(source_def, search):
    q = f"site:{urlparse(source_def['base']).netloc} {build_query_text(search)} ikinci el"
    return "https://www.bing.com/search?q=" + quote_plus(q)


def item_key_for(url, title):
    base = url.split("?")[0].rstrip("/")
    material = base if len(base) > 12 else f"{url}|{title}"
    return hashlib.sha1(material.encode("utf-8", errors="ignore")).hexdigest()


def package_matches(item, search):
    package_name = (search.get("package_name") or "Farketmez").strip()
    if not package_name or package_name == "Farketmez":
        return True
    text = normalize_text((item.get("title", "") or "") + " " + (item.get("url", "") or ""))
    pkg = normalize_text(package_name).replace("-", " ")
    tokens = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", pkg)
    if not tokens:
        return True

    trim_keywords = [
        "comfortline", "highline", "life", "elegance", "executive", "executive+", "r", "line", "rline",
        "style", "business", "trendline", "allure", "active", "gt", "shine", "feel", "bold",
        "touch", "icon", "joy", "dream", "flame", "passion", "premium", "prestige", "ambition",
        "sportline", "limited", "longitude", "summit", "titanium", "st", "elite", "plus", "ultimate",
        "edition", "amg", "avantgarde", "progressive", "luxury", "x", "pack", "skypack", "platinum"
    ]
    important = [t for t in tokens if t in trim_keywords or any(k == t or k in t for k in trim_keywords)]
    engine = [t for t in tokens if re.match(r"^\d+(?:\.\d+)?$", t) or t in {"tsi", "tdi", "tcdi", "tdci", "dci", "hdi", "crdi", "eco", "hybrid", "vtec", "multiair", "multijet", "dig", "bluehdi", "ecoboost", "tgdi"}]

    # Paket adı başlıkta/linkte varsa tam isabet kabul et.
    if important and any(t in text for t in important):
        return True
    # Paket özel isim içermiyorsa motor bilgisinden eşleştir.
    if not important and engine and all(t in text for t in engine[:2]):
        return True
    return False


def passes_filters(item, search):
    text_n = normalize_text(item.get("title", ""))
    brand_ok = normalize_text(search["brand"]).replace("-", " ") in text_n or tr_slug(search["brand"]).replace("-", " ") in text_n
    model_words = [w for w in normalize_text(search["model"]).replace("-", " ").split() if w]
    model_ok = all(w in text_n for w in model_words[:2]) if model_words else True
    # Bazı siteler başlıkta marka/modeli kısaltabilir. Linkte varsa da kabul et.
    url_n = normalize_text(item.get("url", ""))
    if not brand_ok:
        brand_ok = tr_slug(search["brand"]) in url_n
    if not model_ok and model_words:
        model_ok = all(w in url_n for w in model_words[:2])
    if not (brand_ok and model_ok):
        return False
    if not package_matches(item, search):
        return False

    price = item.get("price")
    if price is not None:
        if search["price_min"] and price < search["price_min"]:
            return False
        if search["price_max"] and price > search["price_max"]:
            return False

    year = item.get("year")
    if year is not None:
        if search["year_min"] and year < search["year_min"]:
            return False
        if search["year_max"] and year > search["year_max"]:
            return False

    km = item.get("km")
    if km is not None and search["km_max"] and km > search["km_max"]:
        return False
    return True


def parse_search_page(source_def, html, search, limit=50):
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)
    results = []
    seen = set()
    for a in anchors:
        href = a.get("href", "").strip()
        if href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue
        full_url = urljoin(source_def["base"], href)
        clean_url = full_url.split("#")[0]
        if clean_url in seen:
            continue
        seen.add(clean_url)
        card_text = " ".join(a.stripped_strings)
        parent = a
        for _ in range(4):
            if parent and parent.parent:
                parent = parent.parent
        parent_text = parent.get_text(" ", strip=True) if parent else card_text
        combined = f"{card_text} {parent_text}"
        price = extract_price(combined)
        year = extract_year(combined)
        km = extract_km(combined)
        title = re.sub(r"\s+", " ", card_text or parent_text).strip()
        if not title or len(title) < 5:
            continue
        item = {
            "source_key": source_def["key"],
            "source_name": source_def["name"],
            "title": title[:220],
            "url": clean_url,
            "price": price,
            "year": year,
            "km": km,
            "city": None,
        }
        if passes_filters(item, search):
            results.append(item)
        if len(results) >= limit:
            break
    return results


def fetch_bing_backup(source_def, search, limit=20):
    """Sahibinden gibi engel veren kaynaklar için arama motoru yedek modu.
    Bu mod tam liste garantisi vermez; sadece indekslenmiş ilanları yakalar.
    """
    url = build_backup_search_url(source_def, search)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    results = []
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code >= 400:
            return [], {"source": f"{source_def['name']} yedek arama", "url": url, "status": f"HTTP {resp.status_code}", "status_code": resp.status_code}
        soup = BeautifulSoup(resp.text, "html.parser")
        host = urlparse(source_def["base"]).netloc.replace("www.", "")
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            # Bing bazen gerçek adresi u parametresine koyar.
            if href.startswith("/ck/a"):
                qs = parse_qs(urlparse(href).query)
                if qs.get("u"):
                    href = unquote(qs["u"][0])
                    if href.startswith("a1"):
                        href = href[2:]
            if not href.startswith("http"):
                continue
            if host not in urlparse(href).netloc.replace("www.", ""):
                continue
            clean = href.split("#")[0]
            if clean in seen:
                continue
            seen.add(clean)
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()[:220]
            if not title:
                title = f"{source_def['name']} ilanı"
            item = {
                "source_key": source_def["key"],
                "source_name": source_def["name"] + " / yedek",
                "title": title,
                "url": clean,
                "price": extract_price(title),
                "year": extract_year(title),
                "km": extract_km(title),
                "city": None,
            }
            if passes_filters(item, search):
                results.append(item)
            if len(results) >= limit:
                break
        return results, {"source": f"{source_def['name']} yedek arama", "url": url, "status": "ok", "status_code": 200}
    except Exception as exc:
        return [], {"source": f"{source_def['name']} yedek arama", "url": url, "status": f"Hata: {exc.__class__.__name__}: {exc}", "status_code": None}


def fetch_source(source_def, search, limit=50):
    url = build_search_url(source_def, search)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36 AraçAvcisi/2.0",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    }
    status = "ok"
    status_code = None
    try:
        # Guarded kaynaklarda biraz daha nazik davran. Site engeli görünürse backoff devreye girer.
        if source_def.get("mode") == "guarded":
            time.sleep(1.5)
        resp = requests.get(url, headers=headers, timeout=25, allow_redirects=True)
        status_code = resp.status_code
        status = f"HTTP {resp.status_code}"
        if resp.status_code >= 400:
            log = {"source": source_def["name"], "url": url, "status": status, "status_code": resp.status_code}
            # Sahibinden gibi kaynaklarda engel geldiğinde yedek arama denenir.
            if source_def.get("backup") and resp.status_code in (400, 403, 429):
                backup_items, backup_log = fetch_bing_backup(source_def, search, limit=limit)
                backup_log["primary_status"] = status
                backup_log["primary_status_code"] = resp.status_code
                backup_log["status"] = f"{status} / yedek: {backup_log.get('status', '')}"
                # status_code asıl kaynağın durumudur; böylece kaynak bazlı bekleme devreye girer.
                backup_log["status_code"] = resp.status_code
                return backup_items, backup_log
            return [], log
        results = parse_search_page(source_def, resp.text, search, limit=limit)
        return results, {"source": source_def["name"], "url": url, "status": status, "status_code": resp.status_code}
    except Exception as exc:
        status = f"Hata: {exc.__class__.__name__}: {exc}"
    return [], {"source": source_def["name"], "url": url, "status": status, "status_code": status_code}


def format_price(value):
    if value is None:
        return "Fiyat yok"
    return f"{value:,}".replace(",", ".") + " TL"


def send_telegram(text, chat_id=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat = (chat_id or os.getenv("TELEGRAM_CHAT_ID", "")).strip()
    if not token or not chat:
        return "telegram ayarı yok"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": text, "disable_web_page_preview": False},
            timeout=15,
        )
        if r.status_code == 200:
            return "telegram gönderildi"
        return f"telegram hata: HTTP {r.status_code} {r.text[:120]}"
    except Exception as exc:
        return f"telegram hata: {exc}"


def send_mail(subject, body, to_addr=None):
    to_addr = (to_addr or "").strip()
    host = os.getenv("SMTP_HOST", "").strip()
    user = os.getenv("SMTP_USER", "").strip()
    password = os.getenv("SMTP_PASS", "").strip()
    from_addr = (os.getenv("MAIL_FROM", "").strip() or user)
    port = int(os.getenv("SMTP_PORT", "587") or "587")
    if not to_addr or not host or not user or not password:
        return "mail ayarı yok"
    try:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr
        with smtplib.SMTP(host, port, timeout=20) as s:
            s.starttls()
            s.login(user, password)
            s.send_message(msg)
        return "mail gönderildi"
    except Exception as exc:
        return f"mail hata: {exc}"


def create_event(conn, search_id, item_id, event_type, item, old_price=None, new_price=None, notify=True, search=None):
    title = item.get("title", "Araç")
    url = item.get("url", "")
    source_name = item.get("source_name", "")
    subject = "Araç Avcısı: Yeni ilan" if event_type == "new" else "Araç Avcısı: Fiyat düştü"
    if event_type == "new":
        body = f"Yeni ilan bulundu\n\n{title}\nKaynak: {source_name}\nFiyat: {format_price(new_price)}\nLink: {url}"
    else:
        body = f"Fiyat düştü\n\n{title}\nKaynak: {source_name}\nEski fiyat: {format_price(old_price)}\nYeni fiyat: {format_price(new_price)}\nLink: {url}"
    status_parts = []
    if notify and search:
        status_parts.append(send_telegram(body, search.get("telegram_chat_id")))
        status_parts.append(send_mail(subject, body, search.get("email_to")))
    status = " | ".join(status_parts) if status_parts else "bildirim kapalı"
    conn.execute(
        """INSERT INTO events(search_id,item_id,event_type,title,old_price,new_price,source_name,url,created_at,notification_status)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (search_id, item_id, event_type, title, old_price, new_price, source_name, url, now_iso(), status),
    )
    return status


def load_search(conn, search_id):
    row = conn.execute("SELECT * FROM searches WHERE id=?", (search_id,)).fetchone()
    return dict(row) if row else None


def check_search(search_id, baseline=False):
    conn = db()
    search = load_search(conn, search_id)
    if not search or not search["active"]:
        conn.close()
        return {"ok": False, "message": "Arama pasif veya bulunamadı"}
    source_keys = json.loads(search["sources_json"])
    source_map = {s["key"]: s for s in SOURCE_DEFS}
    total_new = 0
    total_drop = 0
    total_seen = 0
    logs = []
    for key in source_keys:
        source_def = source_map.get(key)
        if not source_def:
            continue
        cooldown = None if baseline else source_is_in_cooldown(conn, search_id, key)
        if cooldown:
            logs.append({
                "source": source_def["name"],
                "url": build_search_url(source_def, search, open_url=True),
                "status": f"Beklemede: {cooldown.get('last_status') or 'kaynak sınırı'} / tekrar: {cooldown.get('human_next_try')}",
                "status_code": None,
                "cooldown": True,
            })
            continue
        items, log = fetch_source(source_def, search)
        logs.append(log)
        status_code = log.get("status_code")
        if status_code and int(status_code) >= 400:
            next_try = set_source_cooldown(conn, search_id, key, status_code, log.get("status", ""))
            log["cooldown_until"] = human_datetime(next_try)
        elif items or (status_code and int(status_code) < 400):
            clear_source_cooldown(conn, search_id, key)
        for item in items:
            total_seen += 1
            item_key = item_key_for(item["url"], item["title"])
            existing = conn.execute(
                "SELECT * FROM items WHERE search_id=? AND source_key=? AND item_key=?",
                (search_id, item["source_key"], item_key),
            ).fetchone()
            price = item.get("price")
            if existing is None:
                cur = conn.execute(
                    """INSERT INTO items(search_id,source_key,source_name,item_key,title,url,city,year,km,first_price,current_price,lowest_price,first_seen_at,last_seen_at,last_notified_price)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        search_id, item["source_key"], item["source_name"], item_key, item["title"], item["url"], item.get("city"),
                        item.get("year"), item.get("km"), price, price, price, now_iso(), now_iso(), price,
                    ),
                )
                item_id = cur.lastrowid
                if not baseline and search["baseline_done"]:
                    total_new += 1
                    create_event(conn, search_id, item_id, "new", item, new_price=price, notify=True, search=search)
            else:
                old_price = existing["current_price"]
                lowest = existing["lowest_price"]
                new_lowest = min([p for p in [lowest, price] if p is not None], default=price)
                conn.execute(
                    """UPDATE items SET title=?, url=?, city=?, year=?, km=?, current_price=?, lowest_price=?, last_seen_at=? WHERE id=?""",
                    (item["title"], item["url"], item.get("city"), item.get("year"), item.get("km"), price, new_lowest, now_iso(), existing["id"]),
                )
                if price is not None and old_price is not None and price < old_price and not baseline and search["baseline_done"]:
                    total_drop += 1
                    create_event(conn, search_id, existing["id"], "price_drop", item, old_price=old_price, new_price=price, notify=True, search=search)
    status = f"Kontrol tamamlandı. Görülen: {total_seen}, yeni: {total_new}, fiyat düşen: {total_drop}"
    conn.execute(
        "UPDATE searches SET baseline_done=1, last_checked_at=?, last_status=? WHERE id=?",
        (now_iso(), status + " | " + " ; ".join([f"{l['source']}: {l['status']}" for l in logs]), search_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True, "status": status, "logs": logs}


def scheduled_job():
    conn = db()
    rows = conn.execute("SELECT * FROM searches WHERE active=1").fetchall()
    searches = [dict(row) for row in rows]
    conn.close()
    for search in searches:
        if not search_is_due(search):
            continue
        try:
            check_search(search["id"], baseline=False)
            time.sleep(2)
        except Exception as exc:
            print(f"Zamanlanmış arama hatası: {search['id']} {exc}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/options")
def options():
    return jsonify({
        "catalog": CAR_CATALOG,
        "package_map": CAR_PACKAGES,
        "default_packages": DEFAULT_PACKAGES,
        "cities": CITIES,
        "sources": SOURCE_DEFS,
        "default_interval_hours": DEFAULT_CHECK_INTERVAL_HOURS,
        "interval_choices": [1, 2, 3, 4, 6, 8, 12, 24, 48, 72],
    })


@app.route("/api/searches", methods=["GET"])
def list_searches():
    conn = db()
    rows = conn.execute("SELECT * FROM searches ORDER BY id DESC").fetchall()
    data = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d.pop("sources_json"))
        source_map = {s["key"]: s for s in SOURCE_DEFS}
        d["source_links"] = [
            {
                "key": key,
                "name": source_map.get(key, {"name": key}).get("name"),
                "url": build_search_url(source_map[key], d, open_url=True) if key in source_map else "",
                "backup_url": build_backup_search_url(source_map[key], d) if key in source_map and source_map[key].get("backup") else "",
                "note": source_map.get(key, {}).get("note", ""),
            }
            for key in d["sources"] if key in source_map
        ]
        count_rows = conn.execute(
            "SELECT source_name, COUNT(*) AS count FROM items WHERE search_id=? GROUP BY source_name ORDER BY source_name",
            (d["id"],),
        ).fetchall()
        d["item_count"] = sum(int(cr["count"]) for cr in count_rows)
        d["source_item_counts"] = [dict(cr) for cr in count_rows]
        data.append(d)
    conn.close()
    return jsonify(data)


def normalize_sources_json(sources):
    return json.dumps(sorted([str(x) for x in (sources or [])]), ensure_ascii=False)


def find_duplicate_search(conn, payload, sources):
    brand = (payload.get("brand") or "").strip()
    model = (payload.get("model") or "").strip()
    city = payload.get("city") or "Tüm Türkiye"
    package_name = payload.get("package_name") or "Farketmez"
    rows = conn.execute(
        "SELECT * FROM searches WHERE active=1 AND brand=? AND model=? AND city=?",
        (brand, model, city),
    ).fetchall()
    wanted_sources = sorted([str(x) for x in sources])
    comparable_keys = ["package_name", "year_min", "year_max", "price_min", "price_max", "km_max", "fuel", "gear"]
    for row in rows:
        d = dict(row)
        try:
            row_sources = sorted(json.loads(d.get("sources_json") or "[]"))
        except Exception:
            row_sources = []
        if row_sources != wanted_sources:
            continue
        same = True
        for key in comparable_keys:
            incoming = payload.get(key)
            if incoming == "":
                incoming = None
            if key in ("fuel", "gear", "package_name"):
                incoming = incoming or "Farketmez"
                existing = d.get(key) or "Farketmez"
            else:
                incoming = int(incoming) if incoming is not None else None
                existing = d.get(key)
            if incoming != existing:
                same = False
                break
        if same:
            return d
    return None


@app.route("/api/searches", methods=["POST"])
def create_search():
    payload = request.get_json(force=True)
    brand = payload.get("brand", "").strip()
    model = payload.get("model", "").strip()
    sources = payload.get("sources") or []
    if not brand or not model or not sources:
        return jsonify({"ok": False, "message": "Marka, model ve en az bir site seçmelisin."}), 400
    name = payload.get("name") or f"{brand} {model}"
    conn = db()
    duplicate = find_duplicate_search(conn, payload, sources)
    if duplicate:
        conn.close()
        return jsonify({
            "ok": True,
            "duplicate": True,
            "id": duplicate["id"],
            "message": "Bu takip zaten var. Yeni kopya oluşturmadım; mevcut takibi açabilirsin."
        })
    cur = conn.execute(
        """INSERT INTO searches(name,brand,model,package_name,city,year_min,year_max,price_min,price_max,km_max,fuel,gear,sources_json,email_to,telegram_chat_id,check_interval_hours,created_at,last_status)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            name, brand, model, payload.get("package_name") or "Farketmez", payload.get("city") or "Tüm Türkiye",
            payload.get("year_min") or None, payload.get("year_max") or None,
            payload.get("price_min") or None, payload.get("price_max") or None,
            payload.get("km_max") or None, payload.get("fuel") or "Farketmez", payload.get("gear") or "Farketmez",
            json.dumps(sources, ensure_ascii=False), payload.get("email_to") or "", payload.get("telegram_chat_id") or "",
            safe_interval_hours(payload.get("check_interval_hours")),
            now_iso(), "İlk kayıt oluşturuldu. Başlangıç araması yapılıyor.",
        ),
    )
    search_id = cur.lastrowid
    conn.commit()
    conn.close()
    result = check_search(search_id, baseline=True)
    return jsonify({"ok": True, "id": search_id, "baseline": result})


@app.route("/api/searches/<int:search_id>/run", methods=["POST"])
def run_search(search_id):
    return jsonify(check_search(search_id, baseline=False))


@app.route("/api/searches/<int:search_id>/items")
def list_items(search_id):
    conn = db()
    rows = conn.execute("SELECT * FROM items WHERE search_id=? ORDER BY last_seen_at DESC LIMIT 300", (search_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/searches/<int:search_id>/source-links")
def source_links(search_id):
    conn = db()
    search = load_search(conn, search_id)
    conn.close()
    if not search:
        return jsonify({"ok": False, "message": "Takip bulunamadı"}), 404
    source_keys = json.loads(search["sources_json"])
    source_map = {s["key"]: s for s in SOURCE_DEFS}
    links = []
    for key in source_keys:
        sdef = source_map.get(key)
        if not sdef:
            continue
        links.append({
            "key": key,
            "name": sdef["name"],
            "url": build_search_url(sdef, search, open_url=True),
            "backup_url": build_backup_search_url(sdef, search) if sdef.get("backup") else "",
            "note": sdef.get("note", ""),
        })
    return jsonify({"ok": True, "links": links})


@app.route("/api/events")
def list_events():
    conn = db()
    rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT 100").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/searches/<int:search_id>/toggle", methods=["POST"])
def toggle_search(search_id):
    conn = db()
    row = conn.execute("SELECT active FROM searches WHERE id=?", (search_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False}), 404
    new_state = 0 if row["active"] else 1
    conn.execute("UPDATE searches SET active=? WHERE id=?", (new_state, search_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "active": new_state})


@app.route("/api/searches/<int:search_id>/delete", methods=["POST"])
def delete_search(search_id):
    conn = db()
    row = conn.execute("SELECT id FROM searches WHERE id=?", (search_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "Takip bulunamadı"}), 404
    conn.execute("DELETE FROM events WHERE search_id=?", (search_id,))
    conn.execute("DELETE FROM items WHERE search_id=?", (search_id,))
    conn.execute("DELETE FROM source_cooldowns WHERE search_id=?", (search_id,))
    conn.execute("DELETE FROM searches WHERE id=?", (search_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/searches/<int:search_id>/interval", methods=["POST"])
def update_interval(search_id):
    payload = request.get_json(force=True)
    interval = safe_interval_hours(payload.get("check_interval_hours"))
    conn = db()
    row = conn.execute("SELECT id FROM searches WHERE id=?", (search_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"ok": False, "message": "Takip bulunamadı"}), 404
    conn.execute(
        "UPDATE searches SET check_interval_hours=?, last_status=? WHERE id=?",
        (interval, f"Kontrol sıklığı {interval} saat olarak güncellendi.", search_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "check_interval_hours": interval})




# -----------------------------------------------------------------------------
# v7: Site linkleri ve liste yakalama düzeltmeleri
# -----------------------------------------------------------------------------
# Önceki sürümlerde bazı kaynaklarda arama parametresi sitenin güncel URL yapısına
# uymadığı için "sonuç bulunamadı" sayfası açılıyordu. Bu blok, ana uygulamayı
# değiştirmeden fonksiyonları daha geniş ve dayanıklı link mantığıyla geçersiz kılar.

SOURCE_DEFS = [
    {
        "key": "sahibinden", "name": "Sahibinden", "base": "https://www.sahibinden.com",
        "template": "", "open_template": "", "mode": "guarded", "backup": True,
        "note": "Geniş marka/model linki + Bing yedek arama. 429/403 gelirse beklemeye alınır."
    },
    {
        "key": "arabam", "name": "Arabam", "base": "https://www.arabam.com",
        "template": "", "open_template": "", "mode": "direct", "backup": True,
    },
    {
        "key": "letgo", "name": "Letgo", "base": "https://www.letgo.com",
        "template": "", "open_template": "", "mode": "direct", "backup": True,
    },
    {
        "key": "facebook", "name": "Facebook Marketplace", "base": "https://www.facebook.com",
        "template": "", "open_template": "", "mode": "guarded", "backup": True,
        "note": "Facebook çoğu zaman giriş ister. Direkt link açılır, ayrıca yedek arama verilir."
    },
    {
        "key": "vavacars", "name": "VavaCars", "base": "https://tr.vava.cars",
        "template": "", "open_template": "", "mode": "direct", "backup": True,
    },
    {
        "key": "otoplus", "name": "Otoplus", "base": "https://www.otoplus.com",
        "template": "", "open_template": "", "mode": "guarded", "backup": True,
    },
    {
        "key": "otokoc", "name": "Otokoç 2. El", "base": "https://www.otokocikinciel.com",
        "template": "", "open_template": "", "mode": "guarded", "backup": True,
    },
    {
        "key": "arabasepeti", "name": "Araba Sepeti", "base": "https://www.arabasepeti.com",
        "template": "", "open_template": "", "mode": "direct", "backup": True,
    },
    {
        "key": "arabalar", "name": "Arabalar.com", "base": "https://www.arabalar.com.tr",
        "template": "", "open_template": "", "mode": "guarded", "backup": True,
    },
]

PACKAGE_SLUG_OVERRIDES = {
    ("Honda", "Civic", "1.6 Eco Elegance"): "1.6i-vtec-eco-elegance",
    ("Honda", "Civic", "1.6 Eco Executive"): "1.6i-vtec-eco-executive",
    ("Honda", "Civic", "1.6 i-VTEC Elegance"): "1.6i-vtec-elegance",
    ("Honda", "Civic", "1.6 i-VTEC Executive"): "1.6i-vtec-executive",
    ("Honda", "Civic", "1.5 VTEC Turbo Elegance"): "1.5-vtec-turbo-elegance",
    ("Honda", "Civic", "1.5 VTEC Turbo Executive+"): "1.5-vtec-turbo-executive",
}


def _city_slug(search):
    city = (search.get("city") or "Tüm Türkiye").strip()
    if not city or city == "Tüm Türkiye":
        return ""
    return tr_slug(city)


def _brand_model_slug(search):
    return f"{tr_slug(search.get('brand', ''))}-{tr_slug(search.get('model', ''))}".strip("-")


def _package_slug(search):
    package_name = (search.get("package_name") or "Farketmez").strip()
    if not package_name or package_name == "Farketmez":
        return ""
    key = ((search.get("brand") or "").strip(), (search.get("model") or "").strip(), package_name)
    return PACKAGE_SLUG_OVERRIDES.get(key) or tr_slug(package_name)


def _exact_query_text(search):
    # Site dışı yedek aramalarda olabildiğince net sorgu kullanılır.
    parts = [search.get("brand"), search.get("model")]
    package_name = (search.get("package_name") or "Farketmez").strip()
    if package_name and package_name != "Farketmez":
        parts.append(package_name)
    if search.get("city") and search.get("city") != "Tüm Türkiye":
        parts.append(search.get("city"))
    if search.get("year_min"):
        parts.append(str(search.get("year_min")))
    if search.get("price_max"):
        parts.append(f"{search.get('price_max')} TL altı")
    return " ".join(str(x) for x in parts if x)


def build_search_url(source_def, search, open_url=False):
    """v7 link üretici.
    Direkt butonlarda geniş marka/model sayfaları kullanılır; böylece siteye gidince
    boş filtre sayfasına düşme ihtimali azalır. Kesin paket ve şehir araması yedek
    arama bağlantısından yapılır.
    """
    key = source_def.get("key")
    q = quote_plus(_exact_query_text(search))
    bm = _brand_model_slug(search)
    city = _city_slug(search)
    pkg = _package_slug(search)

    if key == "sahibinden":
        # Sahibinden en stabil olarak marka-model ve şehir path yapısında açılıyor.
        url = f"https://www.sahibinden.com/{bm}"
        if city:
            url += f"/{city}"
        return url

    if key == "arabam":
        # Arabam tarafında kategori URL'leri path tabanlıdır. Paket exact ise çok daraltabilir,
        # bu yüzden kullanıcı butonu geniş marka/model açar; takip motoru ve yedek arama paketi arar.
        url = f"https://www.arabam.com/ikinci-el/otomobil/{bm}"
        if city:
            url += f"-{city}"
        return url

    if key == "otoplus":
        return f"https://www.otoplus.com/{tr_slug(search.get('brand',''))}/{tr_slug(search.get('model',''))}"

    if key == "otokoc":
        return "https://www.otokocikinciel.com/ikinci-el-araba"

    if key == "vavacars":
        return f"https://tr.vava.cars/?q={q}"

    if key == "letgo":
        return f"https://www.letgo.com/tr-tr/ara?q={q}"

    if key == "facebook":
        return f"https://www.facebook.com/marketplace/search/?query={q}"

    if key == "arabasepeti":
        return f"https://www.arabasepeti.com/ikinci-el-araclar?search={q}"

    if key == "arabalar":
        return f"https://www.arabalar.com.tr/ikinci-el?kelime={q}"

    return source_def.get("base", "")


def build_backup_search_url(source_def, search):
    host = urlparse(source_def.get("base", "")).netloc.replace("www.", "")
    q = f"site:{host} {_exact_query_text(search)} ikinci el fiyat km"
    return "https://www.bing.com/search?q=" + quote_plus(q)


def _price_from_block(text):
    return extract_price(text or "")


def _result_from_text_block(source_def, title, url, text):
    title = re.sub(r"\s+", " ", title or "").strip()
    text = re.sub(r"\s+", " ", text or title).strip()
    if not title:
        title = text[:160]
    return {
        "source_key": source_def["key"],
        "source_name": source_def["name"],
        "title": title[:220] or f"{source_def['name']} ilanı",
        "url": url.split("#")[0],
        "price": _price_from_block(text),
        "year": extract_year(text),
        "km": extract_km(text),
        "city": None,
    }


def parse_search_page(source_def, html, search, limit=50):
    soup = BeautifulSoup(html or "", "html.parser")
    results = []
    seen = set()
    base_host = urlparse(source_def.get("base", "")).netloc.replace("www.", "")

    # Önce güçlü adaylar: list/card/article kapsayıcıları.
    candidates = []
    selectors = ["article", "li", "div[class*='card']", "div[class*='listing']", "div[class*='vehicle']", "tr"]
    for sel in selectors:
        candidates.extend(soup.select(sel))
    if not candidates:
        candidates = soup.find_all("a", href=True)

    for block in candidates:
        a = block.find("a", href=True) if hasattr(block, "find") else None
        if a is None and getattr(block, "name", "") == "a" and block.get("href"):
            a = block
        if not a:
            continue
        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:")):
            continue
        full_url = urljoin(source_def["base"], href).split("#")[0]
        host = urlparse(full_url).netloc.replace("www.", "")
        if base_host and base_host not in host:
            continue
        if full_url in seen:
            continue
        seen.add(full_url)
        title = a.get_text(" ", strip=True)
        block_text = block.get_text(" ", strip=True) if hasattr(block, "get_text") else title
        # Çok genel menü linklerini ele.
        low = normalize_text(title + " " + full_url)
        if any(bad in low for bad in ["giris yap", "uye ol", "favori", "karsilastir", "yardim", "blog"]):
            continue
        item = _result_from_text_block(source_def, title, full_url, block_text)
        if len(item["title"]) < 4:
            continue
        if passes_filters(item, search):
            results.append(item)
        if len(results) >= limit:
            break
    return results


def fetch_bing_backup(source_def, search, limit=30):
    url = build_backup_search_url(source_def, search)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    results = []
    try:
        resp = requests.get(url, headers=headers, timeout=25)
        if resp.status_code >= 400:
            return [], {"source": f"{source_def['name']} yedek arama", "url": url, "status": f"HTTP {resp.status_code}", "status_code": resp.status_code}
        soup = BeautifulSoup(resp.text, "html.parser")
        host = urlparse(source_def["base"]).netloc.replace("www.", "")
        seen = set()
        blocks = soup.select("li.b_algo") or soup.find_all("li") or soup.find_all("a", href=True)
        for block in blocks:
            a = block.find("a", href=True) if hasattr(block, "find") else None
            if a is None and getattr(block, "name", "") == "a" and block.get("href"):
                a = block
            if not a:
                continue
            href = a.get("href", "")
            # Bing bazen gerçek adresi u parametresine koyar.
            if href.startswith("/ck/a"):
                qs = parse_qs(urlparse(href).query)
                if qs.get("u"):
                    href = unquote(qs["u"][0])
                    if href.startswith("a1"):
                        href = href[2:]
            if href.startswith("//"):
                href = "https:" + href
            if not href.startswith("http"):
                continue
            if host and host not in urlparse(href).netloc.replace("www.", ""):
                continue
            clean = href.split("#")[0]
            if clean in seen:
                continue
            seen.add(clean)
            title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
            block_text = block.get_text(" ", strip=True) if hasattr(block, "get_text") else title
            item = _result_from_text_block({**source_def, "name": source_def["name"] + " / yedek"}, title, clean, block_text)
            if passes_filters(item, search):
                results.append(item)
            if len(results) >= limit:
                break
        return results, {"source": f"{source_def['name']} yedek arama", "url": url, "status": "ok", "status_code": 200}
    except Exception as exc:
        return [], {"source": f"{source_def['name']} yedek arama", "url": url, "status": f"Hata: {exc.__class__.__name__}: {exc}", "status_code": None}


def fetch_source(source_def, search, limit=50):
    url = build_search_url(source_def, search)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    }
    status_code = None
    try:
        if source_def.get("mode") == "guarded":
            time.sleep(1.2)
        resp = requests.get(url, headers=headers, timeout=25, allow_redirects=True)
        status_code = resp.status_code
        direct_status = f"HTTP {resp.status_code}"
        if resp.status_code < 400:
            results = parse_search_page(source_def, resp.text, search, limit=limit)
            if results:
                return results, {"source": source_def["name"], "url": url, "status": f"{direct_status} / liste: {len(results)}", "status_code": resp.status_code}
            # Sayfa açıldı ama JS/boş/çok dar filtre yüzünden yakalayamadıysa yedek ara.
            if source_def.get("backup"):
                backup_items, backup_log = fetch_bing_backup(source_def, search, limit=limit)
                backup_log["primary_status"] = direct_status
                backup_log["primary_status_code"] = resp.status_code
                backup_log["status"] = f"{direct_status} / direkt liste yok / yedek: {backup_log.get('status','')}"
                # 200 dönse bile yedek başarılıysa kaynağı soğutma moduna sokma.
                backup_log["status_code"] = 200 if backup_items else resp.status_code
                return backup_items, backup_log
            return [], {"source": source_def["name"], "url": url, "status": f"{direct_status} / liste yok", "status_code": resp.status_code}

        # Engel veya hata durumunda yedek arama.
        if source_def.get("backup") and resp.status_code in (400, 403, 404, 429, 500, 502, 503, 504):
            backup_items, backup_log = fetch_bing_backup(source_def, search, limit=limit)
            backup_log["primary_status"] = direct_status
            backup_log["primary_status_code"] = resp.status_code
            backup_log["status"] = f"{direct_status} / yedek: {backup_log.get('status','')}"
            backup_log["status_code"] = resp.status_code
            return backup_items, backup_log
        return [], {"source": source_def["name"], "url": url, "status": direct_status, "status_code": resp.status_code}
    except Exception as exc:
        # Bağlantı sıfırlanırsa da yedek arama dene.
        if source_def.get("backup"):
            backup_items, backup_log = fetch_bing_backup(source_def, search, limit=limit)
            backup_log["primary_status"] = f"Hata: {exc.__class__.__name__}"
            backup_log["status"] = f"Hata: {exc.__class__.__name__} / yedek: {backup_log.get('status','')}"
            backup_log["status_code"] = 200 if backup_items else status_code
            return backup_items, backup_log
        return [], {"source": source_def["name"], "url": url, "status": f"Hata: {exc.__class__.__name__}: {exc}", "status_code": status_code}


@app.route("/health")
def health():
    return jsonify({
        "ok": True,
        "version": "v7-link-liste-duzeltme",
        "time": now_iso(),
        "default_interval_hours": DEFAULT_CHECK_INTERVAL_HOURS,
        "scheduler_tick_minutes": SCHEDULER_TICK_MINUTES,
    })


_scheduler = None


def start_scheduler():
    scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Istanbul")
    scheduler.add_job(
        scheduled_job,
        "interval",
        minutes=SCHEDULER_TICK_MINUTES,
        id="arac-avcisi",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler


def boot_app():
    global _scheduler
    init_db()
    if os.getenv("ENABLE_SCHEDULER", "1") == "1" and _scheduler is None:
        _scheduler = start_scheduler()




# -----------------------------------------------------------------------------
# v8: Doğru site linkleri + daha sağlam liste yakalama
# -----------------------------------------------------------------------------
# Bu blok boot_app() çağrısından önce çalışır. Böylece Render ayağa kalkarken
# yeni link üretici ve yeni parser aktif olur.

V8_VERSION = "v9-secim-kutulari-duzeltildi"

SUV_MODELS = {
    "Tiguan", "T-Roc", "Taigo", "Kuga", "Puma", "Compass", "Renegade", "Avenger",
    "Tucson", "Bayon", "HR-V", "CR-V", "Sportage", "Qashqai", "Duster", "3008", "2008",
    "C-HR", "RAV4", "T-Cross", "Kodiaq", "Kamiq", "Ateca"
}

SAHIBINDEN_FULL_SLUGS = {
    ("Honda", "Civic", "Farketmez"): "honda-civic",
    ("Honda", "Civic", "1.6 Eco Elegance"): "honda-civic-1.6i-vtec-eco-elegance",
    ("Honda", "Civic", "1.6 Eco Executive"): "honda-civic-1.6i-vtec-eco-executive",
    ("Honda", "Civic", "1.6 i-VTEC Elegance"): "honda-civic-1.6i-vtec-elegance",
    ("Honda", "Civic", "1.6 i-VTEC Executive"): "honda-civic-1.6i-vtec-executive",
    ("Honda", "Civic", "1.5 VTEC Turbo Elegance"): "honda-civic-1.5-vtec-turbo-elegance",
    ("Honda", "Civic", "1.5 VTEC Turbo Executive+"): "honda-civic-1.5-vtec-turbo-executive-plus",
    ("Volkswagen", "Tiguan", "Farketmez"): "arazi-suv-pickup-volkswagen-tiguan",
    ("Volkswagen", "Tiguan", "1.4 TSI Comfortline"): "arazi-suv-pickup-volkswagen-tiguan-1.4-tsi-comfortline",
    ("Volkswagen", "Tiguan", "1.4 TSI Highline"): "arazi-suv-pickup-volkswagen-tiguan-1.4-tsi-highline",
    ("Volkswagen", "Tiguan", "1.4 TSI ACT DSG"): "arazi-suv-pickup-volkswagen-tiguan-1.4-tsi",
    ("Volkswagen", "Tiguan", "1.5 TSI Life"): "arazi-suv-pickup-volkswagen-tiguan-1.5-tsi",
    ("Volkswagen", "Tiguan", "1.5 TSI Elegance"): "arazi-suv-pickup-volkswagen-tiguan-1.5-tsi-elegance",
    ("Volkswagen", "Tiguan", "1.5 TSI R-Line"): "arazi-suv-pickup-volkswagen-tiguan-1.5-tsi-r-line",
    ("Volkswagen", "Tiguan", "2.0 TDI Comfortline"): "arazi-suv-pickup-volkswagen-tiguan-2.0-tdi-comfortline",
    ("Volkswagen", "Tiguan", "2.0 TDI Highline"): "arazi-suv-pickup-volkswagen-tiguan-2.0-tdi-highline",
    ("Volkswagen", "Tiguan", "2.0 TDI R-Line"): "arazi-suv-pickup-volkswagen-tiguan-2.0-tdi-r-line",
}

ARABAM_FULL_SLUGS = {
    ("Honda", "Civic", "Farketmez"): "honda-civic",
    ("Honda", "Civic", "1.6 Eco Elegance"): "honda-civic-1-6-i-vtec-eco-elegance",
    ("Honda", "Civic", "1.6 Eco Executive"): "honda-civic-1-6-i-vtec-eco-executive",
    ("Honda", "Civic", "1.6 i-VTEC Elegance"): "honda-civic-1-6-i-vtec-elegance",
    ("Honda", "Civic", "1.6 i-VTEC Executive"): "honda-civic-1-6-i-vtec-executive",
    ("Honda", "Civic", "1.5 VTEC Turbo Elegance"): "honda-civic-1-5-vtec-turbo-elegance",
    ("Honda", "Civic", "1.5 VTEC Turbo Executive+"): "honda-civic-1-5-vtec-turbo-executive-plus",
    ("Volkswagen", "Tiguan", "Farketmez"): "volkswagen-tiguan",
    ("Volkswagen", "Tiguan", "1.4 TSI Comfortline"): "volkswagen-tiguan-1-4-tsi-comfortline",
    ("Volkswagen", "Tiguan", "1.4 TSI Highline"): "volkswagen-tiguan-1-4-tsi-highline",
    ("Volkswagen", "Tiguan", "1.4 TSI ACT DSG"): "volkswagen-tiguan-1-4-tsi",
    ("Volkswagen", "Tiguan", "1.5 TSI Life"): "volkswagen-tiguan-1-5-tsi-life",
    ("Volkswagen", "Tiguan", "1.5 TSI Elegance"): "volkswagen-tiguan-1-5-tsi-elegance",
    ("Volkswagen", "Tiguan", "1.5 TSI R-Line"): "volkswagen-tiguan-1-5-tsi-r-line",
    ("Volkswagen", "Tiguan", "2.0 TDI Comfortline"): "volkswagen-tiguan-2-0-tdi-comfortline",
    ("Volkswagen", "Tiguan", "2.0 TDI Highline"): "volkswagen-tiguan-2-0-tdi-highline",
    ("Volkswagen", "Tiguan", "2.0 TDI R-Line"): "volkswagen-tiguan-2-0-tdi-r-line",
}

OTOPLUS_PACKAGE_SLUGS = {
    ("Volkswagen", "Tiguan", "1.4 TSI Comfortline"): "tiguan-1.4-tsi-bmt-125-comfortline",
    ("Volkswagen", "Tiguan", "1.4 TSI Highline"): "tiguan-1.4-tsi-act-bmt-150-dsg-highline",
    ("Honda", "Civic", "Farketmez"): "",
}

SOURCE_DEFS = [
    {"key": "sahibinden", "name": "Sahibinden", "base": "https://www.sahibinden.com", "mode": "guarded", "backup": True},
    {"key": "arabam", "name": "Arabam", "base": "https://www.arabam.com", "mode": "direct", "backup": True},
    {"key": "letgo", "name": "Letgo", "base": "https://www.letgo.com", "mode": "direct", "backup": True},
    {"key": "facebook", "name": "Facebook Marketplace", "base": "https://www.facebook.com", "mode": "guarded", "backup": True},
    {"key": "vavacars", "name": "VavaCars", "base": "https://tr.vava.cars", "mode": "direct", "backup": True},
    {"key": "otoplus", "name": "Otoplus", "base": "https://www.otoplus.com", "mode": "direct", "backup": True},
    {"key": "otokoc", "name": "Otokoç 2. El", "base": "https://www.otokocikinciel.com", "mode": "guarded", "backup": True},
    {"key": "arabasepeti", "name": "Araba Sepeti", "base": "https://www.arabasepeti.com", "mode": "direct", "backup": True},
    {"key": "arabalar", "name": "Arabalar.com", "base": "https://www.arabalar.com.tr", "mode": "guarded", "backup": True},
]

def _pkg_name(search):
    return (search.get("package_name") or "Farketmez").strip() or "Farketmez"

def _is_suv(search):
    return (search.get("model") or "").strip() in SUV_MODELS

def _arabam_category(search):
    return "arazi-suv-pick-up" if _is_suv(search) else "otomobil"

def _sahibinden_full_slug(search):
    brand = (search.get("brand") or "").strip()
    model = (search.get("model") or "").strip()
    pkg = _pkg_name(search)
    slug = SAHIBINDEN_FULL_SLUGS.get((brand, model, pkg))
    if not slug and pkg != "Farketmez":
        slug = SAHIBINDEN_FULL_SLUGS.get((brand, model, "Farketmez"))
        # Sahibinden bazı motorlarda paket yerine motor kırılımı kullanıyor. Emin değilsek geniş sayfa açar.
        if not slug:
            base = f"{tr_slug(brand)}-{tr_slug(model)}".strip("-")
            slug = ("arazi-suv-pickup-" if _is_suv(search) else "") + base
    if not slug:
        base = f"{tr_slug(brand)}-{tr_slug(model)}".strip("-")
        slug = ("arazi-suv-pickup-" if _is_suv(search) else "") + base
    return slug

def _arabam_full_slug(search):
    brand = (search.get("brand") or "").strip()
    model = (search.get("model") or "").strip()
    pkg = _pkg_name(search)
    slug = ARABAM_FULL_SLUGS.get((brand, model, pkg))
    if not slug:
        pieces = [brand, model]
        if pkg != "Farketmez":
            pieces.append(pkg)
        slug = tr_slug(" ".join(pieces))
    return slug

def _otoplus_path(search):
    brand = tr_slug(search.get("brand", ""))
    model = tr_slug(search.get("model", ""))
    exact = OTOPLUS_PACKAGE_SLUGS.get(((search.get("brand") or "").strip(), (search.get("model") or "").strip(), _pkg_name(search)))
    if exact:
        return f"/{brand}/{model}/{exact}"
    return f"/{brand}/{model}"

def _url_city_suffix(search):
    city = _city_slug(search)
    return city if city else ""

def build_search_url(source_def, search, open_url=False):
    key = source_def.get("key")
    q = quote_plus(_exact_query_text(search))
    city = _url_city_suffix(search)

    if key == "sahibinden":
        path = _sahibinden_full_slug(search)
        if city:
            path += f"/{city}"
        return f"https://www.sahibinden.com/{path}"

    if key == "arabam":
        slug = _arabam_full_slug(search)
        if city:
            slug += f"-{city}"
        return f"https://www.arabam.com/ikinci-el/{_arabam_category(search)}/{slug}"

    if key == "otoplus":
        return "https://www.otoplus.com" + _otoplus_path(search)

    if key == "facebook":
        return f"https://www.facebook.com/marketplace/search/?query={q}"

    if key == "letgo":
        # letgo web araması çoğu oturumda JS/lokasyon ister. En azından ana sayfa yerine net site içi arama verir.
        return f"https://www.google.com/search?q={quote_plus('site:letgo.com/item ' + _exact_query_text(search))}"

    if key == "vavacars":
        # VavaCars web arayüzü JS ile çalıştığı için ana sayfa yerine site içi arama açılır.
        return f"https://www.google.com/search?q={quote_plus('site:tr.vava.cars ' + _exact_query_text(search))}"

    if key == "otokoc":
        return f"https://www.google.com/search?q={quote_plus('site:otokocikinciel.com ' + _exact_query_text(search))}"

    if key == "arabasepeti":
        return f"https://www.google.com/search?q={quote_plus('site:arabasepeti.com ' + _exact_query_text(search))}"

    if key == "arabalar":
        return f"https://www.google.com/search?q={quote_plus('site:arabalar.com.tr ' + _exact_query_text(search))}"

    return source_def.get("base", "")

def build_backup_search_url(source_def, search):
    # Direkt link çalışmazsa ana sayfaya düşürmek yerine Google site içi arama açılır.
    host = urlparse(source_def.get("base", "")).netloc.replace("www.", "")
    return "https://www.google.com/search?q=" + quote_plus(f"site:{host} {_exact_query_text(search)} ikinci el fiyat km")

def item_key_for(url, title):
    material = f"{url}|{title}"
    return hashlib.sha1(material.encode("utf-8", errors="ignore")).hexdigest()

def _important_pkg_tokens(search):
    pkg = normalize_text(_pkg_name(search)).replace("-", " ")
    tokens = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", pkg)
    return [t for t in tokens if t not in {"farketmez", "i", "v", "tec", "tsi", "tdi", "bmt", "act", "dsg"}]

def package_matches(item, search):
    pkg = _pkg_name(search)
    if pkg == "Farketmez":
        return True
    text = normalize_text((item.get("title") or "") + " " + (item.get("url") or "") + " " + (item.get("raw_text") or ""))
    tokens = _important_pkg_tokens(search)
    if not tokens:
        return True
    # En az bir güçlü paket kelimesi ve mümkünse motor işareti yeterli kabul edilir.
    strong = [t for t in tokens if len(t) >= 4 or t in {"eco", "tsi", "tdi"}]
    if strong and any(t in text for t in strong):
        return True
    # Tüm kısa motor parçaları görünüyorsa kabul.
    return len(tokens) >= 2 and sum(1 for t in tokens if t in text) >= min(2, len(tokens))

def passes_filters(item, search):
    hay = normalize_text((item.get("title") or "") + " " + (item.get("raw_text") or "") + " " + (item.get("url") or ""))
    brand = normalize_text(search.get("brand", ""))
    model_words = [w for w in normalize_text(search.get("model", "")).replace("-", " ").split() if w]
    if brand and brand not in hay and tr_slug(search.get("brand", "")) not in hay:
        return False
    if model_words and not all(w in hay for w in model_words[:2]):
        return False
    if not package_matches(item, search):
        return False
    price = item.get("price")
    if price is not None:
        if search.get("price_min") and price < search["price_min"]: return False
        if search.get("price_max") and price > search["price_max"]: return False
    year = item.get("year")
    if year is not None:
        if search.get("year_min") and year < search["year_min"]: return False
        if search.get("year_max") and year > search["year_max"]: return False
    km = item.get("km")
    if km is not None and search.get("km_max") and km > search["km_max"]: return False
    return True

def _extract_city_from_text(text):
    nt = normalize_text(text)
    for c in CITIES:
        if normalize_text(c) in nt:
            return c
    return None

def _good_href_for_source(source_def, href):
    h = href or ""
    key = source_def.get("key")
    low = h.lower()
    if key == "sahibinden": return "/ilan/" in low
    if key == "arabam": return "/ilan/" in low or ("/ikinci-el/" in low and "?" not in low and len(low) > 35)
    if key == "otoplus": return "sahibinden-" in low or re.search(r"\d+km.*\d+tl", low) is not None
    if key == "letgo": return "/item/" in low
    return any(x in low for x in ["/ilan/", "/item/", "sahibinden-", "ikinci-el"])

def _best_url(block, source_def, search_url):
    best = ""
    for a in block.find_all("a", href=True) if hasattr(block, "find_all") else []:
        href = a.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        full = urljoin(source_def["base"], href).split("#")[0]
        host = urlparse(full).netloc.replace("www.", "")
        base_host = urlparse(source_def["base"]).netloc.replace("www.", "")
        if base_host and base_host not in host:
            continue
        if _good_href_for_source(source_def, href):
            return full
        if not best and full.rstrip("/") != source_def["base"].rstrip("/"):
            best = full
    return best or search_url

def _title_from_lines(lines, search):
    brand = normalize_text(search.get("brand", ""))
    model = normalize_text(search.get("model", ""))
    bad = {"goster", "karşılaştır", "gizle", "favorilerimde", "fiyat", "kilometre", "renk", "tarih", "il", "ilçe", "araba al", "araç sat"}
    for line in lines:
        nl = normalize_text(line)
        if len(line) >= 18 and brand in nl and model in nl and not any(b in nl for b in bad):
            return line
    for line in lines:
        nl = normalize_text(line)
        if len(line) >= 18 and not any(b in nl for b in bad) and (model in nl or any(t in nl for t in _important_pkg_tokens(search))):
            return line
    return lines[0] if lines else "Araç ilanı"

def _item_from_block_v8(source_def, block, search, search_url):
    text = block.get_text("\n", strip=True) if hasattr(block, "get_text") else str(block)
    text = re.sub(r"[ \t]+", " ", text)
    if not text or len(text) < 20:
        return None
    if len(text) > 2500:
        return None
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if re.sub(r"\s+", " ", x).strip()]
    title = _title_from_lines(lines, search)
    url = _best_url(block, source_def, search_url)
    item = {
        "source_key": source_def["key"],
        "source_name": source_def["name"],
        "title": title[:220],
        "url": url,
        "price": extract_price(text),
        "year": extract_year(text),
        "km": extract_km(text),
        "city": _extract_city_from_text(text),
        "raw_text": text[:2000],
    }
    return item if passes_filters(item, search) else None

def _text_fallback_items(source_def, soup, search, search_url, limit):
    text = soup.get_text("\n", strip=True)
    lines = [re.sub(r"\s+", " ", x).strip() for x in text.splitlines() if re.sub(r"\s+", " ", x).strip()]
    results, seen = [], set()
    brand = normalize_text(search.get("brand", ""))
    model = normalize_text(search.get("model", ""))
    for i, line in enumerate(lines):
        window = "\n".join(lines[i:i+12])
        nw = normalize_text(window)
        if brand not in nw or model not in nw:
            continue
        if not extract_price(window):
            continue
        title = _title_from_lines(lines[i:i+6], search)
        # gerçek ilan linki yakalanamayan JS/karmaşık sayfalarda liste sayfasına benzersiz çapa koyulur
        synthetic_url = search_url + "#" + hashlib.sha1(window.encode("utf-8", errors="ignore")).hexdigest()[:12]
        item = {
            "source_key": source_def["key"], "source_name": source_def["name"],
            "title": title[:220], "url": synthetic_url,
            "price": extract_price(window), "year": extract_year(window), "km": extract_km(window),
            "city": _extract_city_from_text(window), "raw_text": window[:2000]
        }
        k = item_key_for(item["url"], item["title"])
        if k in seen: continue
        if passes_filters(item, search):
            seen.add(k); results.append(item)
        if len(results) >= limit: break
    return results

def parse_search_page(source_def, html, search, limit=50):
    soup = BeautifulSoup(html or "", "html.parser")
    search_url = build_search_url(source_def, search)
    selectors = [
        "tr.searchResultsItem", "tr[class*='searchResultsItem']", "tr[class*='listing']",
        "li[class*='listing']", "li[class*='search']", "article", "div[class*='listing']",
        "div[class*='card']", "div[class*='vehicle']", "div[class*='product']",
        "a[href*='/ilan/']", "a[href*='sahibinden-']", "a[href*='/item/']"
    ]
    candidates = []
    for sel in selectors:
        try:
            candidates.extend(soup.select(sel))
        except Exception:
            pass
    # Son çare olarak tablo satırları ve listeleri al.
    if not candidates:
        candidates = soup.find_all(["tr", "li", "article", "a"], href=True) + soup.find_all(["tr", "li", "article"])
    results, seen = [], set()
    for block in candidates:
        item = _item_from_block_v8(source_def, block, search, search_url)
        if not item:
            continue
        k = item_key_for(item["url"], item["title"])
        if k in seen:
            continue
        seen.add(k)
        results.append(item)
        if len(results) >= limit:
            break
    if not results:
        results = _text_fallback_items(source_def, soup, search, search_url, limit)
    return results[:limit]

def fetch_source(source_def, search, limit=50):
    url = build_search_url(source_def, search)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Cache-Control": "no-cache",
    }
    status_code = None
    try:
        if source_def.get("mode") == "guarded":
            time.sleep(1.0)
        # Google yedek linkleri direkt scrape edilmez, sadece buton olarak verilir.
        if url.startswith("https://www.google.com/search"):
            return [], {"source": source_def["name"], "url": url, "status": "Harici arama linki hazır", "status_code": 200}
        resp = requests.get(url, headers=headers, timeout=25, allow_redirects=True)
        status_code = resp.status_code
        direct_status = f"HTTP {resp.status_code}"
        if resp.status_code < 400:
            results = parse_search_page(source_def, resp.text, search, limit=limit)
            return results, {"source": source_def["name"], "url": url, "status": f"{direct_status} / liste: {len(results)}", "status_code": resp.status_code}
        return [], {"source": source_def["name"], "url": url, "status": direct_status, "status_code": resp.status_code}
    except Exception as exc:
        return [], {"source": source_def["name"], "url": url, "status": f"Hata: {exc.__class__.__name__}: {exc}", "status_code": status_code}

def health_v8():
    return jsonify({
        "ok": True,
        "version": V8_VERSION,
        "time": now_iso(),
        "default_interval_hours": DEFAULT_CHECK_INTERVAL_HOURS,
        "scheduler_tick_minutes": SCHEDULER_TICK_MINUTES,
    })
app.view_functions["health"] = health_v8


# Cloud deploys import app:app with gunicorn. The scheduler and database must start on import.
boot_app()


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("APP_PORT", "5050"))
    app.run(host=host, port=port, debug=False)
