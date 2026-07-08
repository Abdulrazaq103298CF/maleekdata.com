import os
import random
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "b3afca732a1e4c769e5d9f023812") 

# --- FLASK LOGIN CONFIGURATION ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"  
login_manager.login_message_category = "error"

class User(UserMixin):
    def __init__(self, user_id, username, wallet_balance, acc_num, assigned_bank):
        self.id = user_id
        self.username = username
        self.wallet_balance = wallet_balance
        self.acc_num = acc_num
        self.assigned_bank = assigned_bank

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    user_record = conn.execute(
        "SELECT id, username, wallet_balance, acc_num, assigned_bank FROM users WHERE id = ?", 
        (user_id,)
    ).fetchone()
    conn.close()
    if user_record:
        return User(
            user_id=user_record["id"], 
            username=user_record["username"], 
            wallet_balance=user_record["wallet_balance"],
            acc_num=user_record["acc_num"],
            assigned_bank=user_record["assigned_bank"]
        )
    return None

# --- DATABASE ENGINE MANAGEMENT ---
def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            gender TEXT,
            wallet_balance REAL DEFAULT 0.0,
            acc_num TEXT,
            assigned_bank TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- SYSTEM RENDERING AND AUTH ROUTING ---

@app.route("/")
def home():
    if current_user.is_authenticated:
        conn = get_db_connection()
        live_record = conn.execute("SELECT wallet_balance FROM users WHERE id = ?", (current_user.id,)).fetchone()
        conn.close()
        
        current_balance = live_record["wallet_balance"] if live_record else current_user.wallet_balance
        
        user_data = {
            "username": current_user.username.upper(),       
            "balance": current_balance,  
            "account_number": current_user.acc_num,  
            "assigned_bank": current_user.assigned_bank  
        }
    else:
        # Crucial fallback dict to stop the 'user_details is undefined' crash
        user_data = {
            "username": "GUEST",
            "balance": 0.00,
            "account_number": "0000000000",
            "assigned_bank": "No Node Configured"
        }
        
    return render_template("intro.html", user_details=user_data)

@app.route("/register_page")
def register_page():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        full_name = request.form.get("regName")
        user_name = request.form.get("regUser", "").strip()
        email_addr = request.form.get("regEmail")
        gender_sel = request.form.get("regGender")
        raw_password = request.form.get("regPass")
        
        if not all([full_name, user_name, email_addr, raw_password]):
            flash("All form fields must be completely filled out!", "error")
            return redirect(url_for("register_page"))
        
        hashed_pwd = generate_password_hash(raw_password, method='pbkdf2:sha256', salt_length=16)
        
        generated_acc = str(random.randint(6110000000, 6999999999))
        mock_bank = "PalmPay"
        initial_balance = 5000.00  
        
        conn = get_db_connection()
        try:
            conn.execute(
                """INSERT INTO users (name, email, username, password, gender, wallet_balance, acc_num, assigned_bank) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                (full_name, email_addr, user_name, hashed_pwd, gender_sel, initial_balance, generated_acc, mock_bank)
            )
            conn.commit()
            flash("Registration Successful! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username or Email address already taken!", "error")
            return redirect(url_for("register_page"))
        finally:
            conn.close()
            
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
        
    if request.method == "POST":
        user_name = request.form.get("Username", "").strip()
        raw_password = request.form.get("password")
        
        conn = get_db_connection()
        user_record = conn.execute("SELECT * FROM users WHERE username = ?", (user_name,)).fetchone()
        conn.close()
        
        if user_record and check_password_hash(user_record["password"], raw_password):
            user_obj = User(
                user_id=user_record["id"], 
                username=user_record["username"],
                wallet_balance=user_record["wallet_balance"],
                acc_num=user_record["acc_num"],
                assigned_bank=user_record["assigned_bank"]
            )
            login_user(user_obj)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid Merchant Username or Password Configuration.", "error")
            return redirect(url_for("login"))
            
    return render_template("login.html")

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        user_name = request.form.get("Username", "").strip()
        new_pwd = request.form.get("new_password")

        conn = get_db_connection()
        user_record = conn.execute("SELECT * FROM users WHERE username = ?", (user_name,)).fetchone()

        if user_record:
            hashed_new_pwd = generate_password_hash(new_pwd, method='pbkdf2:sha256', salt_length=16)
            conn.execute("UPDATE users SET password = ? WHERE username = ?", (hashed_new_pwd, user_name))
            conn.commit()
            conn.close()
            flash("Password updated successfully!", "success")
            return redirect(url_for("login"))
        else:
            conn.close()
            flash("Username not found.", "error")
            return redirect(url_for("forgot_password"))

    return render_template("forgot_password.html")

# --- USER MERCHANDISE INTERFACE ---
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    live_record = conn.execute("SELECT wallet_balance FROM users WHERE id = ?", (current_user.id,)).fetchone()
    conn.close()
    
    current_balance = live_record["wallet_balance"] if live_record else current_user.wallet_balance

    user_data = {
        "username": current_user.username.upper(),       
        "balance": current_balance,  
        "account_number": current_user.acc_num,  
        "assigned_bank": current_user.assigned_bank  
    }
    return render_template('dashboard.html', user_details=user_data)

@app.route("/process_vtu", methods=["POST"])
@login_required
def process_vtu():
    service_type = request.form.get("serviceType") 
    amount = float(request.form.get("amount", 0.0))
    target_num = request.form.get("recipientNumber")
    
    conn = get_db_connection()
    user_record = conn.execute("SELECT wallet_balance FROM users WHERE id = ?", (current_user.id,)).fetchone()
    
    if user_record and user_record["wallet_balance"] >= amount:
        new_balance = user_record["wallet_balance"] - amount
        conn.execute("UPDATE users SET wallet_balance = ? WHERE id = ?", (new_balance, current_user.id))
        conn.commit()
        conn.close()
        flash(f"Successfully processed {service_type} transaction to {target_num} for ₦{amount:,.2f}", "success")
    else:
        conn.close()
        flash("Insufficient funds in your merchant wallet balance!", "error")
        
    return redirect(url_for("dashboard"))

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have successfully signed out of the session environment.", "success")
    return redirect(url_for("home"))

if __name__ == "__main__":
    # Fully bound to all local interfaces on network port 5000
    app.run(host="0.0.0.0", port=5000, debug=True)