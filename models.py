import sqlite3
import os
import csv
import uuid
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'database.db'
CSV_FILE_PATH = BASE_DIR / 'data.csv'


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL DEFAULT '',
            contact TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL DEFAULT 'manager',
            status TEXT NOT NULL DEFAULT 'pending',
            commission_rate REAL NOT NULL DEFAULT 15.0,
            referred_by TEXT DEFAULT NULL,
            last_lead_claimed_at TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS leads (
            id TEXT PRIMARY KEY,
            source TEXT DEFAULT '',
            name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            has_website TEXT DEFAULT '0',
            website_url TEXT DEFAULT '',
            yandex_url TEXT DEFAULT '',
            rating TEXT DEFAULT '',
            reviews_count TEXT DEFAULT '',
            address TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'free',
            assigned_to INTEGER DEFAULT NULL,
            assigned_at TIMESTAMP DEFAULT NULL,
            deal_amount REAL DEFAULT NULL,
            target_result TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (assigned_to) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS deals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id TEXT NOT NULL,
            manager_id INTEGER NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            commission_rate REAL NOT NULL DEFAULT 15.0,
            commission_amount REAL NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES leads(id),
            FOREIGN KEY (manager_id) REFERENCES users(id)
        );
    ''')
    try:
        conn.execute("ALTER TABLE users ADD COLUMN last_lead_claimed_at TIMESTAMP DEFAULT NULL")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def create_admin(username, password):
    """Create admin account if it does not exist yet."""
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not existing:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, role, status, commission_rate) "
            "VALUES (?, ?, ?, 'admin', 'approved', 100.0)",
            (username, generate_password_hash(password), 'Администратор')
        )
        conn.commit()
    conn.close()


def clean_phone_number(phone):
    if not phone:
        return ""
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    return digits


def import_leads_csv(csv_content):
    """
    Import new parsed leads from CSV string, skipping any duplicate leads
    (by normalized phone, yandex_url, or lead ID).
    Returns (added_count, skipped_count, total_count).
    """
    if not csv_content or not csv_content.strip():
        return 0, 0, 0

    conn = get_db()
    existing_rows = conn.execute("SELECT id, phone, yandex_url FROM leads").fetchall()
    existing_ids = set()
    existing_urls = set()
    existing_phones = set()

    for r in existing_rows:
        if r['id']:
            existing_ids.add(r['id'])
        if r['yandex_url'] and r['yandex_url'].strip():
            existing_urls.add(r['yandex_url'].strip())
        cp = clean_phone_number(r['phone'])
        if cp:
            existing_phones.add(cp)

    sample = csv_content[:2000]
    delimiter = ';' if ';' in sample else ','

    lines = [line for line in csv_content.strip().splitlines() if line.strip()]
    if not lines:
        conn.close()
        return 0, 0, 0

    reader = csv.DictReader(lines, delimiter=delimiter)

    added = 0
    skipped = 0
    total = 0

    for row in reader:
        total += 1
        lead_id = (row.get('id') or '').strip()
        if not lead_id:
            lead_id = str(uuid.uuid4())

        source = (row.get('source') or 'yandex').strip()
        name = (row.get('name') or '').strip()
        phone = (row.get('phone') or '').strip()
        has_website = (row.get('has_website') or '0').strip()
        website_url = (row.get('website_url') or '').strip()
        yandex_url = (row.get('yandex_url') or '').strip()
        rating = (row.get('rating') or '').strip()
        reviews_count = (row.get('reviews_count') or '').strip()
        address = (row.get('address') or '').strip()
        target_result = (row.get('target_result') or '').strip()

        cp = clean_phone_number(phone)

        if (cp and cp in existing_phones) or (yandex_url and yandex_url in existing_urls) or (lead_id in existing_ids):
            skipped += 1
            continue

        conn.execute(
            """INSERT INTO leads
               (id, source, name, phone, has_website, website_url, yandex_url,
                rating, reviews_count, address, target_result, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'free')""",
            (lead_id, source, name, phone, has_website, website_url, yandex_url,
             rating, reviews_count, address, target_result)
        )

        existing_ids.add(lead_id)
        if yandex_url:
            existing_urls.add(yandex_url)
        if cp:
            existing_phones.add(cp)
        added += 1

    conn.commit()
    conn.close()

    return added, skipped, total


def migrate_csv_to_db():
    """Import leads from data.csv into SQLite if data.csv exists."""
    if not os.path.exists(CSV_FILE_PATH):
        return
    try:
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8-sig') as f:
            content = f.read()
            import_leads_csv(content)
    except Exception as e:
        print("Error importing data.csv:", e)


# ── User helpers ─────────────────────────────────────────────────

def get_user_by_id(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return user


def get_user_by_username(username):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return user


def create_user(username, password, display_name, contact, referred_by=None):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, password_hash, display_name, contact, referred_by) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, generate_password_hash(password), display_name, contact, referred_by)
        )
        conn.commit()
        conn.close()
        return True, "OK"
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Пользователь с таким логином уже существует"


def get_all_users():
    conn = get_db()
    users = conn.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    return users


def update_user_status(user_id, status):
    conn = get_db()
    conn.execute("UPDATE users SET status = ? WHERE id = ?", (status, user_id))
    conn.commit()
    conn.close()


def update_user_commission(user_id, rate):
    conn = get_db()
    conn.execute("UPDATE users SET commission_rate = ? WHERE id = ?", (rate, user_id))
    conn.commit()
    conn.close()


# ── Lead helpers ─────────────────────────────────────────────────

def get_free_leads():
    conn = get_db()
    leads = conn.execute(
        "SELECT * FROM leads WHERE status = 'free' AND phone != '' ORDER BY name"
    ).fetchall()
    conn.close()
    return leads


def get_leads_by_manager(manager_id):
    conn = get_db()
    leads = conn.execute(
        "SELECT * FROM leads WHERE assigned_to = ? AND status != 'free' "
        "ORDER BY assigned_at DESC",
        (manager_id,)
    ).fetchall()
    conn.close()
    return leads


def get_all_leads():
    conn = get_db()
    leads = conn.execute("""
        SELECT l.*, u.display_name AS manager_name, u.username AS manager_username
        FROM leads l
        LEFT JOIN users u ON l.assigned_to = u.id
        ORDER BY CASE WHEN l.status = 'free' THEN 0 ELSE 1 END, l.assigned_at DESC
    """).fetchall()
    conn.close()
    return leads


def get_user_cooldown(user_id, cooldown_seconds=60):
    """Returns remaining cooldown seconds for a user (0 if ready)."""
    conn = get_db()
    user = conn.execute("SELECT last_lead_claimed_at FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if not user or not user['last_lead_claimed_at']:
        return 0
    try:
        val = user['last_lead_claimed_at']
        if isinstance(val, str):
            last_time = datetime.fromisoformat(val)
        else:
            return 0
        elapsed = (datetime.now() - last_time).total_seconds()
        remaining = cooldown_seconds - elapsed
        return max(0, int(remaining))
    except Exception:
        return 0


def claim_lead(lead_id, manager_id):
    """Atomically claim a free lead for the given manager (taxi-style). 1-min cooldown."""
    conn = get_db()
    cooldown = get_user_cooldown(manager_id, 60)
    if cooldown > 0:
        conn.close()
        return False, f"Перезарядка! Подождите {cooldown} сек. перед взятием следующего клиента."

    lead = conn.execute("SELECT status FROM leads WHERE id = ?", (lead_id,)).fetchone()
    if not lead or lead['status'] != 'free':
        conn.close()
        return False, "Клиент уже занят другим менеджером"

    now_iso = datetime.now().isoformat()
    conn.execute(
        "UPDATE leads SET status = 'taken', assigned_to = ?, assigned_at = ? "
        "WHERE id = ? AND status = 'free'",
        (manager_id, now_iso, lead_id)
    )
    conn.execute("UPDATE users SET last_lead_claimed_at = ? WHERE id = ?", (now_iso, manager_id))
    conn.commit()
    updated = conn.execute("SELECT assigned_to FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    if updated and updated['assigned_to'] == manager_id:
        return True, "OK"
    return False, "Клиент уже занят"


def release_lead(lead_id, manager_id=None, is_admin=False):
    conn = get_db()
    now_iso = datetime.now().isoformat()
    if is_admin:
        conn.execute(
            "UPDATE leads SET status = 'free', assigned_to = NULL, assigned_at = NULL WHERE id = ?",
            (lead_id,)
        )
    else:
        conn.execute(
            "UPDATE leads SET status = 'free', assigned_to = NULL, assigned_at = NULL "
            "WHERE id = ? AND assigned_to = ?",
            (lead_id, manager_id)
        )
        if manager_id:
            conn.execute("UPDATE users SET last_lead_claimed_at = ? WHERE id = ?", (now_iso, manager_id))
    conn.commit()
    conn.close()


def update_lead_status(lead_id, new_status, manager_id=None, is_admin=False):
    conn = get_db()
    if is_admin:
        conn.execute("UPDATE leads SET status = ? WHERE id = ?", (new_status, lead_id))
    else:
        conn.execute(
            "UPDATE leads SET status = ? WHERE id = ? AND assigned_to = ?",
            (new_status, lead_id, manager_id)
        )
        if manager_id and new_status == 'refused':
            conn.execute("UPDATE users SET last_lead_claimed_at = ? WHERE id = ?", (datetime.now().isoformat(), manager_id))
    conn.commit()
    conn.close()


def reassign_lead(lead_id, new_manager_id):
    conn = get_db()
    conn.execute(
        "UPDATE leads SET assigned_to = ?, assigned_at = ?, status = 'taken' WHERE id = ?",
        (new_manager_id, datetime.now().isoformat(), lead_id)
    )
    conn.commit()
    conn.close()


# ── Deal helpers ─────────────────────────────────────────────────

def create_deal(lead_id, manager_id, amount):
    conn = get_db()
    user = conn.execute("SELECT commission_rate FROM users WHERE id = ?", (manager_id,)).fetchone()
    rate = user['commission_rate'] if user else 15.0
    commission = round(amount * rate / 100.0, 2)
    now_iso = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO deals (lead_id, manager_id, amount, commission_rate, commission_amount) "
        "VALUES (?, ?, ?, ?, ?)",
        (lead_id, manager_id, amount, rate, commission)
    )
    conn.execute("UPDATE leads SET status = 'deal', deal_amount = ? WHERE id = ?", (amount, lead_id))
    conn.execute("UPDATE users SET last_lead_claimed_at = ? WHERE id = ?", (now_iso, manager_id))
    conn.commit()
    conn.close()
    return commission


def get_deals_by_manager(manager_id):
    conn = get_db()
    deals = conn.execute("""
        SELECT d.*, l.name AS lead_name, l.phone AS lead_phone,
               l.yandex_url AS lead_yandex_url, l.website_url AS lead_website_url
        FROM deals d JOIN leads l ON d.lead_id = l.id
        WHERE d.manager_id = ?
        ORDER BY d.created_at DESC
    """, (manager_id,)).fetchall()
    conn.close()
    return deals


def get_all_deals():
    conn = get_db()
    deals = conn.execute("""
        SELECT d.*, l.name AS lead_name, l.phone AS lead_phone,
               l.yandex_url AS lead_yandex_url, l.website_url AS lead_website_url,
               u.display_name AS manager_name, u.username AS manager_username
        FROM deals d
        JOIN leads l ON d.lead_id = l.id
        JOIN users u ON d.manager_id = u.id
        ORDER BY d.created_at DESC
    """).fetchall()
    conn.close()
    return deals


# ── Stats helpers ────────────────────────────────────────────────

def get_manager_stats(manager_id):
    conn = get_db()
    s = {}
    s['total_leads'] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE assigned_to = ?", (manager_id,)
    ).fetchone()[0]
    s['active_leads'] = conn.execute(
        "SELECT COUNT(*) FROM leads WHERE assigned_to = ? AND status IN ('taken','in_progress','callback')",
        (manager_id,)
    ).fetchone()[0]
    s['deals_count'] = conn.execute(
        "SELECT COUNT(*) FROM deals WHERE manager_id = ?", (manager_id,)
    ).fetchone()[0]
    row = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS ta, COALESCE(SUM(commission_amount),0) AS tc "
        "FROM deals WHERE manager_id = ?", (manager_id,)
    ).fetchone()
    s['total_amount'] = row['ta']
    s['total_commission'] = row['tc']
    conn.close()
    return s


def get_admin_stats():
    conn = get_db()
    s = {}
    s['total_leads'] = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    s['free_leads'] = conn.execute("SELECT COUNT(*) FROM leads WHERE status = 'free'").fetchone()[0]
    s['taken_leads'] = conn.execute("SELECT COUNT(*) FROM leads WHERE status != 'free'").fetchone()[0]
    s['total_users'] = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'manager'").fetchone()[0]
    s['pending_users'] = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
    s['approved_users'] = conn.execute(
        "SELECT COUNT(*) FROM users WHERE status = 'approved' AND role = 'manager'"
    ).fetchone()[0]
    row = conn.execute(
        "SELECT COALESCE(SUM(amount),0) AS ta, COALESCE(SUM(commission_amount),0) AS tc FROM deals"
    ).fetchone()
    s['total_deals_amount'] = row['ta']
    s['total_commission'] = row['tc']
    s['deals_count'] = conn.execute("SELECT COUNT(*) FROM deals").fetchone()[0]
    conn.close()
    return s
