from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "lifeline.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "lifeline-development-secret-key")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS donors (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT NOT NULL,
        age INTEGER NOT NULL,
        gender TEXT,
        blood_group TEXT NOT NULL,
        phone TEXT NOT NULL,
        email TEXT,
        city TEXT NOT NULL,
        state TEXT,
        available INTEGER DEFAULT 1,
        last_donation TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        requester_name TEXT NOT NULL,
        phone TEXT NOT NULL,
        blood_group TEXT NOT NULL,
        units INTEGER NOT NULL DEFAULT 1,
        hospital TEXT NOT NULL,
        city TEXT NOT NULL,
        required_date TEXT,
        message TEXT,
        status TEXT DEFAULT 'Pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit()

    admin = conn.execute("SELECT id FROM users WHERE email=?", ("admin@lifeline.com",)).fetchone()
    if not admin:
        conn.execute(
            "INSERT INTO users(name,email,phone,password,role) VALUES(?,?,?,?,?)",
            ("Administrator", "admin@lifeline.com", "9999999999",
             generate_password_hash("admin123"), "admin")
        )
        conn.commit()
    conn.close()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def home():
    conn = get_db()
    donors = conn.execute("SELECT COUNT(*) c FROM donors WHERE available=1").fetchone()["c"]
    requests = conn.execute("SELECT COUNT(*) c FROM requests WHERE status='Pending'").fetchone()["c"]
    conn.close()
    return render_template("index.html", donors=donors, requests=requests)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        password = request.form["password"]
        conn = get_db()
        try:
            cur = conn.execute(
                "INSERT INTO users(name,email,phone,password) VALUES(?,?,?,?)",
                (name, email, phone, generate_password_hash(password))
            )
            conn.commit()
            session["user_id"] = cur.lastrowid
            session["user_name"] = name
            flash("Registration successful.", "success")
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("An account with this email already exists.", "danger")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["role"] = user["role"]
            return redirect(url_for("admin" if user["role"] == "admin" else "dashboard"))
        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    donor = conn.execute("SELECT * FROM donors WHERE user_id=? ORDER BY id DESC LIMIT 1",
                         (session["user_id"],)).fetchone()
    conn.close()
    return render_template("dashboard.html", donor=donor)

@app.route("/become-donor", methods=["GET", "POST"])
@login_required
def become_donor():
    if request.method == "POST":
        data = (
            session["user_id"], request.form["name"], int(request.form["age"]),
            request.form.get("gender"), request.form["blood_group"],
            request.form["phone"], request.form.get("email"),
            request.form["city"], request.form.get("state"),
            1, request.form.get("last_donation") or None
        )
        conn = get_db()
        conn.execute("""INSERT INTO donors
            (user_id,name,age,gender,blood_group,phone,email,city,state,available,last_donation)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)""", data)
        conn.commit()
        conn.close()
        flash("You are now registered as a blood donor.", "success")
        return redirect(url_for("dashboard"))
    return render_template("donor_form.html")

@app.route("/donors")
def donors():
    conn = get_db()
    blood = request.args.get("blood_group", "")
    city = request.args.get("city", "")
    if blood or city:
        rows = conn.execute("""SELECT * FROM donors
            WHERE available=1 AND (?='' OR blood_group=?)
            AND (?='' OR city LIKE ?)
            ORDER BY name""",
            (blood, blood, city, f"%{city}%")).fetchall()
    else:
        rows = conn.execute("SELECT * FROM donors WHERE available=1 ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("donors.html", donors=rows, blood=blood, city=city)

@app.route("/request-blood", methods=["GET", "POST"])
def request_blood():
    if request.method == "POST":
        conn = get_db()
        conn.execute("""INSERT INTO requests
            (requester_name,phone,blood_group,units,hospital,city,required_date,message)
            VALUES(?,?,?,?,?,?,?,?)""",
            (request.form["requester_name"], request.form["phone"],
             request.form["blood_group"], int(request.form["units"]),
             request.form["hospital"], request.form["city"],
             request.form.get("required_date"), request.form.get("message")))
        conn.commit()
        conn.close()
        flash("Blood request submitted successfully.", "success")
        return redirect(url_for("home"))
    return render_template("request_blood.html")

@app.route("/admin")
@login_required
def admin():
    if session.get("role") != "admin":
        return redirect(url_for("dashboard"))
    conn = get_db()
    donor_rows = conn.execute("SELECT * FROM donors ORDER BY id DESC").fetchall()
    request_rows = conn.execute("SELECT * FROM requests ORDER BY id DESC").fetchall()
    user_count = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    conn.close()
    return render_template("admin.html", donors=donor_rows, requests=request_rows, user_count=user_count)

@app.route("/admin/request/<int:req_id>/<status>", methods=["POST"])
@login_required
def update_request(req_id, status):
    if session.get("role") != "admin" or status not in ("Pending", "Fulfilled", "Cancelled"):
        return jsonify({"error": "Unauthorized"}), 403
    conn = get_db()
    conn.execute("UPDATE requests SET status=? WHERE id=?", (status, req_id))
    conn.commit()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/api/donors")
def api_donors():
    conn = get_db()
    rows = conn.execute("""SELECT id,name,age,gender,blood_group,phone,email,city,state
                           FROM donors WHERE available=1 ORDER BY name""").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
