# Pistachio & Plum — cafe website with admin dashboard

A complete Flask cafe site: a responsive public website where customers browse the menu,
build a basket, place pickup orders and request tables, plus a staff dashboard for running
the shop.

## Running it

```bash
cd cafe
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000

The database is created and filled with a starter menu on first run. Nothing else to set up.

**Dashboard:** http://127.0.0.1:5000/admin — username `admin`, password `cafe123`.
Change it from the dashboard before anyone else can reach the site.

## What is in it

**Public site**
- Home page with the day's brew bar list and featured items, both pulled from the database
- Menu page grouped into sections, filterable, with add-to-basket buttons
- Basket that survives page changes, quantity controls and a checkout that returns an order reference
- Table booking form and a contact form
- Works down to a 360px phone; keyboard focus is visible throughout and motion respects
  `prefers-reduced-motion`

**Admin dashboard**
- Takings today, orders today, tickets still open, tables to confirm, items live, unread messages
- Seven-day takings chart and a best-sellers table
- Orders: filter by status, see the lines and notes, move a ticket through
  new → preparing → ready → collected
- Tables: confirm, seat or cancel a booking
- Menu: add, edit, delete items; hide an item from the site with one click; flag it as a
  home page feature
- Sections: add or remove the menu's headings and their order
- Inbox for contact form messages
- Password change

## Files

```
app.py                  routes for the public site and the admin dashboard
db.py                   schema, query helpers, starter data
requirements.txt        Flask
templates/              public pages (base.html is the shared shell)
templates/admin/        dashboard pages (admin/base.html is the shared shell)
static/css/style.css    public site
static/css/admin.css    dashboard
static/js/main.js       nav toggle, basket storage
static/js/cart.js       basket page and checkout
instance/cafe.db        SQLite database, created on first run
```

## How it is built

- **Flask** for routing and templating, **SQLite** through Python's built-in `sqlite3`.
  Flask is the only thing to install.
- Passwords are hashed with `werkzeug.security`; admin pages sit behind a `@login_required`
  decorator that checks the session.
- Order prices are re-read from the database when an order is submitted, so a customer
  editing the page in devtools cannot change what they are charged.
- Every query is parameterised, so the forms are not open to SQL injection.
- Jinja escapes template output by default, which covers the customer names and notes that
  appear in the dashboard.

## Before putting it online

1. Change the admin password.
2. Set a real secret key: `export SECRET_KEY="something long and random"`.
3. Turn off debug mode and run behind a real server, for example
   `pip install gunicorn && gunicorn -w 4 'app:app'`.
4. Serve it over HTTPS.

## Changing it for your cafe

The name, address, phone, email and opening hours live in the `CAFE` dictionary at the top
of `app.py`. Colours and fonts are CSS variables in the `:root` block of both stylesheets —
change `--plum`, `--pistachio` and `--porcelain` and the whole site follows. The menu itself
is edited from the dashboard, not in code.
