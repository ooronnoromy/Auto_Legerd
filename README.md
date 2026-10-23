# AutoLedger — responsive car cost management PWA

An original Django + PostgreSQL car expense management application inspired by the supplied black-and-red mobile mockup. Runs in browsers on Windows, macOS, Linux, Android, and iPhone/iPad.

## Interface and navigation

The app uses a liquid glass theme on desktop and phones, with translucent
surfaces and a sticky top navigation dock. Inactive destinations show icons;
the current destination expands to show its label. On phones, swipe the top
dock to reach additional destinations. Manage Users and Django Admin appear
for staff accounts.

Click the search icon to open the search panel below the navigation bar.
Search expense titles, car names, stations, and notes. Press `/` outside a
form field to open search, and Escape to close it. Search also works without
JavaScript using the native disclosure control. The glass theme supports
reduced motion and includes a fallback for browsers without backdrop blur.

The app includes car assignments, fuel and maintenance entries, photo uploads,
filtered histories, analytics, reminders, account settings, and CSV exports.
Currency is BDT. Receipt details are entered manually; uploads do not perform OCR.

## Implemented

Mobile push notifications for new cars and expenses are available from
**Profile → Mobile notifications**. Notifications go to admins, the car owner,
and the assigned driver. See [setup and phone requirements](PUSH_NOTIFICATIONS.md).
- Login using **phone number as username**, Django hashed passwords, and terminal-created superadmin.
- Superadmin dashboard and app user creation; standard users cannot see each other's cars, expenses, photos or reminders.
- Multiple vehicles, photo uploads, fuel type and odometer.
- Fuel and other expense management, including **separate receipt photo and fuel pump/meter photo**. Upload from mobile camera or device files.
- Maintenance reminders with odometer/date triggers (displayed as a list, not automatic push alerts).
- Expense trends and category charts, responsive dashboard and BDT currency.
- CSV expense export; Django admin panel.
- PWA manifest, install prompt and cached app CSS/JS/icons. **Requires network access to use server-side data.** Not offline data entry.

## Quick start on Windows (no Docker or PostgreSQL needed)

Install Python 3.12, open PowerShell in this folder, and run:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

The script creates `.venv`, installs dependencies, applies migrations, and starts
the app at http://127.0.0.1:8000/. Local development defaults to SQLite and stores
data in `db.sqlite3`. Keep that file to preserve your data.

In a second terminal, create your first administrator:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Use your phone number as the username. Stop the server with Ctrl+C. Run the
startup command again whenever you want to use the project. You can select a
different port with `-Port 8001`.

Settings load `.env` automatically. Use `DJANGO_DEBUG=true` for local HTTP
development to avoid collisions with Windows' system `DEBUG` variable.
Copy `.env.example` to `.env` to customize
them; environment variables take precedence. Set `USE_SQLITE=false` when using
PostgreSQL locally. Docker explicitly selects PostgreSQL.

## Deploy to Railway

### Install on a phone

Open the HTTPS website in your phone browser and tap **Download app** on the
sign-in page or above the dashboard. Android browsers can show an install
prompt. On iPhone, the button explains how to use Safari's **Share -> Add to
Home Screen**. The installed app still requires an internet connection.

If sign-in reports an expired form, return to sign in to obtain a fresh token.
Allow cookies and use the same website address throughout. Behind a non-Railway
HTTPS proxy, set `TRUST_PROXY_HTTPS=true` only if that proxy controls the
`X-Forwarded-Proto` header, and configure `ALLOWED_HOSTS` and
`CSRF_TRUSTED_ORIGINS` with your actual domain (origins include `https://`).

Follow [RAILWAY.md](RAILWAY.md) for the PostgreSQL service, persistent photo
volume, production variables, domain setup, and administrator creation.
The included Dockerfile and `railway.json` configure production startup,
migrations, static assets, and health checks.

## Quick start using Docker (Windows PowerShell)
1. Install Docker Desktop and start it.
2. Unzip the folder and open a terminal in its directory.
3. Copy `.env.example` to `.env`. Change `SECRET_KEY` and `POSTGRES_PASSWORD` in `.env` (Docker will use these values). Keep `DJANGO_DEBUG=true` only for local use.
4. Run:
   ```powershell
   docker compose up --build -d
   docker compose exec web python manage.py createsuperuser
   ```
5. Enter your **phone number** as the `Username`, e.g. `01712345678` (10–15 digits, optional +), and set a strong password.
6. Visit `http://localhost:8000/login/` and sign in. Go to **Manage Users → Create User** to create regular users with phone number usernames.
7. Django staff admin is at `http://localhost:8000/admin/`.

`docker compose down` stops the project. Don't run `docker compose down -v` if you want to keep your database.

## Local Python + PostgreSQL (without Docker)
Install Python 3.12+, PostgreSQL 16+, then create a PostgreSQL database and user matching `.env.example`.

**Windows PowerShell:**
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:SECRET_KEY="a-unique-long-random-string"
$env:POSTGRES_DB="autoledger"
$env:POSTGRES_USER="autoledger"
$env:POSTGRES_PASSWORD="your-db-password"
$env:POSTGRES_HOST="localhost"
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Note: both Django and Docker Compose load `.env`. Set `USE_SQLITE=false` there when using PostgreSQL locally.

**For a local development preview without PostgreSQL only:** set `$env:USE_SQLITE="true"` before running `migrate`. Production is intended for PostgreSQL.

## Install on laptops, phones and tablets (PWA)
- On the same computer, `http://localhost:8000` is enough for development.
- To access on another device, run a proper HTTPS-hosted deployment with a domain and DNS, and configure `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, static/media serving, certificates and a production secret; **do not expose Django's development server publicly**.
- Chrome / Edge on Windows, Android or supported desktop: open the HTTPS website → Install icon in address bar or browser menu → Install app.
- iPhone/iPad Safari: open the HTTPS website → Share → Add to Home Screen.
- Tablets use the same method with their respective browsers.
- The installed app opens in a separate app-style window. It is **not** a native Windows `.exe`, APK, or iOS App Store binary.

## Important limitations
This version is a functional core app, not the complete aspirational mockup. Receipt/pump images are stored and viewable but **OCR/AI automatic extraction is not implemented**. Fuel cost calculations are entered as fields rather than OCR-derived. There is no automatic notification service, background photo sync, cloud backup, REST API, native packaging, or app-store publishing. Chart.js and Google Fonts require network access; custom CSS and icons are bundled locally. If charts cannot load, expense totals and the main app remain available.

For production: set `DJANGO_DEBUG=false`, configure a reverse proxy for HTTPS and protected media files, enforce image upload quotas/MIME validation, run `python manage.py check --deploy`, back up PostgreSQL, and add monitoring. Docker's published port is for local/staging use, not hardened internet-facing production.
