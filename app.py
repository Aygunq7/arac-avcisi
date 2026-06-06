import json
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, jsonify, redirect, render_template, request

VERSION = "v24-bildirim-testli-stabil"
APP = Flask(__name__)
APP.secret_key = os.environ.get("SECRET_KEY", "arac-avcisi-v23")

DATA_DIR = Path(os.environ.get("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "arac_avcisi_v23.db"
REQ_TIMEOUT = int(os.environ.get("REQ_TIMEOUT", "18"))
MAX_RESULTS_PER_SOURCE = int(os.environ.get("MAX_RESULTS_PER_SOURCE", "25"))

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.5,en;q=0.3",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

SOURCES = {
    "sahibinden": {"label": "Sahibinden", "domain": "sahibinden.com"},
    "arabam": {"label": "Arabam", "domain": "arabam.com"},
    "otoplus": {"label": "Otoplus", "domain": "otoplus.com"},
    "otokoc": {"label": "Otokoç 2. El", "domain": "otokocikinciel.com"},
    "vavacars": {"label": "VavaCars", "domain": "vava.cars"},
    "arabasepeti": {"label": "Araba Sepeti", "domain": "arabasepeti.com"},
    "arabalar": {"label": "Arabalar.com", "domain": "arabalar.com"},
    "letgo": {"label": "Letgo", "domain": "letgo.com"},
    "facebook": {"label": "Facebook Marketplace", "domain": "facebook.com"},
}

# Liste hazır gelsin ama eksik kalırsa kullanıcı özel marka/model/paket yazabilir.
VEHICLE_DATA = {
    "Volkswagen": {
        "Tiguan": ["Farketmez", "1.4 TSI Comfortline", "1.4 TSI Highline", "1.4 TSI Life", "1.5 TSI Life", "1.5 TSI Elegance", "1.5 TSI R-Line", "2.0 TDI Comfortline", "2.0 TDI Highline", "2.0 TDI R-Line"],
        "Passat": ["Farketmez", "1.4 TSI Comfortline", "1.4 TSI Highline", "1.5 TSI Business", "1.5 TSI Elegance", "1.6 TDI Comfortline", "1.6 TDI Highline", "2.0 TDI Highline"],
        "Golf": ["Farketmez", "1.0 TSI Midline", "1.2 TSI Comfortline", "1.4 TSI Highline", "1.5 eTSI Life", "1.5 eTSI Style", "1.5 eTSI R-Line"],
        "Polo": ["Farketmez", "1.0 MPI Trendline", "1.0 TSI Comfortline", "1.0 TSI Life", "1.0 TSI Style"],
        "T-Roc": ["Farketmez", "1.5 TSI Life", "1.5 TSI Style", "1.5 TSI R-Line"],
        "Jetta": ["Farketmez", "1.2 TSI Trendline", "1.4 TSI Comfortline", "1.6 TDI Comfortline", "1.6 TDI Highline"],
    },
    "Honda": {
        "Civic": ["Farketmez", "1.6 Eco Elegance", "1.6 Eco Executive", "1.5 VTEC Turbo Elegance", "1.5 VTEC Turbo Executive", "1.6 i-VTEC Elegance", "1.6 i-VTEC Executive"],
        "CR-V": ["Farketmez", "1.5 VTEC Turbo Elegance", "1.5 VTEC Turbo Executive", "2.0 i-VTEC Executive"],
        "HR-V": ["Farketmez", "1.5 i-VTEC Elegance", "1.5 e:HEV Advance", "1.5 e:HEV Style"],
        "City": ["Farketmez", "1.5 Executive", "1.5 Elegance"],
        "Jazz": ["Farketmez", "1.4 i-VTEC Joy", "1.4 i-VTEC Fun", "1.5 e:HEV Executive"],
    },
    "Toyota": {
        "Corolla": ["Farketmez", "1.33 Life", "1.6 Dream", "1.6 Flame", "1.6 Vision", "1.8 Hybrid Dream", "1.8 Hybrid Flame", "1.8 Hybrid Passion"],
        "C-HR": ["Farketmez", "1.2 Turbo Advance", "1.2 Turbo Diamond", "1.8 Hybrid Flame", "1.8 Hybrid Passion"],
        "Yaris": ["Farketmez", "1.0 Life", "1.5 Dream", "1.5 Hybrid Dream", "1.5 Hybrid Passion"],
        "RAV4": ["Farketmez", "2.0 Elegant", "2.5 Hybrid Passion", "2.5 Hybrid Premium"],
    },
    "Renault": {
        "Clio": ["Farketmez", "1.0 TCe Joy", "1.0 TCe Touch", "1.0 TCe Icon", "1.5 dCi Joy", "1.5 dCi Touch", "1.5 dCi Icon"],
        "Megane": ["Farketmez", "1.3 TCe Joy", "1.3 TCe Touch", "1.3 TCe Icon", "1.5 dCi Touch", "1.5 dCi Icon"],
        "Captur": ["Farketmez", "1.0 TCe Touch", "1.3 TCe Icon", "1.5 dCi Icon"],
        "Kadjar": ["Farketmez", "1.5 dCi Touch", "1.5 dCi Icon", "1.3 TCe Icon"],
    },
    "Fiat": {
        "Egea": ["Farketmez", "1.4 Fire Easy", "1.4 Fire Urban", "1.3 Multijet Easy", "1.3 Multijet Urban", "1.6 Multijet Lounge", "1.6 E-Torq Urban"],
        "Doblo": ["Farketmez", "1.3 Multijet Easy", "1.6 Multijet Premio", "1.6 Multijet Safeline"],
        "Fiorino": ["Farketmez", "1.3 Multijet Pop", "1.3 Multijet Premio", "1.3 Multijet Safeline"],
    },
    "Hyundai": {
        "i20": ["Farketmez", "1.2 MPI Jump", "1.4 MPI Style", "1.4 MPI Elite", "1.0 T-GDI Style"],
        "i30": ["Farketmez", "1.4 MPI Style", "1.6 CRDi Style", "1.6 CRDi Elite"],
        "Tucson": ["Farketmez", "1.6 GDI Style", "1.6 T-GDI Elite", "1.6 CRDi Elite", "1.6 T-GDI N Line"],
        "Bayon": ["Farketmez", "1.4 MPI Jump", "1.4 MPI Style", "1.0 T-GDI Elite"],
    },
    "Ford": {
        "Focus": ["Farketmez", "1.0 EcoBoost Trend X", "1.5 TDCi Trend X", "1.5 TDCi Titanium", "1.6 TDCi Titanium"],
        "Kuga": ["Farketmez", "1.5 EcoBoost Style", "1.5 EcoBoost Titanium", "1.5 EcoBoost ST-Line", "2.0 TDCi Titanium"],
        "Fiesta": ["Farketmez", "1.1 Trend", "1.0 EcoBoost Titanium", "1.5 TDCi Titanium"],
        "Puma": ["Farketmez", "1.0 EcoBoost Style", "1.0 EcoBoost Titanium", "1.0 EcoBoost ST-Line"],
    },
    "Peugeot": {
        "3008": ["Farketmez", "1.2 PureTech Active", "1.2 PureTech Allure", "1.5 BlueHDi Active", "1.5 BlueHDi Allure", "1.5 BlueHDi GT Line"],
        "2008": ["Farketmez", "1.2 PureTech Active", "1.2 PureTech Allure", "1.5 BlueHDi Allure", "1.5 BlueHDi GT Line"],
        "308": ["Farketmez", "1.2 PureTech Active", "1.2 PureTech Allure", "1.6 BlueHDi Allure"],
    },
    "Opel": {
        "Astra": ["Farketmez", "1.4 Turbo Enjoy", "1.4 Turbo Excellence", "1.5 Diesel Elegance", "1.6 CDTI Enjoy"],
        "Corsa": ["Farketmez", "1.2 Edition", "1.2 Elegance", "1.2 Turbo Elegance", "1.5 Diesel Edition"],
        "Grandland": ["Farketmez", "1.2 Turbo Edition", "1.2 Turbo Elegance", "1.5 Diesel Elegance"],
    },
    "BMW": {"3 Serisi": ["Farketmez", "316i", "318i", "320i", "320d"], "5 Serisi": ["Farketmez", "520i", "520d", "530i", "530d"], "X1": ["Farketmez", "sDrive18i", "sDrive18d", "xDrive20d"], "X3": ["Farketmez", "xDrive20d", "xDrive30i"]},
    "Mercedes-Benz": {"C Serisi": ["Farketmez", "C180 AMG", "C200d AMG", "C200 4Matic"], "E Serisi": ["Farketmez", "E180", "E200", "E220d"], "GLA": ["Farketmez", "GLA 180", "GLA 200", "GLA 200d"], "A Serisi": ["Farketmez", "A180", "A200", "A180d"]},
    "Audi": {"A3": ["Farketmez", "1.0 TFSI", "1.4 TFSI", "1.6 TDI", "30 TFSI", "35 TFSI"], "A4": ["Farketmez", "1.4 TFSI", "2.0 TDI", "40 TDI", "40 TFSI"], "Q3": ["Farketmez", "1.4 TFSI", "35 TFSI", "35 TDI"], "Q5": ["Farketmez", "2.0 TDI", "40 TDI", "45 TFSI"]},
}

CITIES = ["Tüm Türkiye", "Adana", "Ankara", "Antalya", "Balıkesir", "Bursa", "Eskişehir", "İstanbul", "İzmir", "Kocaeli", "Konya", "Sakarya", "Tekirdağ", "Yalova"]
TRANSMISSIONS = ["Farketmez", "Otomatik", "Yarı Otomatik", "Manuel"]
FUELS = ["Farketmez", "Benzin", "Dizel", "LPG", "Hibrit", "Elektrik"]
SUV_MODELS = {"Tiguan", "T-Roc", "Kuga", "Tucson", "3008", "2008", "C-HR", "RAV4", "CR-V", "HR-V", "Kadjar", "Captur", "Puma", "Grandland", "X1", "X3", "Q3", "Q5", "GLA"}

TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def tr_slug(s):
    s = (s or "").translate(TR_MAP).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")

def norm(s):
    return re.sub(r"\s+", " ", (s or "").translate(TR_MAP).lower()).strip()

def int_only(v):
    if v is None or v == "": return None
    m = re.sub(r"[^0-9]", "", str(v))
    return int(m) if m else None

def parse_price(text):
    if not text: return None
    pats = [r"(\d{1,3}(?:[\.\s]\d{3})+|\d{6,9})\s*(?:tl|₺)", r"(?:tl|₺)\s*(\d{1,3}(?:[\.\s]\d{3})+|\d{6,9})"]
    for p in pats:
        m = re.search(p, text, flags=re.I)
        if m:
            n = int_only(m.group(1))
            if n and 10000 <= n <= 20000000: return n
    return None

def parse_year(text):
    if not text: return None
    years = [int(y) for y in re.findall(r"\b(19[8-9]\d|20[0-3]\d)\b", text)]
    if not years: return None
    return max([y for y in years if 1980 <= y <= 2035], default=None)

def parse_km(text):
    if not text: return None
    pats = [r"(\d{1,3}(?:[\.\s]\d{3})+|\d{4,7})\s*(?:km|kilometre)", r"km\s*(\d{1,3}(?:[\.\s]\d{3})+|\d{4,7})"]
    vals = []
    for p in pats:
        for m in re.finditer(p, text, flags=re.I):
            n = int_only(m.group(1))
            if n and 0 <= n <= 1000000:
                vals.append(n)
    return min(vals) if vals else None

def money(n):
    if n is None: return "Fiyat yok"
    return f"{n:,}".replace(",", ".") + " TL"

def km_text(n):
    if n is None: return ""
    return f"{n:,}".replace(",", ".") + " km"

def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    try:
        _init_db_inner()
    except Exception as e:
        backup = DB_PATH.with_suffix(f".bozuk_{int(time.time())}.db")
        try:
            if DB_PATH.exists(): DB_PATH.rename(backup)
        except Exception:
            pass
        _init_db_inner()

def _init_db_inner():
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS searches(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, brand TEXT, model TEXT, variant TEXT, city TEXT,
            min_year INTEGER, max_year INTEGER, max_km INTEGER, min_price INTEGER, max_price INTEGER,
            fuel TEXT, transmission TEXT, sources TEXT,
            interval_hours INTEGER DEFAULT 4, active INTEGER DEFAULT 1,
            email TEXT, telegram_chat_id TEXT,
            created_at TEXT, last_checked TEXT, last_status TEXT DEFAULT '', found_count INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS listings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER, listing_key TEXT, source TEXT, title TEXT, url TEXT,
            price INTEGER, old_price INTEGER, year INTEGER, km INTEGER, city TEXT,
            first_seen TEXT, last_seen TEXT,
            UNIQUE(search_id, listing_key)
        );
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER, event_type TEXT, source TEXT, title TEXT, url TEXT,
            price INTEGER, old_price INTEGER, created_at TEXT, sent INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_listings_search ON listings(search_id);
        CREATE INDEX IF NOT EXISTS idx_events_search ON events(search_id);
        """)

def row_to_dict(row):
    d = dict(row)
    if "sources" in d:
        try: d["sources"] = json.loads(d["sources"] or "[]")
        except Exception: d["sources"] = []
    return d

def search_terms(s):
    parts = [s.get("brand"), s.get("model")]
    if s.get("variant") and s.get("variant") != "Farketmez": parts.append(s.get("variant"))
    return " ".join([p for p in parts if p])

def source_open_url(source, s):
    q = search_terms(s)
    qenc = quote_plus(q)
    brand = tr_slug(s.get("brand"))
    model = tr_slug(s.get("model"))
    variant = tr_slug(s.get("variant") if s.get("variant") != "Farketmez" else "")
    city = tr_slug(s.get("city") if s.get("city") != "Tüm Türkiye" else "")
    params = []
    if s.get("min_price"): params.append(f"price_min={s['min_price']}")
    if s.get("max_price"): params.append(f"price_max={s['max_price']}")
    if s.get("min_year"): params.append(f"year_min={s['min_year']}")
    if s.get("max_year"): params.append(f"year_max={s['max_year']}")
    if s.get("max_km"): params.append(f"km_max={s['max_km']}")
    qs = "&".join(params)
    if source == "arabam":
        cat = "arazi-suv-pick-up" if s.get("model") in SUV_MODELS else "otomobil"
        path = f"https://www.arabam.com/ikinci-el/{cat}/{brand}-{model}"
        if variant: path += f"-{variant}"
        if city: path += f"-{city}"
        return path + ("?" + qs if qs else "")
    if source == "sahibinden":
        # Sahibinden arama sayfası en dayanıklı açık linktir.
        extra = []
        if s.get("max_km"): extra.append(f"a4_max={s['max_km']}")
        if s.get("min_year"): extra.append(f"a5_min={s['min_year']}")
        if s.get("max_year"): extra.append(f"a5_max={s['max_year']}")
        if s.get("min_price"): extra.append(f"price_min={s['min_price']}")
        if s.get("max_price"): extra.append(f"price_max={s['max_price']}")
        return "https://www.sahibinden.com/arama?query=" + qenc + ("&" + "&".join(extra) if extra else "")
    if source == "facebook": return "https://www.facebook.com/marketplace/search/?query=" + qenc
    if source == "letgo": return "https://www.letgo.com/search?q=" + qenc
    if source == "vavacars": return "https://tr.vava.cars/ikinci-el-araba?search=" + qenc
    if source == "otoplus": return f"https://www.otoplus.com/{brand}/{model}" + (f"/{brand}-{model}-{variant}" if variant else "")
    if source == "otokoc": return f"https://www.otokocikinciel.com/ikinci-el-{brand}-{model}"
    if source == "arabasepeti": return "https://www.arabasepeti.com/arama?search=" + qenc
    if source == "arabalar": return f"https://www.arabalar.com/ikinci-el/{brand}/{model}"
    return "https://www.google.com/search?q=" + quote_plus(q + " " + SOURCES.get(source, {}).get("domain", ""))

def likely_listing_url(source, url, title, text):
    u = urlparse(url)
    full = norm(" ".join([url, title or "", text or ""]))
    bad_words = ["arama", "search", "kategori", "category", "fiyatlari", "fiyatları", "liste", "listeleniyor", "filtrele", "compare", "favori"]
    if any(w in full for w in bad_words) and not re.search(r"/ilan/|marketplace/item|/arac-|/vehicle|/detail|/detay", full):
        return False
    if source in ("arabam", "sahibinden"):
        return "/ilan/" in u.path
    if source == "facebook": return "/marketplace/item" in u.path
    if source == "letgo": return any(x in u.path for x in ["/item", "/i/", "/ilan", "/ad/"])
    if source == "vavacars": return any(x in u.path.lower() for x in ["detay", "detail", "arac", "vehicle"])
    if source == "otoplus":
        # Tekil değilse en az başlık/snippetten yıl-km-fiyat şartı aranır.
        if any(x in u.path.lower() for x in ["detay", "detail", "arac-"]): return True
        return parse_price(text) is not None and parse_year(text) is not None and parse_km(text) is not None
    if source == "otokoc": return parse_price(text) is not None and parse_year(text) is not None and parse_km(text) is not None
    if source in ("arabasepeti", "arabalar"):
        if "/ilan" in u.path or "/arac" in u.path: return True
        return parse_price(text) is not None and parse_year(text) is not None
    return False

def criteria_match(s, title, text, url, source):
    hay = norm(" ".join([title or "", text or "", url or ""]))
    brand = norm(s.get("brand"))
    model = norm(s.get("model"))
    variant = norm(s.get("variant"))
    if brand and brand not in hay: return False
    if model and model not in hay: return False
    if variant and variant != "farketmez":
        vtoks = [t for t in re.split(r"[^a-z0-9]+", variant) if len(t) > 1]
        # Motor-paket çok sert olmasın ama yarısını yakalasın.
        if vtoks:
            hits = sum(1 for t in vtoks if t in hay)
            if hits < max(1, len(vtoks)//2): return False
    price = parse_price(text or title or "")
    year = parse_year(text or title or "")
    km = parse_km(text or title or "")
    if price is not None:
        if s.get("min_price") and price < s.get("min_price"): return False
        if s.get("max_price") and price > s.get("max_price"): return False
    if year is not None:
        if s.get("min_year") and year < s.get("min_year"): return False
        if s.get("max_year") and year > s.get("max_year"): return False
    if km is not None and s.get("max_km") and km > s.get("max_km"): return False
    if not likely_listing_url(source, url, title, text): return False
    return True

def listing_key(source, url):
    u = urlparse(url)
    path = re.sub(r"/$", "", u.path)
    return source + ":" + u.netloc.replace("www.", "") + path

def safe_get(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQ_TIMEOUT, allow_redirects=True)
        return r.status_code, r.text[:250000], str(r.url)
    except Exception as e:
        return 0, str(e), url

def reader_get(url):
    # Jina Reader: https://r.jina.ai/https://example.com
    try:
        r = requests.get("https://r.jina.ai/" + url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=REQ_TIMEOUT+12)
        return r.status_code, r.text[:250000]
    except Exception as e:
        return 0, str(e)

def search_jina(query):
    try:
        url = "https://s.jina.ai/" + quote_plus(query)
        r = requests.get(url, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=REQ_TIMEOUT+12)
        if r.status_code != 200:
            return r.status_code, []
        txt = r.text[:250000]
        return 200, parse_markdown_links(txt)
    except Exception as e:
        return 0, []

def parse_markdown_links(txt):
    items = []
    # [title](url) markdown, then capture nearby text
    for m in re.finditer(r"\[([^\]]{5,180})\]\((https?://[^\)\s]+)\)", txt):
        title = re.sub(r"\s+", " ", m.group(1)).strip()
        url = m.group(2).strip().rstrip(")")
        start = max(0, m.start() - 300)
        end = min(len(txt), m.end() + 700)
        snippet = re.sub(r"\s+", " ", txt[start:end]).strip()
        items.append({"title": title, "url": url, "text": snippet})
    # Plain URLs fallback
    for m in re.finditer(r"https?://[^\s\)\]<>\"]+", txt):
        url = m.group(0).rstrip(".,)")
        if any(x["url"] == url for x in items): continue
        start = max(0, m.start() - 200)
        end = min(len(txt), m.end() + 500)
        snippet = re.sub(r"\s+", " ", txt[start:end]).strip()
        title = snippet[:120] or url
        items.append({"title": title, "url": url, "text": snippet})
    return items

def parse_html_links(source, html, base_url, s):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        url = urljoin(base_url, a.get("href"))
        if SOURCES[source]["domain"].replace("www.", "") not in urlparse(url).netloc.replace("www.", ""):
            continue
        block = a
        for _ in range(3):
            if block.parent: block = block.parent
        text = re.sub(r"\s+", " ", block.get_text(" ", strip=True))[:1200]
        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True))[:180]
        if not title or len(title) < 4: title = text[:120]
        if criteria_match(s, title, text, url, source):
            out.append(make_listing(s, source, title, url, text))
    return dedupe(out)

def parse_reader_links(source, text, target_url, s):
    candidates = parse_markdown_links(text)
    # Reader sometimes omits full listing links and returns text of a list. For direct Arabam/Otoplus pages, capture rows.
    out = []
    for c in candidates:
        if SOURCES[source]["domain"].replace("www.", "") not in urlparse(c["url"]).netloc.replace("www.", ""):
            continue
        if criteria_match(s, c["title"], c["text"], c["url"], source):
            out.append(make_listing(s, source, c["title"], c["url"], c["text"]))
    # If reader page itself is an individual listing
    if criteria_match(s, search_terms(s), text[:2000], target_url, source):
        out.append(make_listing(s, source, search_terms(s), target_url, text[:2500]))
    return dedupe(out)

def make_listing(s, source, title, url, text):
    title = clean_title(title, s)
    price = parse_price(text) or parse_price(title)
    year = parse_year(text) or parse_year(title)
    km = parse_km(text) or parse_km(title)
    city = detect_city(text) or (s.get("city") if s.get("city") != "Tüm Türkiye" else "")
    return {"source": source, "source_label": SOURCES[source]["label"], "title": title, "url": url, "price": price, "year": year, "km": km, "city": city, "key": listing_key(source, url)}

def clean_title(title, s):
    t = re.sub(r"\s+", " ", (title or "")).strip(" -|•")
    bad = ["filtrele", "arama", "sonuç", "listeleniyor", "tüm araç", "favori", "karşılaştır"]
    if not t or any(b in norm(t) for b in bad) or len(t) < 6:
        return search_terms(s)
    return t[:180]

def detect_city(text):
    n = norm(text)
    for c in CITIES:
        if c == "Tüm Türkiye": continue
        if norm(c) in n: return c
    return ""

def dedupe(items):
    seen = set(); out=[]
    for it in items:
        k = it.get("key") or listing_key(it.get("source"), it.get("url"))
        if k in seen: continue
        seen.add(k); out.append(it)
    return out

def build_search_query(source, s):
    domain = SOURCES[source]["domain"]
    qparts = [f"site:{domain}", s.get("brand"), s.get("model")]
    if s.get("variant") and s.get("variant") != "Farketmez": qparts.append('"' + s.get("variant") + '"')
    qparts.append("ikinci el")
    if s.get("city") and s.get("city") != "Tüm Türkiye": qparts.append(s.get("city"))
    if s.get("min_year"): qparts.append(str(s.get("min_year")))
    if s.get("max_price"): qparts.append(str(s.get("max_price")) + " TL")
    return " ".join([str(x) for x in qparts if x])

def scrape_source(source, s):
    status = []
    results = []
    open_url = source_open_url(source, s)
    # Direct only for sources that return HTML without login sometimes.
    code, html, final_url = safe_get(open_url)
    status.append(f"HTTP {code}")
    if code == 200 and html and "<!doctype" in html.lower() or "<html" in html.lower():
        try:
            direct = parse_html_links(source, html, final_url, s)
            if direct:
                status.append(f"html {len(direct)}")
                results.extend(direct[:MAX_RESULTS_PER_SOURCE])
            else:
                status.append("html liste yok")
        except Exception as e:
            status.append("html hata " + type(e).__name__)
    elif code in (403, 429, 401):
        status.append("doğrudan engel")
    # Reader on open URL, but not Facebook/Letgo because app pages mostly useless.
    if source not in ("facebook", "letgo") and len(results) < 3:
        rcode, rtext = reader_get(open_url)
        status.append(f"reader {rcode}")
        if rcode == 200:
            reader_results = parse_reader_links(source, rtext, open_url, s)
            if reader_results:
                status.append(f"reader liste {len(reader_results)}")
                results.extend(reader_results[:MAX_RESULTS_PER_SOURCE])
    # Jina Search fallback. It returns indexed results and usually gives individual listing links if they exist.
    if len(results) < 8:
        scode, links = search_jina(build_search_query(source, s))
        status.append(f"arama {scode}")
        found = []
        for c in links:
            net = urlparse(c["url"]).netloc.replace("www.", "")
            if SOURCES[source]["domain"].replace("www.", "") not in net:
                continue
            if criteria_match(s, c["title"], c.get("text", ""), c["url"], source):
                found.append(make_listing(s, source, c["title"], c["url"], c.get("text", "")))
        status.append(f"arama liste {len(found)}")
        results.extend(found[:MAX_RESULTS_PER_SOURCE])
    return dedupe(results)[:MAX_RESULTS_PER_SOURCE], " / ".join(status)

def save_results(search_id, results):
    new_count = 0; drop_count = 0
    with db() as con:
        for it in results:
            existing = con.execute("SELECT * FROM listings WHERE search_id=? AND listing_key=?", (search_id, it["key"])).fetchone()
            if not existing:
                con.execute("""INSERT INTO listings(search_id, listing_key, source, title, url, price, old_price, year, km, city, first_seen, last_seen)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (search_id, it["key"], it["source"], it["title"], it["url"], it["price"], None, it["year"], it["km"], it["city"], now_iso(), now_iso()))
                con.execute("""INSERT INTO events(search_id,event_type,source,title,url,price,old_price,created_at) VALUES(?,?,?,?,?,?,?,?)""", (search_id, "new", it["source"], it["title"], it["url"], it["price"], None, now_iso()))
                new_count += 1
            else:
                old_price = existing["price"]
                price = it["price"] or old_price
                if old_price and it["price"] and it["price"] < old_price:
                    con.execute("""INSERT INTO events(search_id,event_type,source,title,url,price,old_price,created_at) VALUES(?,?,?,?,?,?,?,?)""", (search_id, "price_drop", it["source"], it["title"], it["url"], it["price"], old_price, now_iso()))
                    drop_count += 1
                con.execute("""UPDATE listings SET title=?, url=?, price=?, old_price=?, year=?, km=?, city=?, last_seen=? WHERE id=?""", (it["title"], it["url"], price, old_price, it["year"], it["km"], it["city"], now_iso(), existing["id"]))
    return new_count, drop_count

def run_search(search_id):
    with db() as con:
        row = con.execute("SELECT * FROM searches WHERE id=?", (search_id,)).fetchone()
    if not row: return
    s = row_to_dict(row)
    statuses = []
    all_results = []
    for src in s.get("sources", []):
        if src not in SOURCES: continue
        try:
            res, st = scrape_source(src, s)
            statuses.append(f"{SOURCES[src]['label']}: {st} / liste {len(res)}")
            all_results.extend(res)
        except Exception as e:
            statuses.append(f"{SOURCES[src]['label']}: hata {type(e).__name__}")
    all_results = dedupe(all_results)
    new_count, drop_count = save_results(search_id, all_results)
    with db() as con:
        count = con.execute("SELECT COUNT(*) c FROM listings WHERE search_id=?", (search_id,)).fetchone()["c"]
        con.execute("UPDATE searches SET last_checked=?, last_status=?, found_count=? WHERE id=?", (now_iso(), f"Kontrol tamamlandı. Görülen {len(all_results)}, yeni {new_count}, fiyat düşen {drop_count} | " + " ; ".join(statuses), count, search_id))
    try:
        send_pending_events(search_id)
    except Exception:
        pass

def run_search_async(search_id):
    t = threading.Thread(target=run_search, args=(search_id,), daemon=True)
    t.start()

def send_pending_events(search_id):
    with db() as con:
        s = con.execute("SELECT * FROM searches WHERE id=?", (search_id,)).fetchone()
        events = con.execute("SELECT * FROM events WHERE search_id=? AND sent=0 ORDER BY id DESC LIMIT 20", (search_id,)).fetchall()
    if not s or not events:
        return
    for ev in events:
        if ev["event_type"] == "price_drop":
            msg = f"📉 Fiyat düştü\n{ev['title']}\n{SOURCES.get(ev['source'],{}).get('label',ev['source'])}\nEski: {money(ev['old_price'])}\nYeni: {money(ev['price'])}\n{ev['url']}"
        else:
            msg = f"🚗 Yeni ilan\n{ev['title']}\n{SOURCES.get(ev['source'],{}).get('label',ev['source'])}\nFiyat: {money(ev['price'])}\n{ev['url']}"
        email_to = (s["email"] or os.environ.get("DEFAULT_NOTIFY_EMAIL") or os.environ.get("NOTIFY_EMAIL") or "").strip()
        telegram_to = (s["telegram_chat_id"] or os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
        sent_any = False
        if telegram_to:
            ok, _detail = send_telegram(msg, telegram_to)
            sent_any = ok or sent_any
        if email_to:
            ok, _detail = send_email(email_to, "Araç Avcısı bildirimi", msg)
            sent_any = ok or sent_any
        if sent_any:
            with db() as con:
                con.execute("UPDATE events SET sent=1 WHERE id=?", (ev["id"],))


def notification_config_status():
    return {
        "telegram_token": bool(os.environ.get("TELEGRAM_BOT_TOKEN")),
        "telegram_chat_id_env": bool(os.environ.get("TELEGRAM_CHAT_ID")),
        "smtp_host": bool(os.environ.get("SMTP_HOST")),
        "smtp_user": bool(os.environ.get("SMTP_USER")),
        "smtp_pass": bool(os.environ.get("SMTP_PASS")),
        "mail_from": bool(os.environ.get("MAIL_FROM")),
        "default_notify_email": bool(os.environ.get("DEFAULT_NOTIFY_EMAIL") or os.environ.get("NOTIFY_EMAIL")),
    }


def send_telegram(text, chat_id):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = (chat_id or "").strip()
    if not token:
        return False, "TELEGRAM_BOT_TOKEN eksik"
    if not chat_id:
        return False, "TELEGRAM_CHAT_ID eksik"
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text, "disable_web_page_preview": False},
            timeout=20,
        )
        if r.status_code == 200:
            return True, "Telegram gönderildi"
        return False, f"Telegram hata HTTP {r.status_code}: {r.text[:250]}"
    except Exception as e:
        return False, f"Telegram bağlantı hatası: {type(e).__name__}: {e}"


