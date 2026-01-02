import os
import sqlite3
import secrets
import string
from datetime import datetime, date, timedelta

import requests
import stripe
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "super-secret-key")
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DATABASE = os.path.join(app.root_path, "kimq.db")


# ---------- Database helpers ----------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT,
            role TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            notes TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price_cents INTEGER NOT NULL,
            deposit_cents INTEGER NOT NULL,
            image_url TEXT,
            category TEXT,
            calendar_color TEXT,
            duration_minutes INTEGER DEFAULT 60,
            processing_minutes INTEGER DEFAULT 0,
            block_minutes INTEGER DEFAULT 0,
            require_deposit INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            service_id INTEGER,
            employee_id INTEGER,
            start_time TEXT,
            status TEXT,
            notes TEXT,
            payment_intent_id TEXT,
            payment_status TEXT,
            amount_cents INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES clients(id),
            FOREIGN KEY(service_id) REFERENCES services(id),
            FOREIGN KEY(employee_id) REFERENCES users(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            weekday INTEGER,
            start_time TEXT,
            end_time TEXT,
            FOREIGN KEY(employee_id) REFERENCES users(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS time_off (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER,
            start_time TEXT,
            end_time TEXT,
            reason TEXT,
            FOREIGN KEY(employee_id) REFERENCES users(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS client_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            author_id INTEGER,
            note TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES clients(id),
            FOREIGN KEY(author_id) REFERENCES users(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS client_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            url TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(client_id) REFERENCES clients(id)
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS gift_cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            to_name TEXT,
            from_name TEXT,
            amount_cents INTEGER,
            balance_cents INTEGER,
            message TEXT,
            email TEXT,
            status TEXT,
            payment_intent_id TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_intent_id TEXT,
            amount_cents INTEGER,
            status TEXT,
            client_email TEXT,
            category TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """
    )
    try:
        cur.execute("ALTER TABLE services ADD COLUMN image_url TEXT")
    except sqlite3.OperationalError:
        pass
    for column, default in [
        ("category", "Bridal"),
        ("calendar_color", "#f9b5d0"),
        ("duration_minutes", 90),
        ("processing_minutes", 0),
        ("block_minutes", 0),
        ("require_deposit", 1),
    ]:
        try:
            cur.execute(
                f"ALTER TABLE services ADD COLUMN {column} {'INTEGER' if 'minutes' in column or column=='require_deposit' else 'TEXT'}"
            )
            cur.execute(f"UPDATE services SET {column}=?", (default,))
        except sqlite3.OperationalError:
            pass
    conn.commit()
    seed_users(conn)
    seed_services(conn)
    seed_availability(conn)
    seed_settings(conn)
    conn.close()


def seed_users(conn):
    cur = conn.cursor()
    existing = cur.execute("SELECT COUNT(*) as c FROM users").fetchone()[0]
    if existing:
        return
    users = [
        {
            "name": "Kim Quraishi",
            "email": "quraishi1125@gmail.com",
            "phone": "(313) 598-0229",
            "role": "admin",
            "password": "adminpass",
        },
        {
            "name": "Lena Stylist",
            "email": "lena@studio.com",
            "phone": "555-0101",
            "role": "employee",
            "password": "employeepass",
        },
        {
            "name": "Maya Artist",
            "email": "maya@studio.com",
            "phone": "555-0102",
            "role": "employee",
            "password": "employeepass",
        },
    ]
    for u in users:
        cur.execute(
            "INSERT INTO users (name, email, phone, role, password_hash) VALUES (?, ?, ?, ?, ?)",
            (
                u["name"],
                u["email"],
                u["phone"],
                u["role"],
                generate_password_hash(u["password"]),
            ),
        )
    conn.commit()


def seed_services(conn):
    cur = conn.cursor()
    existing = cur.execute("SELECT COUNT(*) as c FROM services").fetchone()[0]
    if existing:
        return
    services = [
        (
            "Bridal Makeup",
            "Signature bridal glam tailored to your look.",
            29500,
            10000,
            "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=1200&q=80",
            "Bridal",
            120,
            30,
            15,
            "#f9b5d0",
        ),
        (
            "Pre Wedding",
            "Polished look for pre-wedding celebrations.",
            22500,
            9000,
            "https://images.unsplash.com/photo-1515377905703-c4788e51af15?auto=format&fit=crop&w=1200&q=80",
            "Events",
            90,
            15,
            15,
            "#f2d4ae",
        ),
        (
            "Engagement",
            "Camera-ready engagement makeup.",
            25000,
            10000,
            "https://images.unsplash.com/photo-1509631171560-7e2e4ba0b82b?auto=format&fit=crop&w=1200&q=80",
            "Engagement",
            105,
            15,
            15,
            "#b8d8ba",
        ),
        (
            "Bridal Trial",
            "Test drive your wedding-day glam.",
            19500,
            7500,
            "https://images.unsplash.com/photo-1511288593014-8acb33db1c83?auto=format&fit=crop&w=1200&q=80",
            "Trials",
            90,
            0,
            15,
            "#d1c4e9",
        ),
        (
            "Bridal Style",
            "Luxurious bridal hair styling.",
            32500,
            12000,
            "https://images.unsplash.com/photo-1504208458-46c492d1571c?auto=format&fit=crop&w=1200&q=80",
            "Bridal",
            120,
            30,
            15,
            "#f9b5d0",
        ),
        (
            "Pre-Wedding Events",
            "Event-perfect styling for festivities.",
            26500,
            10000,
            "https://images.unsplash.com/photo-1504674900247-0877df9cc836?auto=format&fit=crop&w=1200&q=80",
            "Events",
            90,
            15,
            15,
            "#f2d4ae",
        ),
        (
            "Bridal Trial Style",
            "Trial run for your bridal hairstyle.",
            19500,
            7500,
            "https://images.unsplash.com/photo-1503341455253-b2e723bb3dbb?auto=format&fit=crop&w=1200&q=80",
            "Trials",
            90,
            0,
            15,
            "#d1c4e9",
        ),
        (
            "Engagement Style",
            "Romantic styling for engagement day.",
            25500,
            9500,
            "https://images.unsplash.com/photo-1504198453319-5ce911bafcde?auto=format&fit=crop&w=1200&q=80",
            "Engagement",
            90,
            15,
            15,
            "#b8d8ba",
        ),
        (
            "Formal Style",
            "Elevated formal hair styling.",
            11500,
            5000,
            "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?auto=format&fit=crop&w=1200&q=80",
            "Events",
            75,
            0,
            15,
            "#f2d4ae",
        ),
        (
            "Blow Dry",
            "Smooth, glossy blowout.",
            4500,
            2000,
            "https://images.unsplash.com/photo-1503999422166-6dcb1cdbe1b5?auto=format&fit=crop&w=1200&q=80",
            "Add-On",
            60,
            0,
            15,
            "#c5e1f5",
        ),
    ]
    for name, desc, price, deposit, image_url, category, duration, processing, block, color in services:
        cur.execute(
            """
            INSERT INTO services (name, description, price_cents, deposit_cents, image_url, category, duration_minutes, processing_minutes, block_minutes, calendar_color)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, desc, price, deposit, image_url, category, duration, processing, block, color),
        )
    conn.commit()


def seed_availability(conn):
    cur = conn.cursor()
    existing = cur.execute("SELECT COUNT(*) FROM availability").fetchone()[0]
    if existing:
        return
    employees = cur.execute("SELECT id FROM users WHERE role IN ('employee','admin')").fetchall()
    for emp in employees:
        for weekday in range(0, 5):
            cur.execute(
                "INSERT INTO availability (employee_id, weekday, start_time, end_time) VALUES (?, ?, ?, ?)",
                (emp["id"], weekday, "08:00", "20:00"),
            )
    conn.commit()


def seed_settings(conn):
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO site_settings (key, value) VALUES ('announcement', 'Now booking 8am-8pm with Kim Quraishi. Text (313) 598-0229 for concierge-free support.')"
    )
    conn.commit()


# ---------- Utilities ----------

def format_currency(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def save_uploaded_image(file_storage):
    if not file_storage or not file_storage.filename:
        return None
    filename = secure_filename(file_storage.filename)
    dest_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file_storage.save(dest_path)
    return f"/static/uploads/{filename}"


@app.template_filter("beauty_time")
def beauty_time(value: str | None):
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value
    return dt.strftime("%b %d, %I:%M %p")


def require_role(role_name):
    user = current_user()
    return user and user["role"] == role_name


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return user


# ---------- Integration helpers ----------

def create_payment_intent(amount_cents: int, description: str, customer_email: str | None = None):
    test_key = os.environ.get("STRIPE_TEST_KEY")
    stripe.api_key = test_key or os.environ.get("STRIPE_SECRET_KEY")
    if not stripe.api_key:
        fake_id = "pi_" + secrets.token_hex(8)
        return fake_id, "simulated"
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency="usd",
        description=description,
        receipt_email=customer_email,
        automatic_payment_methods={"enabled": True},
        metadata={"mode": "test" if test_key else "live"},
    )
    return intent.id, intent.status


def send_email(to_email: str, subject: str, body: str):
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print(f"[email skipped] {subject} -> {to_email}\n{body}")
        return
    requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "from": "Kim Quraishi Beauty Studio <hello@kimq.com>",
            "to": [to_email],
            "subject": subject,
            "html": body,
        },
        timeout=10,
    )


