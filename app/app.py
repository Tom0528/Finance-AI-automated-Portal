"""
AW Client Report Portal
~~~~~~~~~~~~~~~~~~~~~~~
Flask application entry-point.

Routing conventions
───────────────────
  GET  /                                              → redirect to /clients
  GET  /clients                                       → client list
  GET  /clients/new                POST               → create client
  GET  /clients/<id>                                  → client detail
  GET  /clients/<id>/edit          POST               → update client
       /clients/<id>/delete        POST               → delete client
  GET  /clients/<id>/reports                          → report history
  GET  /clients/<id>/reports/new   POST               → create report
  GET  /clients/<id>/reports/<id>                     → report detail + PDFs
  GET  /clients/<id>/reports/<id>/sacs.pdf            → download SACS PDF
  GET  /clients/<id>/reports/<id>/tcc.pdf             → download TCC PDF
       /clients/<id>/reports/<id>/canva/<sacs|tcc>  POST → async Canva export
  GET  /api/clients/<id>/last-report                  → JSON last report
  GET  /api/age?dob=YYYY-MM-DD                        → JSON age calculation

Configuration is loaded from config.Config (reads .env via python-dotenv).
"""
import io
import logging
from datetime import date, datetime

from flask import (
    Flask, abort, flash, jsonify, redirect,
    render_template, request, send_file, url_for,
)

import database as db
import canva as canva_api
from canva import CanvaExportError
from config import Config
from pdf_sacs import generate_sacs_pdf
from pdf_tcc import generate_tcc_pdf

# ── Module-level constants ────────────────────────────────────────────────────

ACCOUNT_TYPES = [
    "Checking", "Savings", "Money Market",
    "Roth IRA", "IRA", "401(k)", "403(b)", "SEP IRA",
    "Brokerage", "Joint Brokerage", "FICA",
    "Trust",
    "Liability",
]

QUARTERS = [1, 2, 3, 4]

_LOG = logging.getLogger(__name__)


# ── Module-level helpers ──────────────────────────────────────────────────────

def _parse_float(val, default: float = 0.0) -> float:
    """Parse a currency string ('$1,234.56') or number into a float."""
    try:
        return float(str(val).replace(",", "").replace("$", "").strip() or default)
    except (ValueError, TypeError):
        return default


def _age_from_dob(dob_str: str) -> int | None:
    """Return age in whole years for an ISO or US-formatted date string."""
    if not dob_str:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            dob = datetime.strptime(dob_str, fmt).date()
            today = date.today()
            return today.year - dob.year - (
                (today.month, today.day) < (dob.month, dob.day)
            )
        except ValueError:
            continue
    return None


def _current_quarter() -> int:
    return (date.today().month - 1) // 3 + 1


def _pdf_filename(kind: str, client, report) -> str:
    safe = client["display_name"].replace(" ", "_")
    return f"{kind}_{safe}_Q{report['quarter']}_{report['year']}.pdf"


def _client_data_from_form(form) -> dict:
    return {
        "display_name":          form.get("display_name", "").strip(),
        "client1_first":         form.get("client1_first", "").strip(),
        "client1_last":          form.get("client1_last", "").strip(),
        "client1_dob":           form.get("client1_dob", ""),
        "client1_ssn4":          form.get("client1_ssn4", "").strip(),
        "client2_first":         form.get("client2_first", "").strip(),
        "client2_last":          form.get("client2_last", "").strip(),
        "client2_dob":           form.get("client2_dob", ""),
        "client2_ssn4":          form.get("client2_ssn4", "").strip(),
        "is_married":            1 if form.get("is_married") else 0,
        "client1_salary":        _parse_float(form.get("client1_salary")),
        "client2_salary":        _parse_float(form.get("client2_salary")),
        "monthly_expenses":      _parse_float(form.get("monthly_expenses")),
        "insurance_deductibles": _parse_float(form.get("insurance_deductibles")),
        "notes":                 form.get("notes", ""),
    }


def _parse_accounts_from_form(form) -> list[dict]:
    accounts, i = [], 0
    while f"accounts[{i}][account_type]" in form:
        acct = {
            "owner":                form.get(f"accounts[{i}][owner]", "client1"),
            "account_type":         form.get(f"accounts[{i}][account_type]", ""),
            "institution":          form.get(f"accounts[{i}][institution]", ""),
            "account_number_last4": form.get(f"accounts[{i}][account_number_last4]", ""),
            "is_retirement":        form.get(f"accounts[{i}][is_retirement]") == "1",
            "is_trust":             form.get(f"accounts[{i}][is_trust]") == "1",
            "is_liability":         form.get(f"accounts[{i}][is_liability]") == "1",
            "liability_rate":       _parse_float(form.get(f"accounts[{i}][liability_rate]")),
        }
        if acct["account_type"]:
            accounts.append(acct)
        i += 1
    return accounts


