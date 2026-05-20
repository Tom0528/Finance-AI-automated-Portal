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

## Railway deployment

1. Push this repository to GitHub.
2. Create a new Railway project → **Deploy from GitHub repo**.
3. Railway auto-detects `railway.toml` and uses `app/` as the build root.
4. Add a **Volume** mounted at `/data` for database persistence.
5. Set the following environment variables in the Railway dashboard:

   | Variable | Description |
   |---|---|
   | `SECRET_KEY` | Random secret string (required) |
   | `RAILWAY_DATABASE_PATH` | Path to SQLite file on volume, e.g. `/data/portal.db` |
   | `CANVA_API_KEY` | Canva Connect API key (optional — enables Export to Canva) |
   | `FLASK_ENV` | `production` |

## Environment variables

See `app/.env.example` for a full list with descriptions.

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