def send_email(to_addr, subject, body):
    import smtplib
    from email.message import EmailMessage
    host = (os.environ.get("SMTP_HOST") or "").strip()
    user = (os.environ.get("SMTP_USER") or "").strip()
    pw = (os.environ.get("SMTP_PASS") or "").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))
    to_addr = (to_addr or "").strip()
    if not to_addr:
        return False, "Mail alıcısı yok"
    if not host:
        return False, "SMTP_HOST eksik"
    if not user:
        return False, "SMTP_USER eksik"
    if not pw:
        return False, "SMTP_PASS eksik"
    msg = EmailMessage()
    msg["From"] = os.environ.get("MAIL_FROM", user)
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, port, timeout=25) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
        return True, "Mail gönderildi"
    except Exception as e:
        return False, f"Mail gönderim hatası: {type(e).__name__}: {e}"


@APP.route("/")
def index():
    return render_template("index.html", version=VERSION)

@APP.route("/health")
def health():
    return jsonify(ok=True, version=VERSION, time=now_iso(), data_dir=str(DATA_DIR), db_exists=DB_PATH.exists(), notifications=notification_config_status())

@APP.route("/reset-cache")
def reset_cache():
    return render_template("reset_cache.html")

@APP.route("/reset-db")
def reset_db():
    key = request.args.get("key")
    if key != os.environ.get("RESET_KEY", "temizle"):
        return jsonify(ok=False, error="RESET_KEY yanlış. Render Environment içine RESET_KEY ekle veya ?key=temizle kullan."), 403
    try:
        if DB_PATH.exists(): DB_PATH.unlink()
        init_db()
        return jsonify(ok=True, message="Veritabanı sıfırlandı", version=VERSION)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@APP.route("/api/notifications/status")
