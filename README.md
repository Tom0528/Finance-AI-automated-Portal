# AW Client Report Portal

A web-based financial reporting portal that generates pixel-perfect SACS
(Simple Automated Cashflow System) and TCC (Total Client Chart) PDF reports
for financial advisors, with optional Canva export.

## Features

- **Client management** — create and manage client profiles with dual-client support, accounts, and salary data
- **Quarterly reports** — enter quarterly balance data with automatic cashflow calculations
- **SACS PDF** — one-page cashflow summary with inflow, outflow, and private reserve visualization
- **TCC PDF** — total client chart showing all retirement, non-retirement, trust, and liability balances
- **Canva export** — push generated PDFs to Canva as editable designs (requires API key)

## Project layout

```
app/                     ← deployable application root
├── app.py               Flask application & factory
├── wsgi.py              Gunicorn / WSGI entry-point
├── config.py            Environment-based configuration
├── database.py          SQLite data layer (CRUD + seeding)
├── canva.py             Canva Connect API integration
├── pdf_sacs.py          SACS PDF generator (ReportLab)
├── pdf_tcc.py           TCC PDF generator (ReportLab)
├── static/
│   ├── css/styles.css
│   ├── images/          Source images used in PDFs
│   └── js/app.js
├── templates/
│   ├── base.html
│   ├── clients.html
│   ├── client_detail.html
│   ├── client_form.html
│   ├── report_detail.html
│   ├── report_form.html
│   ├── report_history.html
│   └── errors/
│       ├── 404.html
│       └── 500.html
├── requirements.txt
├── runtime.txt
├── Procfile
└── .env.example         Copy to .env and fill in values
```

## Local development

```bash
cd app
pip install -r requirements.txt
cp .env.example .env          # fill in SECRET_KEY etc.
python app.py                 # starts on http://localhost:5000
```

The database (`portal.db`) is created automatically on first run and seeded
with three demo client families (Green Family, Thompson Family, Parker).

## Deployment (free options)

### Option 1 — Render (easiest, no credit card)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New Web Service** → connect the repo.
3. Render auto-detects `render.yaml` and configures everything.
4. Click **Deploy** — the app is live in ~2 minutes.
5. *(Optional)* Add `CANVA_API_KEY` in the Render environment settings.

> **Note:** The free tier has no persistent disk, so the SQLite database resets
> on each redeploy. The app auto-seeds demo data on every startup, so this is
> fine for demos.

---

### Option 2 — PythonAnywhere (always-on, persistent DB, no credit card)

1. Sign up at [pythonanywhere.com](https://www.pythonanywhere.com) (free account).
2. Open a **Bash console** and run:
   ```bash
   git clone https://github.com/YOUR_USER/YOUR_REPO.git
   cd YOUR_REPO/app
   pip3.12 install --user -r requirements.txt
   ```
3. Go to **Web** tab → **Add a new web app** → **Manual configuration** → **Python 3.12**.
4. Set the **Source code** directory to `/home/YOUR_USER/YOUR_REPO/app`.
5. Edit the **WSGI configuration file** — replace its contents with:
   ```python
   import sys
   sys.path.insert(0, '/home/YOUR_USER/YOUR_REPO/app')
   from wsgi import application
   ```
6. Add environment variables under **Web → Environment variables**:
   - `SECRET_KEY` = any random string
   - `DATABASE_PATH` = `/home/YOUR_USER/YOUR_REPO/app/portal.db`
   - `FLASK_ENV` = `production`
7. Click **Reload** — your app is live at `YOUR_USER.pythonanywhere.com`.

> **Note:** PythonAnywhere's free tier is always-on with a persistent filesystem,
> so the SQLite database survives restarts and reloads.

---

### Option 3 — Railway (when back online)

1. Push this repo to GitHub.
2. Create a new Railway project → **Deploy from GitHub repo**.
3. Railway auto-detects `railway.toml` and uses `app/` as the build root.
4. Add a **Volume** mounted at `/data` for database persistence.
5. Set environment variables:

   | Variable | Value |
   |---|---|
   | `SECRET_KEY` | Any random secret |
   | `RAILWAY_DATABASE_PATH` | `/data/portal.db` |
   | `CANVA_API_KEY` | *(optional)* |
   | `FLASK_ENV` | `production` |

---

## Environment variables

See `app/.env.example` for a full annotated list.

## Tech stack

| Layer | Technology |
|---|---|
| Web framework | Flask 3 |
| Database | SQLite (via Python stdlib `sqlite3`) |
| PDF generation | ReportLab |
| Image processing | Pillow |
| Canva integration | Canva Connect API (REST) |
| Production server | Gunicorn |
| Deployment | Railway |
