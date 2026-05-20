import sqlite3
import os
from datetime import date, datetime

# Resolved at runtime from config via init_db(path=...).
# Falls back to env var for scripts that call get_db() directly.
DB_PATH: str = (
    os.environ.get("RAILWAY_DATABASE_PATH")
    or os.environ.get("DATABASE_PATH")
    or "portal.db"
)


def get_db(path: str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: str | None = None) -> None:
    """Initialise the database schema. Call once per process (idempotent)."""
    global DB_PATH
    if path:
        DB_PATH = path
    conn = get_db()
    c = conn.cursor()

    c.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            display_name TEXT NOT NULL,
            client1_first TEXT NOT NULL,
            client1_last  TEXT NOT NULL,
            client1_dob   TEXT DEFAULT '',
            client1_ssn4  TEXT DEFAULT '',
            client2_first TEXT DEFAULT '',
            client2_last  TEXT DEFAULT '',
            client2_dob   TEXT DEFAULT '',
            client2_ssn4  TEXT DEFAULT '',
            is_married    INTEGER DEFAULT 0,
            client1_salary    REAL DEFAULT 0,
            client2_salary    REAL DEFAULT 0,
            monthly_expenses  REAL DEFAULT 0,
            insurance_deductibles REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            owner      TEXT NOT NULL DEFAULT 'client1',
            account_type      TEXT NOT NULL DEFAULT 'Checking',
            institution       TEXT DEFAULT '',
            account_number_last4 TEXT DEFAULT '',
            is_retirement INTEGER DEFAULT 0,
            is_trust      INTEGER DEFAULT 0,
            is_liability  INTEGER DEFAULT 0,
            liability_rate REAL DEFAULT 0,
            display_order INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id  INTEGER NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
            quarter    INTEGER NOT NULL,
            year       INTEGER NOT NULL,
            inflow     REAL DEFAULT 0,
            outflow    REAL DEFAULT 0,
            excess     REAL DEFAULT 0,
            private_reserve_balance  REAL DEFAULT 0,
            schwab_investment_balance REAL DEFAULT 0,
            private_reserve_target   REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS report_balances (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id  INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
            account_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
            balance    REAL DEFAULT 0,
            cash_value REAL DEFAULT 0,
            as_of_date TEXT DEFAULT '',
            is_stale   INTEGER DEFAULT 0
        );
    """)
    conn.commit()

    # Seed sample client if database is empty
    row = c.execute("SELECT COUNT(*) FROM clients").fetchone()
    if row[0] == 0:
        _seed_sample_data(conn)

    conn.close()


def _seed_sample_data(conn):
    """
    Populate the database with three demo client families, each with a full
    account list and four quarters of report history.
    """
    c = conn.cursor()

    # ── Helper ────────────────────────────────────────────────────────────────
    def add_client(display_name,
                   c1_first, c1_last, c1_dob, c1_ssn4, c1_salary,
                   c2_first, c2_last, c2_dob, c2_ssn4, c2_salary,
                   is_married, monthly_expenses, insurance_deductibles, notes=""):
        c.execute("""
            INSERT INTO clients (display_name,
                client1_first, client1_last, client1_dob, client1_ssn4,
                client2_first, client2_last, client2_dob, client2_ssn4,
                is_married, client1_salary, client2_salary,
                monthly_expenses, insurance_deductibles, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (display_name,
              c1_first, c1_last, c1_dob, c1_ssn4,
              c2_first, c2_last, c2_dob, c2_ssn4,
              is_married, c1_salary, c2_salary,
              monthly_expenses, insurance_deductibles, notes))
        return c.lastrowid

    def add_accounts(client_id, rows):
        """rows: (owner, type, institution, last4, is_ret, is_trust, is_liab, rate)"""
        for i, r in enumerate(rows):
            c.execute("""
                INSERT INTO accounts (client_id, owner, account_type, institution,
                    account_number_last4, is_retirement, is_trust,
                    is_liability, liability_rate, display_order)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, (client_id, r[0], r[1], r[2], r[3],
                  r[4], r[5], r[6], r[7], i))
        conn.commit()
        rows_db = c.execute(
            "SELECT id FROM accounts WHERE client_id=? ORDER BY display_order, id",
            (client_id,)
        ).fetchall()
        return [r["id"] for r in rows_db]

    def add_report(client_id, quarter, year, inflow, outflow,
                   pr_balance, schwab_balance,
                   monthly_expenses, insurance_deductibles,
                   account_ids, balances, created_at=None):
        excess = inflow - outflow
        target = (6 * monthly_expenses) + insurance_deductibles
        ts = created_at or f"{year}-{quarter * 3:02d}-30 12:00:00"
        c.execute("""
            INSERT INTO reports (client_id, quarter, year, inflow, outflow, excess,
                private_reserve_balance, schwab_investment_balance,
                private_reserve_target, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (client_id, quarter, year, inflow, outflow, excess,
              pr_balance, schwab_balance, target, ts))
        report_id = c.lastrowid
        for acct_id, (bal, cv, as_of, stale) in zip(account_ids, balances):
            c.execute("""
                INSERT INTO report_balances
                    (report_id, account_id, balance, cash_value, as_of_date, is_stale)
                VALUES (?,?,?,?,?,?)
            """, (report_id, acct_id, bal, cv, as_of, stale))
        conn.commit()
        return report_id

    # ─────────────────────────────────────────────────────────────────────────
    # CLIENT 1 — Green Family (married couple, ~late 50s, strong retirement base)
    # ─────────────────────────────────────────────────────────────────────────
    cid1 = add_client(
        "Green Family",
        "John", "Green",  "1965-04-12", "3821", 8000,
        "Jane", "Green",  "1967-09-30", "7744", 7000,
        1, 12000, 3000,
        "Flagship family. Prioritising Roth conversions before RMD age."
    )
    acct_ids1 = add_accounts(cid1, [
        # owner,    type,          institution,        last4,  ret, trust, liab, rate
        ("client1", "Roth IRA",    "Charles Schwab",   "4491", 1, 0, 0, 0.0),
        ("client1", "IRA",         "Charles Schwab",   "2203", 1, 0, 0, 0.0),
        ("client2", "IRA",         "Charles Schwab",   "8812", 1, 0, 0, 0.0),
        ("client2", "Roth IRA",    "Charles Schwab",   "3340", 1, 0, 0, 0.0),
        ("client2", "401(k)",      "Fidelity",         "9901", 1, 0, 0, 0.0),
        ("client1", "Checking",    "Pinnacle Bank",    "1100", 0, 0, 0, 0.0),
        ("client1", "FICA",        "StoneCastle",      "7742", 0, 0, 0, 0.0),
        ("joint",   "Brokerage",   "Charles Schwab",   "5500", 0, 0, 0, 0.0),
        ("client2", "Savings",     "Pinnacle Bank",    "2266", 0, 0, 0, 0.0),
        ("trust",   "Family Trust","National Trust Co","",     0, 1, 0, 0.0),
        ("joint",   "Mortgage",    "Wells Fargo",      "6610", 0, 0, 1, 6.5),
        ("joint",   "Auto Loan",   "Toyota Financial", "3392", 0, 0, 1, 4.9),
    ])
    # Q2 2025
    add_report(cid1, 2, 2025, 15000, 12000, 87400, 142000, 12000, 3000,
               acct_ids1, [
        #  balance,     cash_value,  as_of,         stale
        (112340.00,  0,        "2025-06-30", 0),  # John Roth IRA
        (218670.00,  0,        "2025-06-30", 0),  # John IRA
        (195820.00,  0,        "2025-06-30", 0),  # Jane IRA
        ( 88540.00,  0,        "2025-06-30", 0),  # Jane Roth IRA
        (163210.00,  0,        "2025-06-30", 0),  # Jane 401k
        (  8450.00,  0,        "2025-06-30", 0),  # Checking
        ( 15200.00, 15200,     "2025-06-30", 0),  # FICA
        ( 54300.00,  0,        "2025-06-30", 0),  # Brokerage
        (  6800.00,  0,        "2025-06-30", 0),  # Savings
        (425000.00,  0,        "2025-06-30", 0),  # Family Trust
        (287400.00,  0,        "2025-06-30", 0),  # Mortgage
        ( 18600.00,  0,        "2025-06-30", 0),  # Auto Loan
    ], created_at="2025-07-05 10:30:00")
    # Q3 2025
    add_report(cid1, 3, 2025, 15000, 11800, 90100, 149500, 12000, 3000,
               acct_ids1, [
        (118920.00,  0,        "2025-09-30", 0),
        (224100.00,  0,        "2025-09-30", 0),
        (201340.00,  0,        "2025-09-30", 0),
        ( 92780.00,  0,        "2025-09-30", 0),
        (169500.00,  0,        "2025-09-30", 0),
        (  9200.00,  0,        "2025-09-30", 0),
        ( 15200.00, 15200,     "2025-09-30", 0),
        ( 58700.00,  0,        "2025-09-30", 0),
        (  7100.00,  0,        "2025-09-30", 0),
        (425000.00,  0,        "2025-06-30", 1),  # stale — not updated
        (283100.00,  0,        "2025-09-30", 0),
        ( 15900.00,  0,        "2025-09-30", 0),
    ], created_at="2025-10-08 09:15:00")
    # Q4 2025
    add_report(cid1, 4, 2025, 15000, 12200, 93600, 158200, 12000, 3000,
               acct_ids1, [
        (124560.00,  0,        "2025-12-31", 0),
        (231800.00,  0,        "2025-12-31", 0),
        (207900.00,  0,        "2025-12-31", 0),
        ( 97200.00,  0,        "2025-12-31", 0),
        (177400.00,  0,        "2025-12-31", 0),
        ( 10300.00,  0,        "2025-12-31", 0),
        ( 15200.00, 15200,     "2025-12-31", 0),
        ( 63800.00,  0,        "2025-12-31", 0),
        (  8400.00,  0,        "2025-12-31", 0),
        (425000.00,  0,        "2025-06-30", 1),
        (278500.00,  0,        "2025-12-31", 0),
        ( 12900.00,  0,        "2025-12-31", 0),
    ], created_at="2026-01-12 11:00:00")
    # Q1 2026
    add_report(cid1, 1, 2026, 15000, 11600, 96800, 164700, 12000, 3000,
               acct_ids1, [
        (131200.00,  0,        "2026-03-31", 0),
        (238400.00,  0,        "2026-03-31", 0),
        (214600.00,  0,        "2026-03-31", 0),
        (101800.00,  0,        "2026-03-31", 0),
        (184200.00,  0,        "2026-03-31", 0),
        ( 11500.00,  0,        "2026-03-31", 0),
        ( 15200.00, 15200,     "2026-03-31", 0),
        ( 68400.00,  0,        "2026-03-31", 0),
        (  9200.00,  0,        "2026-03-31", 0),
        (425000.00,  0,        "2026-03-31", 0),
        (273700.00,  0,        "2026-03-31", 0),
        (  9800.00,  0,        "2026-03-31", 0),
    ], created_at="2026-04-09 14:20:00")

    # ─────────────────────────────────────────────────────────────────────────
    # CLIENT 2 — Thompson Family (pre-retirees, higher income, larger assets)
    # ─────────────────────────────────────────────────────────────────────────
    cid2 = add_client(
        "Thompson Family",
        "Michael", "Thompson", "1958-11-20", "5512", 12000,
        "Patricia", "Thompson", "1960-03-08", "9034", 6000,
        1, 14000, 5000,
        "Planning to retire in 3 years. Maximising 401(k) catch-up contributions."
    )
    acct_ids2 = add_accounts(cid2, [
        ("client1", "IRA",          "Vanguard",         "7710", 1, 0, 0, 0.0),
        ("client1", "Roth IRA",     "Vanguard",         "3309", 1, 0, 0, 0.0),
        ("client1", "401(k)",       "Empower",          "8821", 1, 0, 0, 0.0),
        ("client2", "IRA",          "Vanguard",         "4456", 1, 0, 0, 0.0),
        ("client2", "Roth IRA",     "Vanguard",         "2287", 1, 0, 0, 0.0),
        ("joint",   "Brokerage",    "TD Ameritrade",    "6600", 0, 0, 0, 0.0),
        ("client1", "Checking",     "Chase Bank",       "0011", 0, 0, 0, 0.0),
        ("client2", "Savings",      "Chase Bank",       "5544", 0, 0, 0, 0.0),
        ("trust",   "Family Trust", "Northern Trust",   "",     0, 1, 0, 0.0),
        ("joint",   "Mortgage",     "Bank of America",  "9902", 0, 0, 1, 5.75),
    ])
    # Q3 2025
    add_report(cid2, 3, 2025, 18000, 14000, 124000, 210000, 14000, 5000,
               acct_ids2, [
        (445200.00,  0,        "2025-09-30", 0),
        ( 98700.00,  0,        "2025-09-30", 0),
        (512300.00,  0,        "2025-09-30", 0),
        (287600.00,  0,        "2025-09-30", 0),
        ( 74100.00,  0,        "2025-09-30", 0),
        (183400.00,  0,        "2025-09-30", 0),
        ( 22100.00,  0,        "2025-09-30", 0),
        ( 18500.00,  0,        "2025-09-30", 0),
        (680000.00,  0,        "2025-09-30", 0),
        (198400.00,  0,        "2025-09-30", 0),
    ], created_at="2025-10-15 09:45:00")
    # Q4 2025
    add_report(cid2, 4, 2025, 18000, 13800, 128000, 221500, 14000, 5000,
               acct_ids2, [
        (461800.00,  0,        "2025-12-31", 0),
        (104200.00,  0,        "2025-12-31", 0),
        (531900.00,  0,        "2025-12-31", 0),
        (298400.00,  0,        "2025-12-31", 0),
        ( 78900.00,  0,        "2025-12-31", 0),
        (194700.00,  0,        "2025-12-31", 0),
        ( 24600.00,  0,        "2025-12-31", 0),
        ( 19800.00,  0,        "2025-12-31", 0),
        (680000.00,  0,        "2025-09-30", 1),
        (193600.00,  0,        "2025-12-31", 0),
    ], created_at="2026-01-18 10:30:00")
    # Q1 2026
    add_report(cid2, 1, 2026, 18000, 14200, 131800, 234600, 14000, 5000,
               acct_ids2, [
        (478300.00,  0,        "2026-03-31", 0),
        (110600.00,  0,        "2026-03-31", 0),
        (553200.00,  0,        "2026-03-31", 0),
        (309100.00,  0,        "2026-03-31", 0),
        ( 83400.00,  0,        "2026-03-31", 0),
        (205800.00,  0,        "2026-03-31", 0),
        ( 26900.00,  0,        "2026-03-31", 0),
        ( 21200.00,  0,        "2026-03-31", 0),
        (680000.00,  0,        "2026-03-31", 0),
        (188400.00,  0,        "2026-03-31", 0),
    ], created_at="2026-04-14 11:15:00")

    # ─────────────────────────────────────────────────────────────────────────
    # CLIENT 3 — Parker (single professional, mid-career, building wealth)
    # ─────────────────────────────────────────────────────────────────────────
    cid3 = add_client(
        "Parker",
        "Rachel", "Parker", "1983-06-25", "2291", 9500,
        "", "", "", "", 0,
        0, 7500, 2000,
        "Single. Recently started maxing Roth IRA and building brokerage account."
    )
    acct_ids3 = add_accounts(cid3, [
        ("client1", "Roth IRA",  "Fidelity",       "8834", 1, 0, 0, 0.0),
        ("client1", "401(k)",    "Fidelity",       "4423", 1, 0, 0, 0.0),
        ("client1", "Brokerage", "Fidelity",       "9910", 0, 0, 0, 0.0),
        ("client1", "Checking",  "Regions Bank",   "3301", 0, 0, 0, 0.0),
        ("client1", "Savings",   "Regions Bank",   "7788", 0, 0, 0, 0.0),
        ("client1", "FICA",      "MassMutual",     "5567", 0, 0, 0, 0.0),
        ("client1", "Auto Loan", "Honda Financial", "",    0, 0, 1, 5.9),
        ("client1", "Student Loan", "Navient",     "",     0, 0, 1, 3.5),
    ])
    # Q4 2025
    add_report(cid3, 4, 2025, 9500, 7500, 42000, 38000, 7500, 2000,
               acct_ids3, [
        ( 28400.00,  0,        "2025-12-31", 0),
        ( 61200.00,  0,        "2025-12-31", 0),
        ( 14700.00,  0,        "2025-12-31", 0),
        (  4800.00,  0,        "2025-12-31", 0),
        ( 38200.00,  0,        "2025-12-31", 0),
        ( 42000.00, 42000,     "2025-12-31", 0),
        ( 14200.00,  0,        "2025-12-31", 0),
        ( 22800.00,  0,        "2025-12-31", 0),
    ], created_at="2026-01-20 15:00:00")
    # Q1 2026
    add_report(cid3, 1, 2026, 9500, 7200, 43800, 41500, 7500, 2000,
               acct_ids3, [
        ( 30100.00,  0,        "2026-03-31", 0),
        ( 64800.00,  0,        "2026-03-31", 0),
        ( 17200.00,  0,        "2026-03-31", 0),
        (  5600.00,  0,        "2026-03-31", 0),
        ( 40100.00,  0,        "2026-03-31", 0),
        ( 43800.00, 43800,     "2026-03-31", 0),
        ( 11400.00,  0,        "2026-03-31", 0),
        ( 20100.00,  0,        "2026-03-31", 0),
    ], created_at="2026-04-21 08:45:00")

    conn.commit()


# ── Client queries ──────────────────────────────────────────────────────────

def get_all_clients():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*,
               (SELECT created_at FROM reports WHERE client_id = c.id ORDER BY year DESC, quarter DESC LIMIT 1) AS last_report_at
        FROM clients c ORDER BY c.display_name
    """).fetchall()
    conn.close()
    return rows


def get_client(client_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
    conn.close()
    return row


def create_client(data):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO clients (display_name, client1_first, client1_last, client1_dob, client1_ssn4,
            client2_first, client2_last, client2_dob, client2_ssn4,
            is_married, client1_salary, client2_salary, monthly_expenses, insurance_deductibles, notes)
        VALUES (:display_name, :client1_first, :client1_last, :client1_dob, :client1_ssn4,
            :client2_first, :client2_last, :client2_dob, :client2_ssn4,
            :is_married, :client1_salary, :client2_salary, :monthly_expenses, :insurance_deductibles, :notes)
    """, data)
    client_id = c.lastrowid
    conn.commit()
    conn.close()
    return client_id