# ── Application factory ───────────────────────────────────────────────────────

def create_app(cfg: Config | None = None) -> Flask:
    app = Flask(__name__)
    cfg = cfg or Config()

    app.secret_key        = cfg.SECRET_KEY
    app.config["DEBUG"]   = cfg.DEBUG
    app.config["DATABASE_PATH"]  = cfg.DATABASE_PATH
    app.config["CANVA_API_KEY"]  = cfg.CANVA_API_KEY
    app.config["CANVA_ENABLED"]  = bool(cfg.CANVA_API_KEY)

    _configure_logging(app)

    # Initialise DB schema once at startup (idempotent — safe to call repeatedly)
    db.init_db(cfg.DATABASE_PATH)

    _register_routes(app)
    _register_error_handlers(app)

    return app


def _configure_logging(app: Flask) -> None:
    level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    if not app.debug:
        logging.getLogger("werkzeug").setLevel(logging.WARNING)


# ── Routes ────────────────────────────────────────────────────────────────────

def _register_routes(app: Flask) -> None:

    # ── Clients ───────────────────────────────────────────────────────────────

    @app.route("/")
    def index():
        return redirect(url_for("clients_list"))

    @app.route("/clients")
    def clients_list():
        return render_template("clients.html", clients=db.get_all_clients())

    @app.route("/clients/new", methods=["GET", "POST"])
    def client_new():
        if request.method == "POST":
            data = _client_data_from_form(request.form)
            if not data["display_name"] or not data["client1_first"]:
                flash("Display name and primary client name are required.", "danger")
                return render_template("client_form.html", client=data,
                                       accounts=[], account_types=ACCOUNT_TYPES, mode="new")
            client_id = db.create_client(data)
            db.replace_accounts(client_id, _parse_accounts_from_form(request.form))
            flash(f"Client '{data['display_name']}' created successfully.", "success")
            return redirect(url_for("client_detail", client_id=client_id))

        return render_template("client_form.html", client={}, accounts=[],
                               account_types=ACCOUNT_TYPES, mode="new")

    @app.route("/clients/<int:client_id>")
    def client_detail(client_id: int):
        client = db.get_client(client_id) or abort(404)
        return render_template("client_detail.html",
                               client=client,
                               accounts=db.get_accounts(client_id),
                               reports=db.get_reports(client_id))

    @app.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
    def client_edit(client_id: int):
        client = db.get_client(client_id) or abort(404)
        if request.method == "POST":
            data = _client_data_from_form(request.form)
            db.update_client(client_id, data)
            db.replace_accounts(client_id, _parse_accounts_from_form(request.form))
            flash("Client updated.", "success")
            return redirect(url_for("client_detail", client_id=client_id))

        return render_template("client_form.html",
                               client=dict(client),
                               accounts=[dict(a) for a in db.get_accounts(client_id)],
                               account_types=ACCOUNT_TYPES, mode="edit")

    @app.route("/clients/<int:client_id>/delete", methods=["POST"])
    def client_delete(client_id: int):
        client = db.get_client(client_id)
        if client:
            db.delete_client(client_id)
            flash(f"Client '{client['display_name']}' deleted.", "info")
        return redirect(url_for("clients_list"))

    # ── Reports ───────────────────────────────────────────────────────────────

    @app.route("/clients/<int:client_id>/reports")
    def reports_list(client_id: int):
        client = db.get_client(client_id) or abort(404)
        return render_template("report_history.html",
                               client=client, reports=db.get_reports(client_id))

    @app.route("/clients/<int:client_id>/reports/new", methods=["GET", "POST"])
    def report_new(client_id: int):
        client   = db.get_client(client_id) or abort(404)
        accounts = db.get_accounts(client_id)

        if request.method == "POST":
            data = {
                "quarter":                   int(request.form.get("quarter", _current_quarter())),
                "year":                      int(request.form.get("year", date.today().year)),
                "inflow":                    _parse_float(request.form.get("inflow")),
                "outflow":                   _parse_float(request.form.get("outflow")),
                "private_reserve_balance":   _parse_float(request.form.get("private_reserve_balance")),
                "schwab_investment_balance": _parse_float(request.form.get("schwab_investment_balance")),
                "monthly_expenses":          float(client["monthly_expenses"] or 0),
                "insurance_deductibles":     float(client["insurance_deductibles"] or 0),
            }
            if not data["inflow"] or not data["outflow"]:
                flash("Inflow and Outflow are required.", "danger")
            else:
                balances = [
                    {
                        "account_id": acct["id"],
                        "balance":    _parse_float(request.form.get(f"balance_{acct['id']}")),
                        "cash_value": _parse_float(request.form.get(f"cash_value_{acct['id']}")),
                        "as_of_date": request.form.get(f"as_of_date_{acct['id']}", ""),
                        "is_stale":   request.form.get(f"is_stale_{acct['id']}") == "1",
                    }
                    for acct in accounts
                ]
                report_id = db.create_report(client_id, data, balances)
                flash("Report created. Download or export your PDFs below.", "success")
                return redirect(url_for("report_detail",
                                        client_id=client_id, report_id=report_id))

        last_balances = db.get_last_report_balances(client_id)
        last_report   = db.get_last_report(client_id)
        today         = date.today()

        return render_template(
            "report_form.html",
            client=dict(client),
            accounts=[dict(a) for a in accounts],
            last_balances=last_balances,
            last_report=dict(last_report) if last_report else {},
            quarters=QUARTERS,
            current_quarter=_current_quarter(),
            current_year=today.year,
        )

    @app.route("/clients/<int:client_id>/reports/<int:report_id>")
    def report_detail(client_id: int, report_id: int):
        client   = db.get_client(client_id) or abort(404)
        report   = db.get_report(report_id) or abort(404)
        balances = db.get_report_balances(report_id)
        totals   = db.calc_tcc_totals(balances)
        return render_template("report_detail.html",
                               client=dict(client),
                               report=dict(report),
                               balances=[dict(b) for b in balances],
                               totals=totals,
                               canva_enabled=app.config["CANVA_ENABLED"])

    # ── PDF downloads ─────────────────────────────────────────────────────────

    @app.route("/clients/<int:client_id>/reports/<int:report_id>/sacs.pdf")
    def download_sacs(client_id: int, report_id: int):
        client = db.get_client(client_id) or abort(404)
        report = db.get_report(report_id) or abort(404)
        pdf    = generate_sacs_pdf(dict(client), dict(report))
        return send_file(io.BytesIO(pdf), mimetype="application/pdf",
                         as_attachment=True,
                         download_name=_pdf_filename("SACS", client, report))

    @app.route("/clients/<int:client_id>/reports/<int:report_id>/tcc.pdf")
    def download_tcc(client_id: int, report_id: int):
        client   = db.get_client(client_id) or abort(404)
        report   = db.get_report(report_id) or abort(404)
        balances = db.get_report_balances(report_id)
        pdf      = generate_tcc_pdf(dict(client), dict(report), [dict(b) for b in balances])
        return send_file(io.BytesIO(pdf), mimetype="application/pdf",
                         as_attachment=True,
                         download_name=_pdf_filename("TCC", client, report))

    # ── Canva export (called via fetch() from the report detail page) ─────────

    @app.route(
        "/clients/<int:client_id>/reports/<int:report_id>/canva/<string:report_type>",
        methods=["POST"],
    )
    def export_to_canva(client_id: int, report_id: int, report_type: str):
        """
        Generate the requested PDF and upload it to Canva as an editable design.
        Returns JSON: {"edit_url": "..."} on success, {"error": "..."} on failure.
        """
        if not app.config["CANVA_ENABLED"]:
            return jsonify({"error": "Canva export is not configured on this server."}), 503

        if report_type not in ("sacs", "tcc"):
            abort(400)

        client   = db.get_client(client_id) or abort(404)
        report   = db.get_report(report_id) or abort(404)
        balances = db.get_report_balances(report_id)
        label    = f"Q{report['quarter']} {report['year']} – {client['display_name']}"

        try:
            if report_type == "sacs":
                pdf  = generate_sacs_pdf(dict(client), dict(report))
                name = f"SACS – {label}"
            else:
                pdf  = generate_tcc_pdf(dict(client), dict(report), [dict(b) for b in balances])
                name = f"TCC – {label}"

            edit_url = canva_api.import_pdf_as_design(
                pdf, name, app.config["CANVA_API_KEY"]
            )
            return jsonify({"edit_url": edit_url})

        except CanvaExportError as exc:
            _LOG.warning("Canva export error: %s", exc)
            return jsonify({"error": str(exc)}), 502
        except Exception:
            _LOG.exception("Unexpected error during Canva export")
            return jsonify({"error": "An unexpected error occurred. Please try again."}), 500

    # ── Utility API ───────────────────────────────────────────────────────────

    @app.route("/api/clients/<int:client_id>/last-report")
    def api_last_report(client_id: int):
        report = db.get_last_report(client_id)
        return jsonify(dict(report) if report else {})

    @app.route("/api/age")
    def api_age():
        """Return age in years for a given ISO date-of-birth (?dob=YYYY-MM-DD)."""
        return jsonify({"age": _age_from_dob(request.args.get("dob", ""))})


# ── Error handlers ────────────────────────────────────────────────────────────

def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        _LOG.exception("500 error: %s", e)
        return render_template("errors/500.html"), 500


# ── Application instance ──────────────────────────────────────────────────────
# Used by `py app.py` for local dev. Production uses wsgi.py instead.

app = create_app()

if __name__ == "__main__":
    cfg = Config()
    app.run(debug=cfg.DEBUG, port=cfg.PORT, host="0.0.0.0")