def fetch_instagram_posts(limit: int = 6):
    token = os.environ.get("INSTAGRAM_ACCESS_TOKEN")
    user_id = os.environ.get("INSTAGRAM_USER_ID", "me")
    if not token:
        return []
    try:
        resp = requests.get(
            f"https://graph.instagram.com/{user_id}/media",
            params={
                "fields": "id,caption,media_url,thumbnail_url,permalink",
                "access_token": token,
                "limit": limit,
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        posts = []
        for item in data:
            posts.append(
                {
                    "image": item.get("media_url") or item.get("thumbnail_url"),
                    "caption": item.get("caption", "Studio update"),
                    "permalink": item.get("permalink"),
                }
            )
        return [p for p in posts if p.get("image")][:limit]
    except Exception as exc:  # noqa: BLE001
        print(f"[instagram] failed to load feed: {exc}")
        return []


def read_log_tail(path: str, max_lines: int = 200):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()[-max_lines:]
    return lines


def summarize_logs():
    log_paths = {
        "access": os.environ.get("ACCESS_LOG", "/var/log/www.kimqbeauty.com.access.log"),
        "error": os.environ.get("ERROR_LOG", "/var/log/www.kimqbeauty.com.error.log"),
        "server": os.environ.get("SERVER_LOG", "/var/log/www.kimqbeauty.com.server.log"),
    }
    metrics = {}
    for kind, path in log_paths.items():
        tail = read_log_tail(path)
        metrics[kind] = {
            "path": path,
            "lines": len(tail),
            "recent": tail[-5:] if tail else [],
        }
        if kind == "access" and tail:
            metrics[kind]["today_hits"] = sum(1 for line in tail if datetime.utcnow().strftime("%d/%b/%Y") in line)
    return metrics


def issue_reset_token(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
    conn = get_db()
    conn.execute("DELETE FROM password_resets WHERE user_id=?", (user_id,))
    conn.execute(
        "INSERT INTO password_resets (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at),
    )
    conn.commit()
    conn.close()
    return token


def validate_reset_token(token: str):
    if not token:
        return None
    now_iso = datetime.utcnow().isoformat()
    conn = get_db()
    row = conn.execute(
        "SELECT pr.*, u.email, u.name FROM password_resets pr JOIN users u ON pr.user_id=u.id WHERE pr.token=?",
        (token,),
    ).fetchone()
    conn.close()
    if not row or row["expires_at"] < now_iso:
        return None
    return row


def generate_gift_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "KQ-" + "".join(secrets.choice(alphabet) for _ in range(8))


def get_setting(key: str, default: str = "") -> str:
    conn = get_db()
    row = conn.execute("SELECT value FROM site_settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else default


def slot_taken(conn, employee_id: int, start_at: datetime) -> bool:
    end_at = start_at + timedelta(hours=1)
    overlap = conn.execute(
        """
        SELECT 1 FROM appointments
        WHERE employee_id=? AND datetime(start_time) < datetime(?) AND datetime(start_time, '+1 hour') > datetime(?)
        """,
        (employee_id, end_at.isoformat(), start_at.isoformat()),
    ).fetchone()
    return overlap is not None


def within_time_off(conn, employee_id: int, start_at: datetime) -> bool:
    end_at = start_at + timedelta(hours=1)
    block = conn.execute(
        """
        SELECT 1 FROM time_off
        WHERE employee_id=? AND datetime(start_time) <= datetime(?) AND datetime(end_time) >= datetime(?)
        """,
        (employee_id, start_at.isoformat(), end_at.isoformat()),
    ).fetchone()
    return block is not None


def available_slots_for_employee(conn, employee_id: int, day: date):
    weekday = day.weekday()
    avail_blocks = conn.execute(
        "SELECT * FROM availability WHERE employee_id=? AND weekday=?",
        (employee_id, weekday),
    ).fetchall()
    slots = []
    for block in avail_blocks:
        start_t = datetime.combine(day, datetime.strptime(block["start_time"], "%H:%M").time())
        end_t = datetime.combine(day, datetime.strptime(block["end_time"], "%H:%M").time())
        cursor = start_t
        while cursor + timedelta(minutes=60) <= end_t:
            if not slot_taken(conn, employee_id, cursor) and not within_time_off(conn, employee_id, cursor):
                slots.append(cursor)
            cursor += timedelta(minutes=30)
    return slots


# ---------- Routes ----------


@app.route("/")
def home():
    google_reviews = [
        {
            "author": "Salma A.",
            "rating": 5,
            "text": "Kim made my bridal morning calm and gorgeous. Makeup stayed perfect for 14 hours!",
        },
        {
            "author": "Nadia P.",
            "rating": 5,
            "text": "The only artist I trust for shoots. She understands camera work and skin tones flawlessly.",
        },
        {
            "author": "Farah K.",
            "rating": 5,
            "text": "Booked hair + makeup for my sister’s wedding party. Everyone looked cohesive and felt seen.",
        },
    ]
    live_instagram = fetch_instagram_posts(limit=9)
    fallback_instagram = [
        {
            "image": "https://images.unsplash.com/photo-1509631171560-7e2e4ba0b82b?auto=format&fit=crop&w=600&q=80",
            "caption": "Soft glam with lived-in waves",
        },
        {
            "image": "https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=600&q=80",
            "caption": "Bridal glow with natural lashes",
        },
        {
            "image": "https://images.unsplash.com/photo-1504198453319-5ce911bafcde?auto=format&fit=crop&w=600&q=80",
            "caption": "Reception-ready volume",
        },
    ]
    instagram_posts = live_instagram or fallback_instagram
    return render_template("index.html", google_reviews=google_reviews, instagram_posts=instagram_posts)


@app.route("/services")
def services():
    conn = get_db()
    items = conn.execute("SELECT * FROM services ORDER BY id").fetchall()
    conn.close()
    categories = sorted({(item["category"] or "Uncategorized") for item in items}) if items else []
    return render_template("services.html", services=items, categories=categories, format_currency=format_currency)


@app.route("/book", methods=["GET", "POST"])
def book():
    conn = get_db()
    services = conn.execute("SELECT * FROM services ORDER BY id").fetchall()
    employees = conn.execute("SELECT * FROM users WHERE role IN ('employee','admin')").fetchall()
    selected_service = request.args.get("service_id")
    if services and not selected_service:
        selected_service = str(services[0]["id"])

    if request.method == "POST":
        service_id = int(request.form.get("service_id"))
        employee_id = request.form.get("employee_id")
        employee_id = int(employee_id) if employee_id and employee_id != "any" else None
        date_str = request.form.get("date")
        time_str = request.form.get("time")
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        notes = request.form.get("notes")

        service = conn.execute("SELECT * FROM services WHERE id=?", (service_id,)).fetchone()
        if not service:
            flash("Service not found.", "error")
            conn.close()
            return redirect(url_for("book"))

        appt_datetime = datetime.fromisoformat(f"{date_str}T{time_str}")

        chosen_employee = employee_id
        if not chosen_employee:
            # pick first available
            for emp in employees:
                if appt_datetime in available_slots_for_employee(conn, emp["id"], appt_datetime.date()):
                    chosen_employee = emp["id"]
                    break
        if not chosen_employee:
            flash("No availability for the selected time.", "error")
            conn.close()
            return redirect(url_for("book"))

        if slot_taken(conn, chosen_employee, appt_datetime) or within_time_off(conn, chosen_employee, appt_datetime):
            flash("Selected time is no longer available.", "error")
            conn.close()
            return redirect(url_for("book"))

        client = conn.execute("SELECT * FROM clients WHERE email=?", (email,)).fetchone()
        if not client:
            cur = conn.execute(
                "INSERT INTO clients (name, email, phone, notes) VALUES (?, ?, ?, ?)",
                (name, email, phone, ""),
            )
            client_id = cur.lastrowid
        else:
            client_id = client["id"]

        payment_intent_id, payment_status = create_payment_intent(
            amount_cents=service["deposit_cents"],
            description=f"Deposit for {service['name']}",
            customer_email=email,
        )
        conn.execute(
            "INSERT INTO payments (payment_intent_id, amount_cents, status, client_email, category) VALUES (?, ?, ?, ?, ?)",
            (payment_intent_id, service["deposit_cents"], payment_status, email, "deposit"),
        )
        appt = conn.execute(
            """
            INSERT INTO appointments (client_id, service_id, employee_id, start_time, status, notes, payment_intent_id, payment_status, amount_cents)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                client_id,
                service_id,
                chosen_employee,
                appt_datetime.isoformat(),
                "Booked",
                notes,
                payment_intent_id,
                payment_status,
                service["deposit_cents"],
            ),
        )
        conn.commit()
        appt_id = appt.lastrowid

        email_body = f"<p>Hi {name},</p><p>Your appointment for {service['name']} is confirmed for {appt_datetime.strftime('%B %d, %Y %I:%M %p')}.</p><p>Deposit: {format_currency(service['deposit_cents'])}</p>"
        send_email(email, "Appointment Confirmation", email_body)
        flash("Appointment booked and deposit captured. Confirmation sent via email.", "success")
        conn.close()
        return redirect(url_for("appointment_detail", appointment_id=appt_id))

    conn.close()
    return render_template(
        "book.html",
        services=services,
        employees=employees,
        selected_service=selected_service,
        format_currency=format_currency,
    )


@app.route("/appointment/<int:appointment_id>")
def appointment_detail(appointment_id):
    conn = get_db()
    appt = conn.execute(
        """
        SELECT a.*, s.name as service_name, s.price_cents, s.deposit_cents, u.name as employee_name, c.name as client_name, c.email as client_email
        FROM appointments a
        LEFT JOIN services s ON a.service_id=s.id
        LEFT JOIN users u ON a.employee_id=u.id
        LEFT JOIN clients c ON a.client_id=c.id
        WHERE a.id=?
        """,
        (appointment_id,),
    ).fetchone()
    conn.close()
    if not appt:
        flash("Appointment not found.", "error")
        return redirect(url_for("home"))
    return render_template("appointment_detail.html", appt=appt, format_currency=format_currency)


@app.route("/gift-cards", methods=["GET", "POST"])
def gift_cards():
    if request.method == "POST":
        to_name = request.form.get("to_name")
        from_name = request.form.get("from_name")
        amount = int(float(request.form.get("amount")) * 100)
        message = request.form.get("message")
        email = request.form.get("email")

        code = generate_gift_code()
        payment_intent_id, payment_status = create_payment_intent(amount, "Gift Card", email)
        conn = get_db()
        conn.execute(
            "INSERT INTO gift_cards (code, to_name, from_name, amount_cents, balance_cents, message, email, status, payment_intent_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                code,
                to_name,
                from_name,
                amount,
                amount,
                message,
                email,
                "Active",
                payment_intent_id,
            ),
        )
        conn.execute(
            "INSERT INTO payments (payment_intent_id, amount_cents, status, client_email, category) VALUES (?, ?, ?, ?, ?)",
            (payment_intent_id, amount, payment_status, email, "gift_card"),
        )
        conn.commit()
        conn.close()
        send_email(
            email,
            "Your Kim Quraishi Beauty Studio Gift Card",
            f"<p>Hi {to_name},</p><p>You received a gift card from {from_name} for {format_currency(amount)}.</p><p>Code: <strong>{code}</strong></p><p>Message: {message}</p>",
        )
        flash("Gift card purchased! We emailed the details.", "success")
        return redirect(url_for("gift_cards"))
    return render_template("gift_cards.html", format_currency=format_currency)


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")
        send_email("kim@studio.com", f"New inquiry from {name}", f"<p>From: {email}</p><p>{message}</p>")
        flash("Thanks for reaching out. We'll respond shortly.", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        action = request.form.get("action", "login")
        email = request.form.get("email")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if action == "send_link":
            if not user:
                flash("No account found for that email.", "error")
                return redirect(url_for("login"))
            token = issue_reset_token(user["id"])
            reset_link = url_for("reset_password", token=token, _external=True)
            send_email(
                email,
                "Reset your Kim Quraishi password",
                f"<p>Click below to reset your password:</p><p><a href='{reset_link}'>{reset_link}</a></p>",
            )
            flash("Reset link sent. Check your email (and spam).", "success")
            return redirect(url_for("login"))
        password = request.form.get("password")
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Welcome back!", "success")
            if user["role"] == "admin":
                return redirect(url_for("admin"))
            if user["role"] == "employee":
                return redirect(url_for("employee_dashboard"))
            return redirect(url_for("home"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if not user:
            flash("We couldn't find that email.", "error")
            return redirect(url_for("forgot_password"))
        token = issue_reset_token(user["id"])
        reset_link = url_for("reset_password", token=token, _external=True)
        send_email(
            email,
            "Reset your Kim Quraishi password",
            f"<p>Hi {user['name']},</p><p>Reset your password here: <a href='{reset_link}'>{reset_link}</a></p>",
        )
        flash("Password reset link sent. Please check your inbox.", "success")
        return redirect(url_for("login"))
    return render_template("forgot_password.html")


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    row = validate_reset_token(token)
    if not row:
        flash("Reset link is invalid or expired.", "error")
        return redirect(url_for("login"))
    if request.method == "POST":
        new_password = request.form.get("password")
        conn = get_db()
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (generate_password_hash(new_password), row["user_id"]),
        )
        conn.execute("DELETE FROM password_resets WHERE user_id=?", (row["user_id"],))
        conn.commit()
        conn.close()
        flash("Password updated. You can log in now.", "success")
        return redirect(url_for("login"))
    return render_template("reset_password.html", token=token, email=row["email"])


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        password = request.form.get("password")
        conn = get_db()
        existing = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            flash("Account already exists.", "error")
            conn.close()
            return redirect(url_for("signup"))
        cur = conn.execute(
            "INSERT INTO users (name, email, phone, role, password_hash) VALUES (?, ?, ?, 'client', ?)",
            (name, email, phone, generate_password_hash(password)),
        )
        conn.execute(
            "INSERT INTO clients (name, email, phone, notes) VALUES (?, ?, ?, '')",
            (name, email, phone),
        )
        conn.commit()
        session["user_id"] = cur.lastrowid
        conn.close()
        flash("Account created.", "success")
        return redirect(url_for("home"))
    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("home"))


@app.route("/billing")
def billing():
    user = current_user()
    if not user:
        flash("Login to see your billing history.", "error")
        return redirect(url_for("login"))
    conn = get_db()
    payments = conn.execute(
        "SELECT * FROM payments WHERE client_email=? ORDER BY datetime(created_at) DESC",
        (user["email"],),
    ).fetchall()
    appointments = conn.execute(
        """
        SELECT a.*, s.name as service_name
        FROM appointments a
        LEFT JOIN services s ON a.service_id=s.id
        LEFT JOIN clients c ON a.client_id=c.id
        WHERE c.email=?
        ORDER BY datetime(a.start_time) DESC
        """,
        (user["email"],),
    ).fetchall()
    conn.close()
    return render_template("billing.html", payments=payments, appointments=appointments, format_currency=format_currency)


@app.route("/admin", methods=["GET", "POST"])
def admin():
    user = current_user()
    if not user or user["role"] != "admin":
        flash("Admin access only.", "error")
        return redirect(url_for("login"))
    conn = get_db()
    employees = conn.execute("SELECT * FROM users WHERE role IN ('employee','admin')").fetchall()
    services = conn.execute("SELECT * FROM services").fetchall()
    categories = sorted({(svc["category"] or "Uncategorized") for svc in services}) if services else []
    appointments = conn.execute(
        "SELECT a.*, s.name as service_name, s.deposit_cents, u.name as employee_name, c.name as client_name FROM appointments a LEFT JOIN services s ON a.service_id=s.id LEFT JOIN users u ON a.employee_id=u.id LEFT JOIN clients c ON a.client_id=c.id ORDER BY datetime(start_time) DESC LIMIT 20",
    ).fetchall()
    gift_cards = conn.execute("SELECT * FROM gift_cards ORDER BY created_at DESC LIMIT 20").fetchall()
    clients = conn.execute("SELECT * FROM clients ORDER BY datetime(created_at) DESC LIMIT 50").fetchall()
    earnings = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) as total, COUNT(*) as count FROM payments",
    ).fetchone()
    upcoming_count = conn.execute(
        "SELECT COUNT(*) as c FROM appointments WHERE datetime(start_time) >= datetime('now')",
    ).fetchone()["c"]
    conn.close()
    log_metrics = summarize_logs()
    return render_template(
        "admin.html",
        employees=employees,
        services=services,
        categories=categories,
        appointments=appointments,
        gift_cards=gift_cards,
        clients=clients,
        format_currency=format_currency,
        announcement=get_setting("announcement", ""),
        earnings=earnings,
        upcoming_count=upcoming_count,
        log_metrics=log_metrics,
    )

# @app.route("/admin/announcement", methods=["POST"])
# def update_announcement():
#     if not require_role("admin"):
#         return redirect(url_for("login"))
#     message = request.form.get("announcement", "").strip()
#     conn = get_db()
#     conn.execute(
#         "INSERT INTO site_settings (key, value, updated_at) VALUES ('announcement', ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
#         (message,),
#     )
#     conn.commit()
#     conn.close()
#     flash("Announcement updated.", "success")
#     return redirect(url_for("admin"))


@app.route("/admin/announcement", methods=["POST"])
def update_announcement():
    if not require_role("admin"):
        return redirect(url_for("login"))
    message = request.form.get("announcement", "").strip()
    conn = get_db()
    conn.execute(
        "INSERT INTO site_settings (key, value, updated_at) VALUES ('announcement', ?, CURRENT_TIMESTAMP) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
        (message,),
    )
    conn.commit()
    conn.close()
    flash("Announcement updated.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/add_service", methods=["POST"])
def add_service():
    if not require_role("admin"):
        return redirect(url_for("login"))
    name = request.form.get("name")
    description = request.form.get("description")
    price = int(float(request.form.get("price")) * 100)
    deposit = int(float(request.form.get("deposit")) * 100)
    category = request.form.get("category")
    calendar_color = request.form.get("calendar_color")
    duration = int(request.form.get("duration") or 60)
    processing = int(request.form.get("processing_minutes") or 0)
    block_minutes = int(request.form.get("block_minutes") or 0)
    require_deposit = 1 if request.form.get("require_deposit") == "on" else 0
    image_url = request.form.get("image_url")
    uploaded = save_uploaded_image(request.files.get("image_file"))
    if uploaded:
        image_url = uploaded
    conn = get_db()
    conn.execute(
        """
        INSERT INTO services (name, description, price_cents, deposit_cents, image_url, category, calendar_color, duration_minutes, processing_minutes, block_minutes, require_deposit)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            description,
            price,
            deposit,
            image_url,
            category,
            calendar_color,
            duration,
            processing,
            block_minutes,
            require_deposit,
        ),
    )
    conn.commit()
    conn.close()
    flash("Service added.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/services/<int:service_id>/delete", methods=["POST"])
def delete_service(service_id):
    if not require_role("admin"):
        return redirect(url_for("login"))
    conn = get_db()
    conn.execute("DELETE FROM appointments WHERE service_id=?", (service_id,))
    conn.execute("DELETE FROM services WHERE id=?", (service_id,))
    conn.commit()
    conn.close()
    flash("Service removed.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/add_employee", methods=["POST"])
def add_employee():
    if not require_role("admin"):
        return redirect(url_for("login"))
    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")
    title = request.form.get("title")
    password = request.form.get("password") or "welcome123"
    conn = get_db()
    conn.execute(
        "INSERT INTO users (name, email, phone, role, password_hash) VALUES (?, ?, ?, 'employee', ?)",
        (name, email, phone, generate_password_hash(password)),
    )
    conn.commit()
    conn.close()
    flash(f"Employee {name} added.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/service/<int:service_id>/pricing", methods=["POST"])
def update_service_pricing(service_id):
    if not require_role("admin"):
        return redirect(url_for("login"))
    price = int(float(request.form.get("price")) * 100)
    deposit = int(float(request.form.get("deposit")) * 100)
    description = request.form.get("description")
    image_url = request.form.get("image_url")
    category = request.form.get("category")
    calendar_color = request.form.get("calendar_color")
    duration = int(request.form.get("duration") or 60)
    processing = int(request.form.get("processing_minutes") or 0)
    block_minutes = int(request.form.get("block_minutes") or 0)
    require_deposit = 1 if request.form.get("require_deposit") == "on" else 0
    uploaded = save_uploaded_image(request.files.get("image_file"))
    if uploaded:
        image_url = uploaded
    conn = get_db()
    conn.execute(
        """
        UPDATE services
        SET price_cents=?, deposit_cents=?, description=?, image_url=?, category=?, calendar_color=?, duration_minutes=?, processing_minutes=?, block_minutes=?, require_deposit=?
        WHERE id=?
        """,
        (
            price,
            deposit,
            description,
            image_url,
            category,
            calendar_color,
            duration,
            processing,
            block_minutes,
            require_deposit,
            service_id,
        ),
    )
    conn.commit()
    conn.close()
    flash("Service pricing updated.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/appointments/<int:appointment_id>/update", methods=["POST"])
def update_appointment(appointment_id):
    if not require_role("admin"):
        return redirect(url_for("login"))
    flash("Rescheduling and cancelling are unavailable via dashboard. Please handle directly with the client.", "error")
    return redirect(url_for("admin"))


@app.route("/admin/availability", methods=["POST"])
def admin_availability():
    if not require_role("admin"):
        return redirect(url_for("login"))
    employee_id = int(request.form.get("employee_id"))
    weekday = int(request.form.get("weekday"))
    start_time_str = request.form.get("start_time")
    end_time_str = request.form.get("end_time")
    conn = get_db()
    conn.execute(
        "INSERT INTO availability (employee_id, weekday, start_time, end_time) VALUES (?, ?, ?, ?)",
        (employee_id, weekday, start_time_str, end_time_str),
    )
    conn.commit()
    conn.close()
    flash("Availability saved.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/time_off", methods=["POST"])
def admin_time_off():
    if not require_role("admin"):
        return redirect(url_for("login"))
    employee_id = int(request.form.get("employee_id"))
    start_time_str = request.form.get("start_time")
    end_time_str = request.form.get("end_time")
    reason = request.form.get("reason")
    conn = get_db()
    conn.execute(
        "INSERT INTO time_off (employee_id, start_time, end_time, reason) VALUES (?, ?, ?, ?)",
        (employee_id, start_time_str, end_time_str, reason),
    )
    conn.commit()
    conn.close()
    flash("Time off added.", "success")
    return redirect(url_for("admin"))


@app.route("/dashboard")
def employee_dashboard():
    user = current_user()
    if not user or user["role"] not in {"employee", "admin"}:
        flash("Employee access only.", "error")
        return redirect(url_for("login"))
    conn = get_db()
    today = date.today()
    upcoming = conn.execute(
        """
        SELECT a.*, s.name as service_name, c.name as client_name, c.phone as client_phone
        FROM appointments a
        LEFT JOIN services s ON a.service_id=s.id
        LEFT JOIN clients c ON a.client_id=c.id
        WHERE a.employee_id=? AND datetime(start_time) >= datetime(?)
        ORDER BY datetime(start_time)
        """,
        (user["id"], today.isoformat()),
    ).fetchall()
    conn.close()
    return render_template("dashboard.html", appointments=upcoming)


@app.route("/clients/<int:client_id>")
def client_profile(client_id):
    user = current_user()
    if not user or user["role"] not in {"employee", "admin"}:
        flash("Restricted.", "error")
        return redirect(url_for("login"))
    conn = get_db()
    client = conn.execute("SELECT * FROM clients WHERE id=?", (client_id,)).fetchone()
    visits = conn.execute(
        "SELECT a.*, s.name as service_name FROM appointments a LEFT JOIN services s ON a.service_id=s.id WHERE client_id=? ORDER BY datetime(start_time) DESC",
        (client_id,),
    ).fetchall()
    notes = conn.execute("SELECT n.*, u.name as author_name FROM client_notes n LEFT JOIN users u ON n.author_id=u.id WHERE client_id=? ORDER BY datetime(n.created_at) DESC", (client_id,)).fetchall()
    photos = conn.execute("SELECT * FROM client_photos WHERE client_id=? ORDER BY created_at DESC", (client_id,)).fetchall()
    conn.close()
    return render_template(
        "client_profile.html", client=client, visits=visits, notes=notes, photos=photos
    )


@app.route("/clients/<int:client_id>/notes", methods=["POST"])
def add_client_note(client_id):
    if not current_user():
        return redirect(url_for("login"))
    note = request.form.get("note")
    conn = get_db()
    conn.execute(
        "INSERT INTO client_notes (client_id, author_id, note) VALUES (?, ?, ?)",
        (client_id, current_user()["id"], note),
    )
    conn.commit()
    conn.close()
    flash("Note added.", "success")
    return redirect(url_for("client_profile", client_id=client_id))


@app.route("/api/availability")
def api_availability():
    date_str = request.args.get("date")
    employee_id = request.args.get("employee_id")
    if not date_str:
        return jsonify([])
    day = datetime.fromisoformat(date_str).date()
    conn = get_db()
    employees = conn.execute("SELECT * FROM users WHERE role IN ('employee','admin')").fetchall()
    results = []
    for emp in employees:
        if employee_id and employee_id != "any" and int(employee_id) != emp["id"]:
            continue
        slots = available_slots_for_employee(conn, emp["id"], day)
        results.append(
            {
                "employee_id": emp["id"],
                "employee_name": emp["name"],
                "slots": [
                    {"value": s.strftime("%H:%M"), "label": s.strftime("%I:%M %p")}
                    for s in slots
                ],
            }
        )
    conn.close()
    return jsonify(results)


@app.context_processor
def inject_user():
    return {
        "current_user": current_user(),
        "now": datetime.now,
        "announcement": get_setting("announcement", ""),
    }


init_db()


if __name__ == "__main__":
    app.run(debug=True)