def update_client(client_id, data):
    conn = get_db()
    data["id"] = client_id
    conn.execute("""
        UPDATE clients SET
            display_name=:display_name, client1_first=:client1_first, client1_last=:client1_last,
            client1_dob=:client1_dob, client1_ssn4=:client1_ssn4,
            client2_first=:client2_first, client2_last=:client2_last,
            client2_dob=:client2_dob, client2_ssn4=:client2_ssn4,
            is_married=:is_married, client1_salary=:client1_salary, client2_salary=:client2_salary,
            monthly_expenses=:monthly_expenses, insurance_deductibles=:insurance_deductibles,
            notes=:notes, updated_at=datetime('now')
        WHERE id=:id
    """, data)
    conn.commit()
    conn.close()


def delete_client(client_id):
    conn = get_db()
    conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()


# ── Account queries ──────────────────────────────────────────────────────────

def get_accounts(client_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM accounts WHERE client_id = ? ORDER BY display_order, id",
        (client_id,)
    ).fetchall()
    conn.close()
    return rows


def replace_accounts(client_id, account_list):
    """Delete existing accounts and insert fresh list."""
    conn = get_db()
    conn.execute("DELETE FROM accounts WHERE client_id = ?", (client_id,))
    for i, acct in enumerate(account_list):
        conn.execute("""
            INSERT INTO accounts (client_id, owner, account_type, institution,
                account_number_last4, is_retirement, is_trust, is_liability, liability_rate, display_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client_id,
            acct.get("owner", "client1"),
            acct.get("account_type", ""),
            acct.get("institution", ""),
            acct.get("account_number_last4", ""),
            1 if acct.get("is_retirement") else 0,
            1 if acct.get("is_trust") else 0,
            1 if acct.get("is_liability") else 0,
            float(acct.get("liability_rate") or 0),
            i,
        ))
    conn.commit()
    conn.close()


# ── Report queries ──────────────────────────────────────────────────────────

def get_reports(client_id):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM reports WHERE client_id = ? ORDER BY year DESC, quarter DESC",
        (client_id,)
    ).fetchall()
    conn.close()
    return rows


def get_report(report_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    conn.close()
    return row


def get_last_report(client_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM reports WHERE client_id = ? ORDER BY year DESC, quarter DESC LIMIT 1",
        (client_id,)
    ).fetchone()
    conn.close()
    return row


def create_report(client_id, data, balances):
    """Create a report and its account balances. Returns report_id."""
    conn = get_db()
    c = conn.cursor()

    inflow  = float(data.get("inflow", 0) or 0)
    outflow = float(data.get("outflow", 0) or 0)
    excess  = inflow - outflow
    monthly_expenses = float(data.get("monthly_expenses", 0) or 0)
    deductibles      = float(data.get("insurance_deductibles", 0) or 0)
    target = (6 * monthly_expenses) + deductibles

    c.execute("""
        INSERT INTO reports (client_id, quarter, year, inflow, outflow, excess,
            private_reserve_balance, schwab_investment_balance, private_reserve_target)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        int(data["quarter"]),
        int(data["year"]),
        inflow, outflow, excess,
        float(data.get("private_reserve_balance", 0) or 0),
        float(data.get("schwab_investment_balance", 0) or 0),
        target,
    ))
    report_id = c.lastrowid

    for b in balances:
        c.execute("""
            INSERT INTO report_balances (report_id, account_id, balance, cash_value, as_of_date, is_stale)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            report_id,
            int(b["account_id"]),
            float(b.get("balance", 0) or 0),
            float(b.get("cash_value", 0) or 0),
            b.get("as_of_date", ""),
            1 if b.get("is_stale") else 0,
        ))

    conn.commit()
    conn.close()
    return report_id


def get_report_balances(report_id):
    conn = get_db()
    rows = conn.execute("""
        SELECT rb.*, a.owner, a.account_type, a.institution, a.account_number_last4,
               a.is_retirement, a.is_trust, a.is_liability, a.liability_rate
        FROM report_balances rb
        JOIN accounts a ON rb.account_id = a.id
        WHERE rb.report_id = ?
        ORDER BY a.display_order, a.id
    """, (report_id,)).fetchall()
    conn.close()
    return rows


def get_last_report_balances(client_id):
    """Get balances from the most recent report for pre-fill."""
    conn = get_db()
    rows = conn.execute("""
        SELECT rb.account_id, rb.balance, rb.cash_value, rb.as_of_date
        FROM report_balances rb
        JOIN reports r ON rb.report_id = r.id
        WHERE r.client_id = ? AND r.id = (
            SELECT id FROM reports WHERE client_id = ? ORDER BY year DESC, quarter DESC LIMIT 1
        )
    """, (client_id, client_id)).fetchall()
    conn.close()
    return {row["account_id"]: dict(row) for row in rows}


def calc_tcc_totals(balances):
    """Compute TCC summary numbers from a list of balance rows."""
    c1_ret = c2_ret = non_ret = trust = liab = 0.0
    for b in balances:
        bal = float(b["balance"] or 0)
        if b["is_liability"]:
            liab += bal
        elif b["is_trust"]:
            trust += bal
        elif b["is_retirement"]:
            if b["owner"] == "client1":
                c1_ret += bal
            elif b["owner"] == "client2":
                c2_ret += bal
            else:
                c1_ret += bal / 2
                c2_ret += bal / 2
        else:
            non_ret += bal
    grand = c1_ret + c2_ret + non_ret + trust
    return dict(c1_ret=c1_ret, c2_ret=c2_ret, non_ret=non_ret,
                trust=trust, liab=liab, grand=grand)
