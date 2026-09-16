"""Pistachio & Plum — cafe website with an admin dashboard.

Run:
    pip install -r requirements.txt
    python app.py
Then open http://127.0.0.1:5000  (admin at /admin, login admin / cafe123)
"""

import os
import secrets
from datetime import date, datetime, timedelta
from functools import wraps

from flask import (
    Flask, abort, flash, jsonify, redirect, render_template,
    request, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import db

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")

CAFE = {
    "name": "Pistachio & Plum",
    "tagline": "A small roastery and bakehouse.",
    "address": "14 Ashwood Lane, Sector 29",
    "phone": "+91 98100 00000",
    "email": "hello@pistachioandplum.cafe",
    "hours": [
        ("Monday to Friday", "7:00 — 19:00"),
        ("Saturday", "8:00 — 21:00"),
        ("Sunday", "8:00 — 16:00"),
    ],
}

ORDER_STATUSES = ["new", "preparing", "ready", "collected", "cancelled"]
RESERVATION_STATUSES = ["pending", "confirmed", "seated", "cancelled"]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

@app.context_processor
def inject_globals():
    return {"cafe": CAFE, "year": date.today().year}


@app.template_filter("money")
def money(value):
    return f"\u20b9{value:,.0f}"


@app.template_filter("nicedate")
def nicedate(value):
    if not value:
        return ""
    try:
        return datetime.fromisoformat(value).strftime("%d %b, %H:%M")
    except ValueError:
        return value


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            flash("Sign in to reach the dashboard.", "warn")
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def categories():
    return db.query("SELECT * FROM category ORDER BY position, name")


def unread_count():
    row = db.query("SELECT COUNT(*) AS c FROM message WHERE is_read = 0", one=True)
    return row["c"] if row else 0


# --------------------------------------------------------------------------
# public site
# --------------------------------------------------------------------------

@app.route("/")
def home():
    specials = db.query(
        """SELECT m.*, c.name AS category FROM menu_item m
           JOIN category c ON c.id = m.category_id
           WHERE m.is_special = 1 AND m.available = 1
           ORDER BY m.id LIMIT 4"""
    )
    brew = db.query(
        """SELECT m.* FROM menu_item m JOIN category c ON c.id = m.category_id
           WHERE c.name = 'Brew bar' AND m.available = 1 ORDER BY m.id LIMIT 3"""
    )
    return render_template("index.html", specials=specials, brew=brew)


@app.route("/menu")
def menu():
    active = request.args.get("c", "")
    cats = categories()
    grouped = []
    for cat in cats:
        if active and str(cat["id"]) != active:
            continue
        items = db.query(
            "SELECT * FROM menu_item WHERE category_id = ? ORDER BY available DESC, name",
            (cat["id"],),
        )
        if items:
            grouped.append((cat, items))
    return render_template("menu.html", grouped=grouped, cats=cats, active=active)


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/cart")
def cart():
    return render_template("cart.html")


@app.post("/api/order")
def api_order():
    """Create an order. Prices are always re-read from the database."""
    data = request.get_json(silent=True) or {}
    lines = data.get("items") or []
    customer = (data.get("customer") or "").strip()
    phone = (data.get("phone") or "").strip()

    if not customer or not phone:
        return jsonify(ok=False, error="Add your name and a phone number."), 400
    if not lines:
        return jsonify(ok=False, error="Your basket is empty."), 400

    resolved, total = [], 0.0
    for line in lines:
        try:
            item_id = int(line.get("id"))
            qty = max(1, min(20, int(line.get("qty", 1))))
        except (TypeError, ValueError):
            return jsonify(ok=False, error="That basket could not be read."), 400
        item = db.query(
            "SELECT * FROM menu_item WHERE id = ? AND available = 1", (item_id,), one=True
        )
        if not item:
            return jsonify(ok=False, error="One item is no longer available."), 400
        total += item["price"] * qty
        resolved.append((item, qty))

    reference = "PP-" + secrets.token_hex(3).upper()
    order_id = db.execute(
        """INSERT INTO "order" (reference, customer, phone, note, fulfilment, total, status, created_at)
           VALUES (?,?,?,?,?,?,'new',?)""",
        (
            reference, customer, phone,
            (data.get("note") or "").strip()[:400],
            "dine-in" if data.get("fulfilment") == "dine-in" else "pickup",
            round(total, 2), db.now(),
        ),
    )
    for item, qty in resolved:
        db.execute(
            """INSERT INTO order_line (order_id, item_id, item_name, unit_price, quantity)
               VALUES (?,?,?,?,?)""",
            (order_id, item["id"], item["name"], item["price"], qty),
        )
    return jsonify(ok=True, reference=reference, total=round(total, 2))


@app.route("/reserve", methods=["GET", "POST"])
def reserve():
    if request.method == "POST":
        f = request.form
        name, phone = f.get("name", "").strip(), f.get("phone", "").strip()
        day, time_ = f.get("date", ""), f.get("time", "")
        if not all([name, phone, day, time_]):
            flash("Name, phone, date and time are all needed to hold a table.", "warn")
        else:
            db.execute(
                """INSERT INTO reservation (name, phone, email, date, time, guests, note, status, created_at)
                   VALUES (?,?,?,?,?,?,?,'pending',?)""",
                (
                    name, phone, f.get("email", "").strip(), day, time_,
                    max(1, min(20, int(f.get("guests") or 2))),
                    f.get("note", "").strip()[:400], db.now(),
                ),
            )
            flash(f"Table requested for {name}. We will call to confirm.", "good")
            return redirect(url_for("reserve"))
    return render_template(
        "reserve.html", min_date=date.today().isoformat(),
        max_date=(date.today() + timedelta(days=60)).isoformat(),
    )


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        f = request.form
        if not all([f.get("name"), f.get("email"), f.get("body")]):
            flash("Name, email and a message are needed.", "warn")
        else:
            db.execute(
                "INSERT INTO message (name, email, subject, body, created_at) VALUES (?,?,?,?,?)",
                (
                    f["name"].strip(), f["email"].strip(),
                    f.get("subject", "").strip(), f["body"].strip()[:2000], db.now(),
                ),
            )
            flash("Message sent. We read these every morning.", "good")
            return redirect(url_for("contact"))
    return render_template("contact.html")


# --------------------------------------------------------------------------
# admin: auth
# --------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        user = db.query(
            "SELECT * FROM admin_user WHERE username = ?",
            (request.form.get("username", "").strip(),), one=True,
        )
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session["admin_id"] = user["id"]
            session["admin_name"] = user["username"]
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        flash("That username and password do not match.", "warn")
    return render_template("admin/login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin/password", methods=["POST"])