def api_notification_status():
    return jsonify(ok=True, version=VERSION, config=notification_config_status())


@APP.route("/api/notifications/test", methods=["POST"])
def api_notification_test():
    data = request.get_json(silent=True) or {}
    email_to = (data.get("email") or os.environ.get("DEFAULT_NOTIFY_EMAIL") or os.environ.get("NOTIFY_EMAIL") or "").strip()
    telegram_to = (data.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    msg = "✅ Araç Avcısı test bildirimi\nBildirim bağlantısı çalışıyor. Bundan sonra yeni ilan ve fiyat düşüşü olursa linkli bildirim gönderilir."
    results = []
    ok_any = False
    if telegram_to or os.environ.get("TELEGRAM_BOT_TOKEN"):
        ok, detail = send_telegram(msg, telegram_to)
        results.append({"channel": "telegram", "ok": ok, "detail": detail})
        ok_any = ok_any or ok
    else:
        results.append({"channel": "telegram", "ok": False, "detail": "Telegram bilgisi yok: TELEGRAM_BOT_TOKEN ve TELEGRAM_CHAT_ID gerekli"})
    if email_to or os.environ.get("SMTP_HOST") or os.environ.get("SMTP_USER"):
        ok, detail = send_email(email_to, "Araç Avcısı test bildirimi", msg)
        results.append({"channel": "mail", "ok": ok, "detail": detail})
        ok_any = ok_any or ok
    else:
        results.append({"channel": "mail", "ok": False, "detail": "Mail bilgisi yok: SMTP_HOST, SMTP_USER, SMTP_PASS ve alıcı mail gerekli"})
    return jsonify(ok=ok_any, results=results, config=notification_config_status())


@APP.route("/api/searches/<int:sid>/notify-test", methods=["POST"])
def api_search_notify_test(sid):
    with db() as con:
        s = con.execute("SELECT * FROM searches WHERE id=?", (sid,)).fetchone()
    if not s:
        return jsonify(ok=False, error="Takip bulunamadı"), 404
    s = row_to_dict(s)
    msg = f"✅ Araç Avcısı takip test bildirimi\n{s.get('name')}\nBu takip için bildirim çalışıyor. Yeni ilan veya fiyat düşüşü yakalanırsa ilan linkiyle gönderilecek."
    email_to = (s.get("email") or os.environ.get("DEFAULT_NOTIFY_EMAIL") or os.environ.get("NOTIFY_EMAIL") or "").strip()
    telegram_to = (s.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID") or "").strip()
    results = []
    ok_any = False
    ok, detail = send_telegram(msg, telegram_to)
    results.append({"channel": "telegram", "ok": ok, "detail": detail})
    ok_any = ok_any or ok
    ok, detail = send_email(email_to, "Araç Avcısı takip test bildirimi", msg)
    results.append({"channel": "mail", "ok": ok, "detail": detail})
    ok_any = ok_any or ok
    return jsonify(ok=ok_any, results=results, config=notification_config_status())

@APP.route("/api/options")
def api_options():
    return jsonify(sources=SOURCES, vehicles=VEHICLE_DATA, cities=CITIES, fuels=FUELS, transmissions=TRANSMISSIONS, version=VERSION)

@APP.route("/api/searches", methods=["GET", "POST"])
def api_searches():
    if request.method == "POST":
        data = request.get_json(force=True)
        brand = (data.get("brand_custom") or data.get("brand") or "").strip()
        model = (data.get("model_custom") or data.get("model") or "").strip()
        variant = (data.get("variant_custom") or data.get("variant") or "Farketmez").strip() or "Farketmez"
        name = (data.get("name") or f"{brand} {model} {'' if variant=='Farketmez' else variant}").strip()
        sources = data.get("sources") or list(SOURCES.keys())
        if not brand or not model:
            return jsonify(ok=False, error="Marka ve model zorunlu"), 400
        with db() as con:
            cur = con.execute("""INSERT INTO searches(name, brand, model, variant, city, min_year, max_year, max_km, min_price, max_price, fuel, transmission, sources, interval_hours, active, email, telegram_chat_id, created_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (name, brand, model, variant, data.get("city") or "Tüm Türkiye", int_only(data.get("min_year")), int_only(data.get("max_year")), int_only(data.get("max_km")), int_only(data.get("min_price")), int_only(data.get("max_price")), data.get("fuel") or "Farketmez", data.get("transmission") or "Farketmez", json.dumps(sources, ensure_ascii=False), int_only(data.get("interval_hours")) or 4, 1, data.get("email") or "", data.get("telegram_chat_id") or "", now_iso()))
            sid = cur.lastrowid
            con.execute("UPDATE searches SET last_status=? WHERE id=?", ("Takip kaydedildi. İlk kontrol arka planda başladı.", sid))
        run_search_async(sid)
        return jsonify(ok=True, id=sid, message="Takip kaydedildi. İlk kontrol arka planda başladı.")
    with db() as con:
        rows = con.execute("SELECT * FROM searches ORDER BY id DESC").fetchall()
    data = []
    for r in rows:
        d = row_to_dict(r)
        d["open_urls"] = {src: source_open_url(src, d) for src in d.get("sources", []) if src in SOURCES}
        data.append(d)
    return jsonify(ok=True, searches=data)

@APP.route("/api/searches/<int:sid>/run", methods=["POST"])
def api_run(sid):
    run_search(sid)
    return jsonify(ok=True)

@APP.route("/api/searches/<int:sid>/toggle", methods=["POST"])
def api_toggle(sid):
    with db() as con:
        row = con.execute("SELECT active FROM searches WHERE id=?", (sid,)).fetchone()
        if not row: return jsonify(ok=False), 404
        con.execute("UPDATE searches SET active=? WHERE id=?", (0 if row["active"] else 1, sid))
    return jsonify(ok=True)

@APP.route("/api/searches/<int:sid>/interval", methods=["POST"])
def api_interval(sid):
    hours = int_only((request.get_json(force=True) or {}).get("interval_hours")) or 4
    with db() as con:
        con.execute("UPDATE searches SET interval_hours=? WHERE id=?", (hours, sid))
    return jsonify(ok=True)

@APP.route("/api/searches/<int:sid>", methods=["DELETE"])
def api_delete(sid):
    with db() as con:
        con.execute("DELETE FROM listings WHERE search_id=?", (sid,))
        con.execute("DELETE FROM events WHERE search_id=?", (sid,))
        con.execute("DELETE FROM searches WHERE id=?", (sid,))
    return jsonify(ok=True)

@APP.route("/api/searches/<int:sid>/results")
def api_results(sid):
    with db() as con:
        rows = con.execute("SELECT * FROM listings WHERE search_id=? ORDER BY COALESCE(price, 999999999), last_seen DESC", (sid,)).fetchall()
    return jsonify(ok=True, results=[dict(r, price_text=money(r["price"]), km_text=km_text(r["km"]), source_label=SOURCES.get(r["source"], {}).get("label", r["source"])) for r in rows])

@APP.route("/api/events")
def api_events():
    with db() as con:
        rows = con.execute("SELECT * FROM events ORDER BY id DESC LIMIT 50").fetchall()
    return jsonify(ok=True, events=[dict(r, price_text=money(r["price"]), old_price_text=money(r["old_price"]), source_label=SOURCES.get(r["source"], {}).get("label", r["source"])) for r in rows])


def scheduler_tick():
    try:
        with db() as con:
            rows = con.execute("SELECT * FROM searches WHERE active=1").fetchall()
        for r in rows:
            d = row_to_dict(r)
            last = d.get("last_checked")
            interval = int(d.get("interval_hours") or 4)
            due = True
            if last:
                try:
                    due = datetime.fromisoformat(last) + timedelta(hours=interval) <= datetime.now(timezone.utc)
                except Exception:
                    due = True
            if due:
                run_search_async(d["id"])
    except Exception:
        pass

init_db()
try:
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(scheduler_tick, "interval", minutes=int(os.environ.get("SCHEDULER_TICK_MINUTES", "15")))
    scheduler.start()
except Exception:
    pass

if __name__ == "__main__":
    APP.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5050")), debug=False)
# Compatibility for old Render commands using app:app
app = APP
