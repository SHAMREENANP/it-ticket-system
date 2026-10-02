import os
import sqlite3
from functools import wraps

from flask import (
    Flask, abort, flash, g, redirect, render_template,
    request, session, url_for
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-development-key")
DATABASE = os.path.join(app.root_path, "tickets.db")

STATUSES = ["Pending", "In Progress", "Complete", "Cancelled"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.commit()


@app.before_request
def setup_database():
    init_db()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Please sign in as an administrator.")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def home():
    return redirect(url_for("new_ticket"))


@app.route("/ticket/new", methods=["GET", "POST"])
def new_ticket():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()

        if not all([name, email, title, description]):
            flash("Please complete every field.")
        else:
            db = get_db()
            cursor = db.execute(
                """INSERT INTO tickets (name, email, title, description)
                   VALUES (?, ?, ?, ?)""",
                (name, email, title, description),
            )
            db.commit()
            flash(f"Ticket #{cursor.lastrowid} was submitted.")
            return redirect(url_for("my_tickets", email=email))

    return render_template("new_ticket.html")


@app.route("/tickets")
def my_tickets():
    email = request.args.get("email", "").strip()
    tickets = []

    if email:
        tickets = get_db().execute(
            "SELECT * FROM tickets WHERE email = ? ORDER BY id DESC",
            (email,),
        ).fetchall()

    return render_template("my_tickets.html", tickets=tickets, email=email)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD", "admin@123")

        if (
            request.form.get("username") == username
            and request.form.get("password") == password
        ):
            session["is_admin"] = True
            return redirect(url_for("admin_dashboard"))

        flash("Incorrect username or password.")

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@admin_required
def admin_dashboard():
    tickets = get_db().execute(
        "SELECT * FROM tickets ORDER BY id DESC"
    ).fetchall()
    return render_template(
        "admin_dashboard.html", tickets=tickets, statuses=STATUSES
    )


@app.route("/admin/ticket/<int:ticket_id>/status", methods=["POST"])
@admin_required
def update_status(ticket_id):
    status = request.form.get("status")

    if status not in STATUSES:
        abort(400)

    db = get_db()
    result = db.execute(
        "UPDATE tickets SET status = ? WHERE id = ?",
        (status, ticket_id),
    )
    db.commit()

    if result.rowcount == 0:
        abort(404)

    flash(f"Ticket #{ticket_id} updated to {status}.")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    app.run(debug=True)