@login_required
def admin_password():
    current = request.form.get("current", "")
    new = request.form.get("new", "")
    user = db.query("SELECT * FROM admin_user WHERE id = ?", (session["admin_id"],), one=True)
    if not check_password_hash(user["password_hash"], current):
        flash("The current password is wrong.", "warn")
    elif len(new) < 6:
        flash("Use at least six characters.", "warn")
    else:
        db.execute(
            "UPDATE admin_user SET password_hash = ? WHERE id = ?",
            (generate_password_hash(new), user["id"]),
        )
        flash("Password changed.", "good")
    return redirect(url_for("admin_dashboard"))


# --------------------------------------------------------------------------
# admin: dashboard
# --------------------------------------------------------------------------

@app.route("/admin")
@login_required
def admin_dashboard():
    today = date.today().isoformat()
    stats = {
        "orders_today": db.query(
            "SELECT COUNT(*) AS c FROM \"order\" WHERE substr(created_at,1,10) = ?",
            (today,), one=True)["c"],
        "revenue_today": db.query(
            "SELECT COALESCE(SUM(total),0) AS s FROM \"order\" "
            "WHERE substr(created_at,1,10) = ? AND status != 'cancelled'",
            (today,), one=True)["s"],
        "open_orders": db.query(
            "SELECT COUNT(*) AS c FROM \"order\" WHERE status IN ('new','preparing')",
            one=True)["c"],
        "pending_tables": db.query(
            "SELECT COUNT(*) AS c FROM reservation WHERE status = 'pending'",
            one=True)["c"],
        "items_live": db.query(
            "SELECT COUNT(*) AS c FROM menu_item WHERE available = 1", one=True)["c"],
        "unread": unread_count(),
    }

    # last 7 days of revenue, for the bar chart
    series = []
    for offset in range(6, -1, -1):
        day = (date.today() - timedelta(days=offset))
        row = db.query(
            "SELECT COALESCE(SUM(total),0) AS s FROM \"order\" "
            "WHERE substr(created_at,1,10) = ? AND status != 'cancelled'",
            (day.isoformat(),), one=True)
        series.append({"label": day.strftime("%a"), "value": row["s"]})

    top = db.query(
        """SELECT item_name, SUM(quantity) AS qty, SUM(quantity * unit_price) AS revenue
           FROM order_line GROUP BY item_name ORDER BY qty DESC LIMIT 5"""
    )
    recent_orders = db.query('SELECT * FROM "order" ORDER BY id DESC LIMIT 6')
    upcoming = db.query(
        "SELECT * FROM reservation WHERE status IN ('pending','confirmed') "
        "ORDER BY date, time LIMIT 6"
    )
    return render_template(
        "admin/dashboard.html", stats=stats, series=series, top=top,
        recent_orders=recent_orders, upcoming=upcoming, unread=stats["unread"],
    )


