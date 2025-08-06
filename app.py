# Import the necessary modules from the Flask framework, psycopg2, os, random, and time
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import psycopg2
import os
import random
import time
from datetime import datetime

# Create a Flask web application instance
app = Flask(__name__)
# Add a secret key for session management, required for flash messages
app.secret_key = os.urandom(24)

# --- PostgreSQL Database Configuration ---
# IMPORTANT: Replace these with your actual PostgreSQL credentials


# ...
DB_HOST = os.environ.get("DB_HOST", "dpg-d29jgt2dbo4c73bjuusg-a")
DB_NAME = os.environ.get("DB_NAME", "siwan_college_db")
DB_USER = os.environ.get("DB_USER", "rawnac")
DB_PASS = os.environ.get("DB_PASS", "cTjPKesw12R0ntRWEaNdtsdTnTLBa8kn")
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24)) # Get from env or generate
# ...

# In-memory storage for OTPs (for demonstration purposes)
# In a real application, you would use a database with an expiration timestamp
otp_storage = {}

def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        return conn
    except psycopg2.OperationalError as e:
        print(f"Database connection failed: {e}")
        return None

def setup_database():
    """
    Sets up the initial database tables: users and students_data.
    This function is for demonstration purposes.
    """
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        try:
            # Create the users table if it doesn't exist, and add 'role' and 'is_approved' columns
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    role VARCHAR(10) NOT NULL DEFAULT 'student',
                    is_approved BOOLEAN DEFAULT FALSE -- NEW: Approval status for accounts
                );
            """)

            # Create the students_data table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS students_data (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    full_name VARCHAR(100),
                    father_name VARCHAR(100),
                    registration_number VARCHAR(20) UNIQUE,
                    roll_number VARCHAR(20) UNIQUE,
                    mobile_number VARCHAR(15) UNIQUE,
                    session VARCHAR(20), -- This column will store "YYYY-YYYY"
                    address TEXT
                );
            """)
            conn.commit() # Commit after table creation to ensure it exists for subsequent checks

            # Check if 'session' column exists in students_data, if not, add it
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='students_data' AND column_name='session';")
            if not cursor.fetchone():
                print("Adding 'session' column to students_data table...")
                cursor.execute("ALTER TABLE students_data ADD COLUMN session VARCHAR(20);")
                conn.commit()
                print("'session' column added.")
            
            # Check if 'is_approved' column exists in users, if not, add it
            cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users' AND column_name='is_approved';")
            if not cursor.fetchone():
                print("Adding 'is_approved' column to users table...")
                cursor.execute("ALTER TABLE users ADD COLUMN is_approved BOOLEAN DEFAULT FALSE;")
                conn.commit()
                print("'is_approved' column added.")


            # Check if a default admin user exists and insert one if not
            cursor.execute("SELECT * FROM users WHERE username = 'admin'")
            if not cursor.fetchone():
                # Default admin should be approved immediately
                cursor.execute("INSERT INTO users (username, password, role, is_approved) VALUES (%s, %s, %s, %s);", ('rawnac', 'rawnac@22105123021', 'admin', True))
                print("Default admin user 'admin' with password 'password' created and approved.")
            
          
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"An error occurred during database setup: {e}")
        finally:
            cursor.close()
            conn.close()

