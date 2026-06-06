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

VERSION = "v25-filters-server-rendered-stable"
DATA_DIR = os.getenv("DATA_DIR", "data")
DB_PATH = os.path.join(DATA_DIR, "arac_avcisi.db")
DEFAULT_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "4") or 4)
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "1") == "1"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "18") or 18)
MAX_ITEMS_PER_SOURCE = int(os.getenv("MAX_ITEMS_PER_SOURCE", "12") or 12)

os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "arac-avcisi-v25")

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
        active INTEGER DEFAULT 1, created_at TEXT, updated_at TEXT,
        last_check_at TEXT, last_status TEXT DEFAULT '', item_count INTEGER DEFAULT 0
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS listings(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER, source TEXT, title TEXT, price INTEGER,
        year INTEGER, km INTEGER, city TEXT, url TEXT, uid TEXT,
        first_seen TEXT, last_seen TEXT, UNIQUE(track_id, uid)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_id INTEGER, type TEXT, source TEXT, title TEXT, price_old INTEGER,
        price_new INTEGER, url TEXT, created_at TEXT, notify_status TEXT DEFAULT ''
    )""")
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
    qs = {}
    if t.get("price_min"): qs["price_min"] = t.get("price_min")
    if t.get("price_max"): qs["price_max"] = t.get("price_max")
    if t.get("year_min"): qs["year_min"] = t.get("year_min")
    if t.get("year_max"): qs["year_max"] = t.get("year_max")
    if t.get("km_max"): qs["km_max"] = t.get("km_max")
    add = ("?" + urlencode(qs)) if qs else ""
    if source == "arabam":
        path = f"{b}-{m}" + (f"-{tm}" if tm else "")
        return f"https://www.arabam.com/ikinci-el/arazi-suv-pick-up/{path}{add}"
    if source == "sahibinden":
        path = f"arazi-suv-pickup-{b}-{m}" + (f"-{tm}" if tm else "")
        return f"https://www.sahibinden.com/{path}?{urlencode({'price_min': t.get('price_min') or '', 'price_max': t.get('price_max') or '', 'a4_max': t.get('km_max') or '', 'a5_min': t.get('year_min') or '', 'a5_max': t.get('year_max') or ''})}"
    if source == "otoplus":
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
        return f"https://www.letgo.com/arama?q={quote_plus(q)}"
    if source == "facebook":
        return f"https://www.facebook.com/marketplace/search/?query={quote_plus(q)}"
    return "https://www.google.com/search?q=" + quote_plus(q)


def is_detail_url(source, url):
    if not url or not url.startswith("http"):
        return False
    bad = ["/search", "arama", "filtre", "kategori", "javascript:", "#"]
    u = url.lower()
    if any(x in u for x in bad):
        return False
    if source == "sahibinden":
        return "/ilan/" in u
    if source == "arabam":
        return "/ilan/" in u or bool(re.search(r"-[0-9]{6,}", u))
    if source == "otoplus":
        return bool(re.search(r"/[a-z0-9-]+-[0-9]{4}-", u)) or "sahibinden-" in u
    if source == "otokoc":
        return "/ikinci-el/" in u or bool(re.search(r"/[0-9]{5,}", u))
    return bool(re.search(r"[0-9]{5,}", u))


def clean_title(s):
    s = BeautifulSoup(s or "", "html.parser").get_text(" ")
    s = re.sub(r"\s+", " ", s).strip(" -•|\n\t")
    return s[:160]


def bad_title(title):
    t = (title or "").lower()
    bads = ["filtre", "çerez", "giriş", "üye", "sonuç bulunamadı", "araçları listeleniyor", "arama", "anasayfa", "kategori", "model seç", "marka seç"]
    return len(t) < 8 or any(b in t for b in bads)


def parse_price(text):
    matches = re.findall(r"((?:\d{1,3}[\.\s]){1,4}\d{3}|\d{6,9})\s*(?:tl|₺)", text.lower())
    if not matches:
        return None
    vals = [as_int(m) for m in matches]
    vals = [v for v in vals if v and 20000 <= v <= 20000000]
    return vals[0] if vals else None


def parse_year(text):
    years = [int(x) for x in re.findall(r"\b(19[8-9]\d|20[0-3]\d)\b", text)]
    return years[0] if years else None


def parse_km(text):
    m = re.search(r"((?:\d{1,3}[\.\s]){1,3}\d{3}|\d{4,7})\s*km", text.lower())
    if m:
        v = as_int(m.group(1))
        return v if v and v < 1000000 else None
    return None


def passes_filters(item, t):
    title_blob = f"{item.get('title','')} {item.get('url','')}".lower()
    if slug_tr(t.get("brand")) not in slug_tr(title_blob):
        return False
    model_slug = slug_tr(t.get("model"))
    if model_slug and model_slug not in slug_tr(title_blob):
        return False
    trim = t.get("trim") or ""
    if trim and trim != "Farketmez":
        # trim token toleransı: hepsi değil, kritik tokenlardan biri yeterli olsun
        tokens = [x for x in re.split(r"\s+", trim.lower()) if len(x) > 1 and x not in ["tsi", "tdi", "bmt"]]
        if tokens and not any(slug_tr(tok) in slug_tr(title_blob) for tok in tokens[:3]):
            pass
    price = item.get("price")
    if price:
        if t.get("price_min") and price < t["price_min"]: return False
        if t.get("price_max") and price > t["price_max"]: return False
    year = item.get("year")
    if year:
        if t.get("year_min") and year < t["year_min"]: return False
        if t.get("year_max") and year > t["year_max"]: return False
    km = item.get("km")
    if km and t.get("km_max") and km > t["km_max"]:
        return False
    city = t.get("city")
    if city and city != "Tüm Türkiye" and item.get("city"):
        if slug_tr(city) not in slug_tr(item.get("city")):
            return False
    return True


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
        item = {"source": source, "title": title, "url": url.split("?")[0], "price": parse_price(around), "year": parse_year(around), "km": parse_km(around), "city": extract_city(around)}
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
            item = {"source": source, "title": title, "url": url.split("?")[0], "price": parse_price(around), "year": parse_year(around), "km": parse_km(around), "city": extract_city(around)}
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
    url = list_url(source, t)
    try:
        code, html, final_url = fetch(url)
        status.append(f"HTTP {code}")
        if code == 200:
            html_items = parse_html_items(source, html, final_url, t)
            status.append(f"html {len(html_items)}")
            items.extend(html_items)
        elif code in (403, 410, 429):
            status.append("doğrudan engel")
    except Exception as e:
        status.append(f"site hata: {type(e).__name__}")
    # reader fallback
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
    # search fallback
    if len(items) < 2 and source not in ["facebook", "letgo"]:
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
    # dedupe
    out = []
    seen = set()
    for it in items:
        if not is_detail_url(source, it.get("url")):
            continue
        uid = make_uid(it)
        if uid in seen:
            continue
        it["uid"] = uid
        seen.add(uid)
        out.append(it)
        if len(out) >= MAX_ITEMS_PER_SOURCE:
            break
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
    return d


def check_track(track_id, notify=True):
    con = db()
    row = con.execute("SELECT * FROM tracks WHERE id=?", (track_id,)).fetchone()
    if not row:
        con.close(); return
    t = row_to_track(row)
    statuses = []
    total_seen = 0
    new_count = 0
    drop_count = 0
    for source in t["sources"]:
        found, st, _ = source_check(source, t)
        statuses.append(f"{source}: {st} / liste {len(found)}")
        total_seen += len(found)
        for item in found:
            item["uid"] = item.get("uid") or make_uid(item)
            old = con.execute("SELECT * FROM listings WHERE track_id=? AND uid=?", (track_id, item["uid"])).fetchone()
            if not old:
                con.execute("""INSERT OR IGNORE INTO listings(track_id, source, title, price, year, km, city, url, uid, first_seen, last_seen)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?)""", (track_id, source, item.get("title"), item.get("price"), item.get("year"), item.get("km"), item.get("city"), item.get("url"), item["uid"], now_iso(), now_iso()))
                con.execute("INSERT INTO events(track_id,type,source,title,price_new,url,created_at) VALUES(?,?,?,?,?,?,?)", (track_id,"new",source,item.get("title"),item.get("price"),item.get("url"),now_iso()))
                new_count += 1
                if notify:
                    send_notification(t, "Yeni ilan", item, None, item.get("price"))
            else:
                old_price = old["price"]
                new_price = item.get("price")
                if old_price and new_price and new_price < old_price:
                    con.execute("UPDATE listings SET price=?, year=?, km=?, city=?, title=?, url=?, last_seen=? WHERE id=?", (new_price,item.get("year"),item.get("km"),item.get("city"),item.get("title"),item.get("url"),now_iso(),old["id"]))
                    con.execute("INSERT INTO events(track_id,type,source,title,price_old,price_new,url,created_at) VALUES(?,?,?,?,?,?,?,?)", (track_id,"price_drop",source,item.get("title"),old_price,new_price,item.get("url"),now_iso()))
                    drop_count += 1
                    if notify:
                        send_notification(t, "Fiyat düştü", item, old_price, new_price)
                else:
                    con.execute("UPDATE listings SET last_seen=? WHERE id=?", (now_iso(), old["id"]))
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
        listings[t["id"]] = [dict(x) for x in con.execute("SELECT * FROM listings WHERE track_id=? ORDER BY first_seen DESC LIMIT 80", (t["id"],)).fetchall()]
    events = [dict(x) for x in con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 50").fetchall()]
    con.close()
    all_models = sorted(set(m for b in BRANDS.values() for m in b["models"]))
    all_packages = sorted(set(p for b in BRANDS.values() for p in b["packages"]))
    return render_template("index.html", version=VERSION, brands=BRANDS, cities=CITIES, sources=SOURCES, fuel_options=FUEL_OPTIONS, gear_options=GEAR_OPTIONS, intervals=INTERVALS, tracks=tracks, listings=listings, events=events, all_models=all_models, all_packages=all_packages)


@app.route("/create", methods=["POST"])
def create():
    init_db()
    f = request.form
    brand = f.get("brand_custom") or f.get("brand")
    model = f.get("model_custom") or f.get("model")
    trim = f.get("trim_custom") or f.get("trim") or "Farketmez"
    name = f.get("name") or f"{brand} {model} {trim if trim!='Farketmez' else ''}".strip()
    sources = f.getlist("sources") or ["arabam"]
    data = (
        name, brand, model, trim, f.get("city") or "Tüm Türkiye", as_int(f.get("year_min")), as_int(f.get("year_max")), as_int(f.get("km_max")), as_int(f.get("price_min")), as_int(f.get("price_max")), f.get("fuel") or "Farketmez", f.get("gear") or "Farketmez", json.dumps(sources, ensure_ascii=False), as_int(f.get("interval_hours"), DEFAULT_INTERVAL_HOURS), f.get("notify_email") or "", f.get("telegram_chat_id") or "", 1, now_iso(), now_iso()
    )
    con = db(); cur = con.cursor()
    cur.execute("""INSERT INTO tracks(name,brand,model,trim,city,year_min,year_max,km_max,price_min,price_max,fuel,gear,sources,interval_hours,notify_email,telegram_chat_id,active,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", data)
    tid = cur.lastrowid
    con.commit(); con.close()
    background_check(tid)
    return redirect(url_for("index"))


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
    check_track(track_id, notify=True)
    return redirect(url_for("index"))


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
    caches && caches.keys().then(keys=>keys.forEach(k=>caches.delete(k))).finally(()=>location.href='/?v=25&t='+Date.now());
    </script><h2>Önbellek temizleniyor...</h2><a href='/?v=25'>Aç</a>"""


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