# --------------------------------------------------------------------------
# admin: menu
# --------------------------------------------------------------------------

@app.route("/admin/menu")
@login_required
def admin_menu():
    items = db.query(
        """SELECT m.*, c.name AS category FROM menu_item m
           JOIN category c ON c.id = m.category_id
           ORDER BY c.position, m.name"""
    )
    return render_template("admin/menu.html", items=items, cats=categories(),
                           unread=unread_count())


@app.route("/admin/menu/new", methods=["GET", "POST"])
@app.route("/admin/menu/<int:item_id>/edit", methods=["GET", "POST"])
@login_required
def admin_item_form(item_id=None):
    item = None
    if item_id:
        item = db.query("SELECT * FROM menu_item WHERE id = ?", (item_id,), one=True)
        if not item:
            abort(404)

    if request.method == "POST":
        f = request.form
        name = f.get("name", "").strip()
        try:
            price = float(f.get("price") or 0)
        except ValueError:
            price = -1
        if not name or price < 0:
            flash("A name and a price of zero or more are needed.", "warn")
        else:
            values = (
                name, f.get("description", "").strip()[:400], price,
                int(f.get("category_id")), f.get("image_url", "").strip(),
                1 if f.get("is_special") else 0,
                1 if f.get("available") else 0,
            )
            if item:
                db.execute(
                    """UPDATE menu_item SET name=?, description=?, price=?, category_id=?,
                       image_url=?, is_special=?, available=? WHERE id=?""",
                    values + (item["id"],))
                flash(f"{name} updated.", "good")
            else:
                db.execute(
                    """INSERT INTO menu_item
                       (name, description, price, category_id, image_url, is_special, available, created_at)
                       VALUES (?,?,?,?,?,?,?,?)""", values + (db.now(),))
                flash(f"{name} added to the menu.", "good")
            return redirect(url_for("admin_menu"))

    return render_template("admin/item_form.html", item=item, cats=categories(),
                           unread=unread_count())