@app.route('/')
def index():
    """
    Redirects logged-in users to their respective dashboards or to the login page.
    """
    if 'username' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Handles the login page, displaying the form and processing form submissions.
    """
    if 'username' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
            
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        captcha_solution_submitted = request.form.get('captcha')
        
        # Get from_year and to_year for session from form
        from_year = request.form.get('from_year')
        to_year = request.form.get('to_year')
        
        login_session_string = None
        if from_year and to_year:
            # Basic validation for year format (numeric)
            if from_year.isdigit() and to_year.isdigit():
                login_session_string = f"{from_year}-{to_year}"
            else:
                flash("Invalid year format for session. Please select numeric years.", "error")
                num1 = random.randint(1, 9)
                num2 = random.randint(1, 9)
                captcha_text = f"{num1} + {num2}"
                session['captcha_solution'] = str(num1 + num2)
                return render_template('login.html', captcha_text=captcha_text, selected_from_year=from_year, selected_to_year=to_year)


        if captcha_solution_submitted != session.get('captcha_solution'):
            flash("Incorrect captcha. Please try again.", "error")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            # Pass back the selected years to repopulate the dropdowns
            return render_template('login.html', captcha_text=captcha_text, selected_from_year=from_year, selected_to_year=to_year)

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "error")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            return render_template('login.html', captcha_text=captcha_text, selected_from_year=from_year, selected_to_year=to_year)

        cursor = conn.cursor()
        try:
            # First, verify username and password, and fetch is_approved status
            cursor.execute("SELECT id, username, role, is_approved FROM users WHERE username = %s AND password = %s", (username, password))
            user = cursor.fetchone()

            if user:
                user_id, username, role, is_approved = user # NEW: Get is_approved
                
                if role == 'student':
                    # For students, session selection is mandatory and must be verified
                    if not from_year or not to_year:
                        flash("Session (From Year and To Year) is mandatory for student login.", "error")
                        num1 = random.randint(1, 9)
                        num2 = random.randint(1, 9)
                        captcha_text = f"{num1} + {num2}"
                        session['captcha_solution'] = str(num1 + num2)
                        return render_template('login.html', captcha_text=captcha_text, selected_from_year=from_year, selected_to_year=to_year)
                    
                    # Check if the account is approved
                    if not is_approved: # NEW: Check approval status
                        flash("Your account is pending administrator approval. Please try again after approval.", "error")
                        num1 = random.randint(1, 9)
                        num2 = random.randint(1, 9)
                        captcha_text = f"{num1} + {num2}"
                        session['captcha_solution'] = str(num1 + num2)
                        return render_template('login.html', captcha_text=captcha_text, selected_from_year=from_year, selected_to_year=to_year)

                    cursor.execute("SELECT session FROM students_data WHERE user_id = %s", (user_id,))
                    student_session_data = cursor.fetchone()

                    if student_session_data and student_session_data[0] == login_session_string:
                        # Session matches, proceed with login
                        session['user_id'] = user_id
                        session['username'] = username
                        session['role'] = role
                        session['is_approved'] = is_approved # NEW: Store approval status in session
                        flash("Login successful!", "success")
                        return redirect(url_for('student_dashboard'))
                    else:
                        flash("Invalid session for this student.", "error")
                        num1 = random.randint(1, 9)
                        num2 = random.randint(1, 9)
                        captcha_text = f"{num1} + {num2}"
                        session['captcha_solution'] = str(num1 + num2)
                        return render_template('login.html', captcha_text=captcha_text, selected_from_year=from_year, selected_to_year=to_year)
                
                elif role == 'admin':
                    # For admins, session is not mandatory, log them in directly
                    session['user_id'] = user_id
                    session['username'] = username
                    session['role'] = role
                    session['is_approved'] = is_approved # NEW: Store approval status in session
                    flash("Admin login successful!", "success")
                    return redirect(url_for('admin_dashboard'))
            else:
                flash("Invalid username or password.", "error")
                num1 = random.randint(1, 9)
                num2 = random.randint(1, 9)
                captcha_text = f"{num1} + {num2}"
                session['captcha_solution'] = str(num1 + num2)
                return render_template('login.html', captcha_text=captcha_text, selected_from_year=from_year, selected_to_year=to_year)

        except Exception as e:
            flash("An error occurred during login. Please try again.", "error")
            print(f"Login error: {e}")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            return render_template('login.html', captcha_text=captcha_text, selected_from_year=from_year, selected_to_year=to_year)
        finally:
            cursor.close()
            conn.close()

    # Initial GET request for login page
    num1 = random.randint(1, 9)
    num2 = random.randint(1, 9)
    captcha_text = f"{num1} + {num2}"
    session['captcha_solution'] = str(num1 + num2)
    # Default selected years (optional, can be empty)
    current_year = datetime.now().year
    return render_template('login.html', captcha_text=captcha_text, 
                           selected_from_year=str(current_year), selected_to_year=str(current_year + 4))


@app.route('/logout')
def logout():
    """
    Logs the user out and clears the session.
    """
    session.pop('user_id', None)
    session.pop('username', None)
    session.pop('role', None)
    session.pop('is_approved', None) # NEW: Clear approval status from session
    flash("You have been logged out.", "success")
    return redirect(url_for('login'))

# NEW: Route to check username availability
@app.route('/check_username', methods=['POST'])
def check_username():
    username = request.json.get('username')
    conn = get_db_connection()
    if conn is None:
        return jsonify(exists=False, error="Database connection error"), 500 # Return 500 for server error

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        exists = cursor.fetchone() is not None
        return jsonify(exists=exists)
    except Exception as e:
        print(f"Error checking username: {e}")
        return jsonify(exists=False, error="An error occurred"), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Handles the registration page, displaying the form and processing new user creation.
    """
    if 'username' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
            
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        father_name = request.form.get('father_name')
        registration_number = request.form.get('registration_number')
        roll_number = request.form.get('roll_number')
        mobile_number = request.form.get('mobile_number')
        
        # Get from_year and to_year from form
        from_year = request.form.get('from_year')
        to_year = request.form.get('to_year')
        
        # --- UPDATED SESSION VALIDATION ---
        if not (from_year and to_year and from_year.isdigit() and to_year.isdigit()):
            flash("Invalid session format. Please select valid numeric 'From Year' and 'To Year'.", "error")
            return render_template('register.html', selected_from_year=from_year, selected_to_year=to_year)
        
        # Ensure 'To Year' is strictly greater than 'From Year'
        if int(to_year) <= int(from_year):
            flash("Invalid session. 'To Year' must be greater than 'From Year'.", "error")
            return render_template('register.html', selected_from_year=from_year, selected_to_year=to_year)
        # --- END UPDATED SESSION VALIDATION ---
            
        session_string = f"{from_year}-{to_year}" # Construct the session string
        address = request.form.get('address')

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "error")
            return render_template('register.html', selected_from_year=from_year, selected_to_year=to_year)

        cursor = conn.cursor()
        try:
            # Re-check username here to be safe, though client-side helps UX
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            if cursor.fetchone():
                flash("Username already exists. Please choose a different one.", "error")
                return render_template('register.html', selected_from_year=from_year, selected_to_year=to_year)

            cursor.execute("SELECT * FROM students_data WHERE registration_number = %s", (registration_number,))
            if cursor.fetchone():
                flash("Registration number already exists. Please check your input.", "error")
                return render_template('register.html', selected_from_year=from_year, selected_to_year=to_year)
            
            cursor.execute("SELECT * FROM students_data WHERE roll_number = %s", (roll_number,))
            if cursor.fetchone():
                flash("Roll number already exists. Please check your input.", "error")
                return render_template('register.html', selected_from_year=from_year, selected_to_year=to_year)

            cursor.execute("SELECT * FROM students_data WHERE mobile_number = %s", (mobile_number,))
            if cursor.fetchone():
                flash("Mobile number already exists. Please check your input.", "error")
                return render_template('register.html', selected_from_year=from_year, selected_to_year=to_year)

            # NEW: Set is_approved to FALSE by default for new registrations
            cursor.execute("INSERT INTO users (username, password, role, is_approved) VALUES (%s, %s, %s, FALSE) RETURNING id;", (username, password, 'student'))
            user_id = cursor.fetchone()[0]

            cursor.execute("INSERT INTO students_data (user_id, full_name, father_name, registration_number, roll_number, mobile_number, session, address) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                           (user_id, full_name, father_name, registration_number, roll_number, mobile_number, session_string, address))

            conn.commit()
            flash("Registration successful! Your account is pending administrator approval. You will be able to log in once approved.", "success")
            return redirect(url_for('login'))

        except Exception as e:
            conn.rollback()
            flash("An error occurred during registration. Please try again.", "error")
            print(f"Registration error: {e}")
            return render_template('register.html', selected_from_year=from_year, selected_to_year=to_year)
        finally:
            cursor.close()
            conn.close()
    
    # Initial GET request for register page
    current_year = datetime.now().year
    # Set default values for the dropdowns (e.g., current year and current year + 4 for a 4-year program)
    return render_template('register.html', selected_from_year=str(current_year), selected_to_year=str(current_year + 4))


@app.route('/otp-login', methods=['GET', 'POST'])
def otp_login():
    """
    Handles the OTP login page.
    GET: Displays form to enter username for OTP.
    POST: Processes username, generates OTP, and displays form to enter OTP.
    """
    if 'username' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
            
    if request.method == 'POST':
        username = request.form.get('username')
        captcha_solution_submitted = request.form.get('captcha')

        if captcha_solution_submitted != session.get('captcha_solution'):
            flash("Incorrect captcha. Please try again.", "error")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            return render_template('otp_login.html', captcha_text=captcha_text)

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "error")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            return render_template('otp_login.html', captcha_text=captcha_text)

        cursor = conn.cursor()
        try:
            # Fetch is_approved status here as well for OTP login
            cursor.execute("""
                SELECT sd.mobile_number, u.id, u.username, u.role, u.is_approved
                FROM users u
                JOIN students_data sd ON u.id = sd.user_id
                WHERE u.username = %s
            """, (username,))
            user_data = cursor.fetchone()

            if user_data:
                mobile_number = user_data[0]
                user_id, username, role, is_approved = user_data[1], user_data[2], user_data[3], user_data[4] # NEW: Get is_approved
                last_four_digits = mobile_number[-4:]

                # Check if the account is approved before sending OTP
                if not is_approved: # NEW: Check approval status
                    flash("Your account is pending administrator approval. You cannot log in via OTP until approved.", "error")
                    num1 = random.randint(1, 9)
                    num2 = random.randint(1, 9)
                    captcha_text = f"{num1} + {num2}"
                    session['captcha_solution'] = str(num1 + num2)
                    return render_template('otp_login.html', captcha_text=captcha_text)

                otp = str(random.randint(1000, 9999))
                otp_storage[username] = {'otp': otp, 'expires_at': time.time() + 300, 'mobile_number': mobile_number}
                print(f"--- OTP for mobile number {mobile_number}: {otp} ---")
                
                flash(f"An OTP has been sent to the mobile number ending in ****{last_four_digits}.", "success")
                
                return render_template('otp_login.html', username_for_otp=username, last_four_digits=last_four_digits)
            else:
                flash("Username not found. Please try again.", "error")
                num1 = random.randint(1, 9)
                num2 = random.randint(1, 9)
                captcha_text = f"{num1} + {num2}"
                session['captcha_solution'] = str(num1 + num2)
                return render_template('otp_login.html', captcha_text=captcha_text)
        except Exception as e:
            flash("An error occurred while requesting OTP. Please try again.", "error")
            print(f"OTP request error: {e}")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            return render_template('otp_login.html', captcha_text=captcha_text)
        finally:
            cursor.close()
            conn.close()

    num1 = random.randint(1, 9)
    num2 = random.randint(1, 9)
    captcha_text = f"{num1} + {num2}"
    session['captcha_solution'] = str(num1 + num2)
    return render_template('otp_login.html', captcha_text=captcha_text)

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    """
    Verifies the OTP submitted by the user.
    """
    username = request.form.get('username')
    otp_entered = request.form.get('otp')
    
    if username in otp_storage:
        stored_otp_data = otp_storage[username]
        if stored_otp_data['otp'] == otp_entered and time.time() < stored_otp_data['expires_at']:
            conn = get_db_connection()
            if conn is None:
                flash("Database connection error. Please try again later.", "error")
                return redirect(url_for('otp_login'))

            cursor = conn.cursor()
            try:
                # Fetch is_approved status here as well for OTP verification
                cursor.execute("SELECT id, username, role, is_approved FROM users WHERE username = %s", (username,))
                user = cursor.fetchone()
                if user:
                    user_id, username, role, is_approved = user # NEW: Get is_approved
                    
                    if not is_approved: # NEW: Double check approval status
                        flash("Your account is pending administrator approval. Please try again after approval.", "error")
                        return redirect(url_for('otp_login'))

                    session['user_id'] = user_id
                    session['username'] = username
                    session['role'] = role
                    session['is_approved'] = is_approved # NEW: Store approval status in session
                    del otp_storage[username]
                    flash("Login successful via OTP!", "success")
                    if role == 'admin':
                        return redirect(url_for('admin_dashboard'))
                    else:
                        return redirect(url_for('student_dashboard'))
                else:
                    flash("An error occurred during OTP login.", "error")
                    return redirect(url_for('otp_login'))
            except Exception as e:
                flash("An error occurred during OTP login.", "error")
                print(f"OTP verification error: {e}")
                return redirect(url_for('otp_login'))
            finally:
                cursor.close()
                conn.close()
        else:
            flash("Invalid or expired OTP. Please try again.", "error")
            if username in otp_storage and time.time() >= otp_storage[username]['expires_at']:
                del otp_storage[username]
            
            return render_template('otp_login.html', username_for_otp=username, last_four_digits=stored_otp_data.get('mobile_number', '0000')[-4:])
    else:
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for('otp_login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """
    Displays the forgot password page and handles the request to send OTP.
    """
    if 'username' in session:
        if session['role'] == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        captcha_solution_submitted = request.form.get('captcha')

        if captcha_solution_submitted != session.get('captcha_solution'):
            flash("Incorrect captcha. Please try again.", "error")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            return render_template('forgot_password.html', captcha_text=captcha_text)

        conn = get_db_connection()
        if conn is None:
            flash("Database connection error. Please try again later.", "error")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            return render_template('forgot_password.html', captcha_text=captcha_text)

        cursor = conn.cursor()
        try:
            # Fetch is_approved status here as well for forgot password
            cursor.execute("""
                SELECT sd.mobile_number, u.is_approved FROM users u
                JOIN students_data sd ON u.id = sd.user_id
                WHERE u.username = %s
            """, (username,))
            user_data = cursor.fetchone()

            if user_data:
                mobile_number, is_approved = user_data[0], user_data[1] # NEW: Get is_approved
                last_four_digits = mobile_number[-4:]

                # Prevent password reset for unapproved accounts
                if not is_approved: # NEW: Check approval status
                    flash("Your account is pending administrator approval. Password reset is not available until approved.", "error")
                    num1 = random.randint(1, 9)
                    num2 = random.randint(1, 9)
                    captcha_text = f"{num1} + {num2}"
                    session['captcha_solution'] = str(num1 + num2)
                    return render_template('forgot_password.html', captcha_text=captcha_text)

                otp = str(random.randint(1000, 9999))
                otp_storage[username] = {'otp': otp, 'expires_at': time.time() + 300, 'mobile_number': mobile_number}
                print(f"--- Password Reset OTP for {username} on mobile number {mobile_number}: {otp} ---")
                
                flash(f"An OTP has been sent to the mobile number ending in ****{last_four_digits}.", "success")
                
                return render_template('forgot_password.html', username_for_reset=username, last_four_digits=last_four_digits)
            else:
                flash("Username not found. Please try again.", "error")
                num1 = random.randint(1, 9)
                num2 = random.randint(1, 9)
                captcha_text = f"{num1} + {num2}"
                session['captcha_solution'] = str(num1 + num2)
                return render_template('forgot_password.html', captcha_text=captcha_text)

        except Exception as e:
            flash("An error occurred. Please try again.", "error")
            print(f"Forgot password error: {e}")
            num1 = random.randint(1, 9)
            num2 = random.randint(1, 9)
            captcha_text = f"{num1} + {num2}"
            session['captcha_solution'] = str(num1 + num2)
            return render_template('forgot_password.html', captcha_text=captcha_text)
        finally:
            cursor.close()
            conn.close()

    num1 = random.randint(1, 9)
    num2 = random.randint(1, 9)
    captcha_text = f"{num1} + {num2}"
    session['captcha_solution'] = str(num1 + num2)
    return render_template('forgot_password.html', captcha_text=captcha_text)

@app.route('/reset-password', methods=['POST'])
def reset_password():
    """
    Handles the password reset form submission.
    """
    username = request.form.get('username')
    otp_entered = request.form.get('otp')
    new_password = request.form.get('new_password')

    if username in otp_storage:
        stored_otp_data = otp_storage[username]
        if stored_otp_data['otp'] == otp_entered and time.time() < stored_otp_data['expires_at']:
            conn = get_db_connection()
            if conn is None:
                flash("Database connection error. Please try again later.", "error")
                return redirect(url_for('forgot_password'))

            cursor = conn.cursor()
            try:
                # Update the password in the database
                cursor.execute("UPDATE users SET password = %s WHERE username = %s", (new_password, username))
                conn.commit()
                del otp_storage[username]
                flash("Password has been reset successfully. You can now log in with your new password.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                conn.rollback()
                flash("An error occurred while resetting the password. Please try again.", "error")
                print(f"Password reset error: {e}")
                return redirect(url_for('forgot_password'))
            finally:
                cursor.close()
                conn.close()
        else:
            flash("Invalid or expired OTP. Please try again.", "error")
            if username in otp_storage and time.time() >= otp_storage[username]['expires_at']:
                del otp_storage[username]
            # Redirect to forgot password page, but with the username pre-populated for a new OTP
            return render_template('forgot_password.html', username_for_reset=username, last_four_digits=stored_otp_data.get('mobile_number', '0000')[-4:])
    else:
        flash("Invalid request. Please try again.", "error")
        return redirect(url_for('forgot_password'))

@app.route('/admin-dashboard')
def admin_dashboard():
    """
    Displays the admin dashboard with a list of all students.
    Only accessible to admin users.
    """
    if 'role' not in session or session['role'] != 'admin':
        flash("Unauthorized access. Please log in as an administrator.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    approved_students_data = []
    pending_students_data = [] # NEW: List for pending students

    if conn:
        cursor = conn.cursor()
        try:
            search_roll = request.args.get('roll_number')
            from_year_filter = request.args.get('from_year_filter')
            to_year_filter = request.args.get('to_year_filter')
            
            filter_session_string = None
            if from_year_filter and to_year_filter:
                if from_year_filter.isdigit() and to_year_filter.isdigit():
                    filter_session_string = f"{from_year_filter}-{to_year_filter}"
                else:
                    flash("Invalid year format for session filter. Please enter numeric years.", "error")

            # Query for APPROVED students
            approved_query = """
                SELECT 
                    sd.full_name, sd.father_name, sd.registration_number, sd.roll_number, sd.mobile_number, sd.session, sd.address
                FROM students_data sd
                JOIN users u ON sd.user_id = u.id
                WHERE u.role = 'student' AND u.is_approved = TRUE
            """
            approved_params = []
            
            if search_roll:
                approved_query += " AND sd.roll_number ILIKE %s"
                approved_params.append(f"%{search_roll}%")
            
            if filter_session_string:
                approved_query += " AND sd.session ILIKE %s"
                approved_params.append(f"%{filter_session_string}%")
            
            cursor.execute(approved_query, approved_params)
            approved_students_data = cursor.fetchall()

            # NEW: Query for PENDING students
            pending_query = """
                SELECT 
                    u.id, u.username, sd.full_name, sd.registration_number, sd.roll_number, sd.session, sd.mobile_number
                FROM students_data sd
                JOIN users u ON sd.user_id = u.id
                WHERE u.role = 'student' AND u.is_approved = FALSE
            """
            # No filtering for pending list for simplicity, but could add if needed
            cursor.execute(pending_query)
            pending_students_data = cursor.fetchall()


        except Exception as e:
            flash("An error occurred while fetching student data.", "error")
            print(f"Error fetching students data: {e}")
        finally:
            cursor.close()
            conn.close()

    return render_template('admin_dashboard.html', 
                           approved_students=approved_students_data, # Pass approved students
                           pending_students=pending_students_data,   # Pass pending students
                           session=session, 
                           search_roll=search_roll, 
                           from_year_filter=from_year_filter, 
                           to_year_filter=to_year_filter)

# NEW: Route to approve a user
@app.route('/approve_user/<int:user_id>', methods=['POST'])
def approve_user(user_id):
    if 'role' not in session or session['role'] != 'admin':
        flash("Unauthorized action.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash("Database connection error. Please try again later.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_approved = TRUE WHERE id = %s AND role = 'student';", (user_id,))
        conn.commit()
        flash("Student account approved successfully!", "success")
    except Exception as e:
        conn.rollback()
        flash("Error approving account.", "error")
        print(f"Error approving user {user_id}: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_dashboard'))

# NEW: Route to reject/delete a user
@app.route('/reject_user/<int:user_id>', methods=['POST'])
def reject_user(user_id):
    if 'role' not in session or session['role'] != 'admin':
        flash("Unauthorized action.", "error")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn is None:
        flash("Database connection error. Please try again later.", "error")
        return redirect(url_for('admin_dashboard'))

    cursor = conn.cursor()
    try:
        # Deleting the user from 'users' table will cascade delete from 'students_data'
        cursor.execute("DELETE FROM users WHERE id = %s AND role = 'student';", (user_id,))
        conn.commit()
        flash("Student account rejected and deleted.", "success")
    except Exception as e:
        conn.rollback()
        flash("Error rejecting account.", "error")
        print(f"Error rejecting user {user_id}: {e}")
    finally:
        cursor.close()
        conn.close()
    return redirect(url_for('admin_dashboard'))


@app.route('/student-dashboard')
def student_dashboard():
    """
    Displays the student dashboard.
    Only accessible to student users.
    """
    if 'role' not in session or session['role'] != 'student':
        flash("Unauthorized access. Please log in as a student.", "error")
        return redirect(url_for('login'))

    # NEW: Check if the student's account is approved
    if not session.get('is_approved'):
        flash("Your account is pending administrator approval. Please wait for approval to access your dashboard features.", "info")
        # You might want to render a different, simpler template here
        # or just show a limited view. For now, we'll let them see the dashboard
        # but with a prominent message.
        return render_template('student_dashboard.html', session=session, pending_approval=True)

    return render_template('student_dashboard.html', session=session, pending_approval=False)

# Run the application if the script is executed directly
if __name__ == '__main__':
    setup_database()
    app.run()