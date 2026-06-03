import os
import re
import json
import time
import sqlite3
import hashlib
import smtplib
import unicodedata
from email.mime.text import MIMEText
from datetime import datetime, timezone
from urllib.parse import quote_plus, urljoin

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

CHECK_INTERVAL_HOURS = int(os.getenv("CHECK_INTERVAL_HOURS", "4"))

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
SOURCE_DEFS = [
    {"key": "sahibinden", "name": "Sahibinden", "base": "https://www.sahibinden.com", "template": "https://www.sahibinden.com/otomobil?query_text={q}"},
    {"key": "arabam", "name": "Arabam", "base": "https://www.arabam.com", "template": "https://www.arabam.com/ikinci-el/otomobil?searchText={q}"},
    {"key": "letgo", "name": "Letgo", "base": "https://www.letgo.com", "template": "https://www.letgo.com/tr-tr/otomobil?q={q}"},
    {"key": "facebook", "name": "Facebook Marketplace", "base": "https://www.facebook.com", "template": "https://www.facebook.com/marketplace/search/?query={q}"},
    {"key": "vavacars", "name": "VavaCars", "base": "https://www.vavacars.com", "template": "https://www.vavacars.com/ikinci-el-araba?search={q}"},
    {"key": "otoplus", "name": "Otoplus", "base": "https://www.otoplus.com", "template": "https://www.otoplus.com/ikinci-el-araba?search={q}"},
    {"key": "otokoc", "name": "Otokoç 2. El", "base": "https://www.otokocikinciel.com", "template": "https://www.otokocikinciel.com/ikinci-el-arac?search={q}"},
    {"key": "arabasepeti", "name": "Araba Sepeti", "base": "https://www.arabasepeti.com", "template": "https://www.arabasepeti.com/ikinci-el-araclar?search={q}"},
    {"key": "arabalar", "name": "Arabalar.com", "base": "https://www.arabalar.com.tr", "template": "https://www.arabalar.com.tr/ikinci-el?kelime={q}"},
]


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
        """
    )
    conn.commit()
    conn.close()


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


def build_search_url(source_def, search):
    q_parts = [search["brand"], search["model"]]
    if search["city"] and search["city"] != "Tüm Türkiye":
        q_parts.append(search["city"])
    if search["year_min"]:
        q_parts.append(str(search["year_min"]))
    q = " ".join([str(x) for x in q_parts if x])
    q_enc = quote_plus(q)
    return source_def["template"].format(q=q_enc, brand=tr_slug(search["brand"]), model=tr_slug(search["model"]))


def item_key_for(url, title):
    base = url.split("?")[0].rstrip("/")
    material = base if len(base) > 12 else f"{url}|{title}"
    return hashlib.sha1(material.encode("utf-8", errors="ignore")).hexdigest()


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


def fetch_source(source_def, search, limit=50):
    url = build_search_url(source_def, search)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36 AraçAvcisi/1.0",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    results = []
    status = "ok"
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        status = f"HTTP {resp.status_code}"
        if resp.status_code >= 400:
            return [], {"source": source_def["name"], "url": url, "status": status}
        soup = BeautifulSoup(resp.text, "html.parser")
        anchors = soup.find_all("a", href=True)
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
            # Yakındaki parent kart içinde fiyat/yıl/km bulunabilir.
            parent = a
            for _ in range(3):
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
    except Exception as exc:
        status = f"Hata: {exc.__class__.__name__}: {exc}"
    return results, {"source": source_def["name"], "url": url, "status": status}


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
        items, log = fetch_source(source_def, search)
        logs.append(log)
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
    rows = conn.execute("SELECT id FROM searches WHERE active=1").fetchall()
    conn.close()
    for row in rows:
        try:
            check_search(row["id"], baseline=False)
            time.sleep(2)
        except Exception as exc:
            print(f"Zamanlanmış arama hatası: {row['id']} {exc}")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/options")
def options():
    return jsonify({"catalog": CAR_CATALOG, "cities": CITIES, "sources": SOURCE_DEFS})


@app.route("/api/searches", methods=["GET"])
def list_searches():
    conn = db()
    rows = conn.execute("SELECT * FROM searches ORDER BY id DESC").fetchall()
    data = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d.pop("sources_json"))
        data.append(d)
    conn.close()
    return jsonify(data)


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
    cur = conn.execute(
        """INSERT INTO searches(name,brand,model,city,year_min,year_max,price_min,price_max,km_max,fuel,gear,sources_json,email_to,telegram_chat_id,created_at,last_status)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            name, brand, model, payload.get("city") or "Tüm Türkiye",
            payload.get("year_min") or None, payload.get("year_max") or None,
            payload.get("price_min") or None, payload.get("price_max") or None,
            payload.get("km_max") or None, payload.get("fuel") or "Farketmez", payload.get("gear") or "Farketmez",
            json.dumps(sources, ensure_ascii=False), payload.get("email_to") or "", payload.get("telegram_chat_id") or "",
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


@app.route("/health")
def health():
    return jsonify({"ok": True, "time": now_iso(), "interval_hours": CHECK_INTERVAL_HOURS})


_scheduler = None


def start_scheduler():
    scheduler = BackgroundScheduler(daemon=True, timezone="Europe/Istanbul")
    scheduler.add_job(
        scheduled_job,
        "interval",
        hours=CHECK_INTERVAL_HOURS,
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


# Cloud deploys import app:app with gunicorn. The scheduler and database must start on import.
boot_app()


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("PORT") or os.getenv("APP_PORT", "5050"))
    app.run(host=host, port=port, debug=False)
