"""SQLite data layer for the Pistachio & Plum cafe site.

Uses only the standard library so the project runs with Flask alone.
"""

import os
import sqlite3
from datetime import datetime

from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "cafe.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS admin_user (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS category (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL UNIQUE,
    blurb    TEXT DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS menu_item (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    description TEXT DEFAULT '',
    price       REAL NOT NULL,
    category_id INTEGER NOT NULL REFERENCES category(id) ON DELETE CASCADE,
    image_url   TEXT DEFAULT '',
    is_special  INTEGER NOT NULL DEFAULT 0,
    available   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS "order" (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    reference    TEXT NOT NULL UNIQUE,
    customer     TEXT NOT NULL,
    phone        TEXT NOT NULL,
    note         TEXT DEFAULT '',
    fulfilment   TEXT NOT NULL DEFAULT 'pickup',
    total        REAL NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'new',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_line (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id  INTEGER NOT NULL REFERENCES "order"(id) ON DELETE CASCADE,
    item_id   INTEGER REFERENCES menu_item(id) ON DELETE SET NULL,
    item_name TEXT NOT NULL,
    unit_price REAL NOT NULL,
    quantity  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS reservation (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    phone      TEXT NOT NULL,
    email      TEXT DEFAULT '',
    date       TEXT NOT NULL,
    time       TEXT NOT NULL,
    guests     INTEGER NOT NULL,
    note       TEXT DEFAULT '',
    status     TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS message (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    subject    TEXT DEFAULT '',
    body       TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
"""


def get_db():
    """Open a connection with row access by column name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query(sql, args=(), one=False):
    conn = get_db()
    try:
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    conn = get_db()
    try:
        cur = conn.execute(sql, args)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def now():
    return datetime.utcnow().isoformat(timespec="seconds")


def init_db(admin_user="admin", admin_password="cafe123"):
    """Create tables and, on a fresh database, load the starter menu."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    try:
        conn.executescript(SCHEMA)
        conn.commit()

        existing = conn.execute("SELECT COUNT(*) AS c FROM admin_user").fetchone()["c"]
        if not existing:
            conn.execute(
                "INSERT INTO admin_user (username, password_hash, created_at) VALUES (?,?,?)",
                (admin_user, generate_password_hash(admin_password), now()),
            )
            conn.commit()

        seeded = conn.execute("SELECT COUNT(*) AS c FROM category").fetchone()["c"]
        if not seeded:
            _seed(conn)
    finally:
        conn.close()


def _seed(conn):
    categories = [
        ("Brew bar", "Single origin, ground to order, poured slow.", 1),
        ("Milk & espresso", "Our house blend with milk, done properly.", 2),
        ("Bakes", "Out of the oven at 7am, gone by four.", 3),
        ("Plates", "Small kitchen, short menu, everything made here.", 4),
    ]
    conn.executemany(
        "INSERT INTO category (name, blurb, position) VALUES (?,?,?)", categories
    )

    ids = {
        row["name"]: row["id"]
        for row in conn.execute("SELECT id, name FROM category").fetchall()
    }

    items = [
        ("Ethiopia Guji pour-over", "Jasmine, ripe peach, a long clean finish.", 320, "Brew bar", 1),
        ("Cold brew, 18 hours", "Steeped overnight, served over a single big cube.", 280, "Brew bar", 0),
        ("South Indian filter coffee", "Chicory blend, pulled between two steel tumblers.", 160, "Brew bar", 1),
        ("Cortado", "Two ristretto shots, cut with warm milk.", 210, "Milk & espresso", 0),
        ("Pistachio latte", "House pistachio paste, no syrup, lightly salted.", 290, "Milk & espresso", 1),
        ("Cardamom cappuccino", "Green cardamom ground into the shot.", 250, "Milk & espresso", 0),
        ("Plum and almond galette", "Seasonal plums, rough puff, flaked almonds.", 240, "Bakes", 1),
        ("Sourdough croissant", "Three days of folding, two minutes of eating.", 180, "Bakes", 0),
        ("Dark chocolate rye cookie", "Rye flour, 70% chocolate, sea salt.", 150, "Bakes", 0),
        ("Baked eggs, harissa butter", "Two eggs, tomato, feta, sourdough soldiers.", 420, "Plates", 1),
        ("Mushroom toast", "Butter-roasted mushrooms, thyme, parmesan.", 380, "Plates", 0),
        ("Banana bread, brown butter", "Toasted on the flat top, with cultured cream.", 260, "Plates", 0),
    ]
    conn.executemany(
        """INSERT INTO menu_item
           (name, description, price, category_id, image_url, is_special, available, created_at)
           VALUES (?,?,?,?,'',?,1,?)""",
        [(n, d, p, ids[c], s, now()) for n, d, p, c, s in items],
    )

    from datetime import date, timedelta

    today = date.today()
    conn.executemany(
        """INSERT INTO reservation (name, phone, email, date, time, guests, note, status, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        [
            ("Ira Menon", "9812345670", "ira@example.com",
             (today + timedelta(days=1)).isoformat(), "09:30", 2,
             "Window seat if free", "pending", now()),
            ("Dev Anand", "9812345671", "dev@example.com",
             (today + timedelta(days=3)).isoformat(), "18:00", 5,
             "Birthday, bringing a cake", "confirmed", now()),
        ],
    )
    conn.commit()
    _seed_orders(conn, today)


def _seed_orders(conn, today):
    """A week of sample tickets so the dashboard is not blank on first run."""
    from datetime import timedelta

    menu = {row["name"]: row for row in conn.execute("SELECT * FROM menu_item").fetchall()}
    samples = [
        (6, "Ira Menon", "9810000001", "pickup", "collected", [("Cortado", 2), ("Sourdough croissant", 1)]),
        (5, "Dev Anand", "9810000002", "dine-in", "collected", [("Baked eggs, harissa butter", 2), ("Cold brew, 18 hours", 2)]),
        (4, "Sana Qureshi", "9810000003", "pickup", "collected", [("Pistachio latte", 1), ("Dark chocolate rye cookie", 2)]),
        (3, "Tarun Rao", "9810000004", "dine-in", "collected", [("South Indian filter coffee", 3), ("Banana bread, brown butter", 1)]),
        (2, "Meera Iyer", "9810000005", "pickup", "collected", [("Ethiopia Guji pour-over", 1), ("Plum and almond galette", 2)]),
        (1, "Joseph Mathew", "9810000006", "dine-in", "collected", [("Cardamom cappuccino", 2), ("Mushroom toast", 1)]),
        (0, "Aarav Shah", "9810000007", "pickup", "preparing", [("Pistachio latte", 2), ("Sourdough croissant", 2)]),
        (0, "Leah Fernandes", "9810000008", "dine-in", "new", [("Cortado", 1), ("Plum and almond galette", 1)]),
    ]

    for index, (days_ago, customer, phone, fulfilment, status, lines) in enumerate(samples, start=1):
        stamp = (datetime.combine(today - timedelta(days=days_ago), datetime.min.time())
                 .replace(hour=9 + index % 8, minute=15)).isoformat(timespec="seconds")
        total = sum(menu[name]["price"] * qty for name, qty in lines)
        cur = conn.execute(
            """INSERT INTO "order" (reference, customer, phone, note, fulfilment, total, status, created_at)
               VALUES (?,?,?,'',?,?,?,?)""",
            (f"PP-S{index:04d}", customer, phone, fulfilment, total, status, stamp),
        )
        for name, qty in lines:
            item = menu[name]
            conn.execute(
                """INSERT INTO order_line (order_id, item_id, item_name, unit_price, quantity)
                   VALUES (?,?,?,?,?)""",
                (cur.lastrowid, item["id"], item["name"], item["price"], qty),
            )
    conn.commit()