@app.post("/admin/menu/<int:item_id>/toggle")
@login_required
def admin_item_toggle(item_id):
    db.execute("UPDATE menu_item SET available = 1 - available WHERE id = ?", (item_id,))
    return redirect(url_for("admin_menu"))


@app.post("/admin/menu/<int:item_id>/delete")
@login_required
def admin_item_delete(item_id):
    db.execute("DELETE FROM menu_item WHERE id = ?", (item_id,))
    flash("Item removed.", "good")
    return redirect(url_for("admin_menu"))


@app.route("/admin/categories", methods=["GET", "POST"])
@login_required
def admin_categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            try:
                db.execute(
                    "INSERT INTO category (name, blurb, position) VALUES (?,?,?)",
                    (name, request.form.get("blurb", "").strip(),
                     int(request.form.get("position") or 99)))
                flash(f"Section “{name}” added.", "good")
            except Exception:
                flash("There is already a section with that name.", "warn")
        return redirect(url_for("admin_categories"))

    rows = db.query(
        """SELECT c.*, COUNT(m.id) AS item_count FROM category c
           LEFT JOIN menu_item m ON m.category_id = c.id
           GROUP BY c.id ORDER BY c.position, c.name"""
    )
    return render_template("admin/categories.html", rows=rows, unread=unread_count())


@app.post("/admin/categories/<int:cat_id>/delete")
@login_required
def admin_category_delete(cat_id):
    db.execute("DELETE FROM category WHERE id = ?", (cat_id,))
    flash("Section removed along with its items.", "good")
    return redirect(url_for("admin_categories"))


# --------------------------------------------------------------------------
# admin: orders, tables, inbox
# --------------------------------------------------------------------------

@app.route("/admin/orders")
@login_required
def admin_orders():
    status = request.args.get("status", "")
    if status in ORDER_STATUSES:
        orders = db.query('SELECT * FROM "order" WHERE status = ? ORDER BY id DESC', (status,))
    else:
        orders = db.query('SELECT * FROM "order" ORDER BY id DESC')
    lines = {}
    for order in orders:
        lines[order["id"]] = db.query(
            "SELECT * FROM order_line WHERE order_id = ?", (order["id"],))
    return render_template("admin/orders.html", orders=orders, lines=lines,
                           statuses=ORDER_STATUSES, status=status, unread=unread_count())


@app.post("/admin/orders/<int:order_id>/status")
@login_required
def admin_order_status(order_id):
    new = request.form.get("status")
    if new in ORDER_STATUSES:
        db.execute('UPDATE "order" SET status = ? WHERE id = ?', (new, order_id))
    return redirect(request.referrer or url_for("admin_orders"))


@app.route("/admin/reservations")
@login_required
def admin_reservations():
    rows = db.query("SELECT * FROM reservation ORDER BY date DESC, time DESC")
    return render_template("admin/reservations.html", rows=rows,
                           statuses=RESERVATION_STATUSES, unread=unread_count())


@app.post("/admin/reservations/<int:res_id>/status")
@login_required
def admin_reservation_status(res_id):
    new = request.form.get("status")
    if new in RESERVATION_STATUSES:
        db.execute("UPDATE reservation SET status = ? WHERE id = ?", (new, res_id))
    return redirect(url_for("admin_reservations"))


@app.route("/admin/messages")
@login_required
def admin_messages():
    rows = db.query("SELECT * FROM message ORDER BY id DESC")
    return render_template("admin/messages.html", rows=rows, unread=unread_count())


@app.post("/admin/messages/<int:msg_id>/read")
@login_required
def admin_message_read(msg_id):
    db.execute("UPDATE message SET is_read = 1 WHERE id = ?", (msg_id,))
    return redirect(url_for("admin_messages"))


@app.post("/admin/messages/<int:msg_id>/delete")
@login_required
def admin_message_delete(msg_id):
    db.execute("DELETE FROM message WHERE id = ?", (msg_id,))
    return redirect(url_for("admin_messages"))


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True, port=5000)
