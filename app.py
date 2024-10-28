import streamlit as st
import sqlite3
import hashlib
import os
import json
import pandas as pd
from datetime import datetime, timedelta
import io
import time
import struct
import re
from partner_records import partner_records_ui, TITLE_OPTIONS, CURRENCIES
from church_records import church_records_ui, fetch_church_partner_records, CONVERSION_RATES, set_display_currency, convert_to_espees
from calendar import month_name
from analytics import analytics_dashboard, fetch_all_partner_records
from record_templates import record_templates_ui
from partner_analytics import partner_analytics_ui
from partner_reports import partner_reports_ui

# Database initialization functions
def init_partner_db():
    """Initialize the partner records database without dropping existing tables"""
    try:
        conn = sqlite3.connect('partner_records.db')
        c = conn.cursor()
        
        # Create tables if they don't exist (preserves existing data)
        tables = {
            'adult_partners': '''CREATE TABLE IF NOT EXISTS adult_partners
                               (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                record_data TEXT NOT NULL,
                                submission_date DATETIME NOT NULL)''',
                                
            'children_partners': '''CREATE TABLE IF NOT EXISTS children_partners
                                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                   record_data TEXT NOT NULL,
                                   submission_date DATETIME NOT NULL)''',
                                   
            'teenager_partners': '''CREATE TABLE IF NOT EXISTS teenager_partners
                                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                   record_data TEXT NOT NULL,
                                   submission_date DATETIME NOT NULL)''',
                                   
            'external_partners': '''CREATE TABLE IF NOT EXISTS external_partners
                                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                                   record_data TEXT NOT NULL,
                                   submission_date DATETIME NOT NULL)'''
        }
        
        # Create each table if it doesn't exist
        for create_statement in tables.values():
            c.execute(create_statement)
        
        # Add any necessary indices for performance
        indices = [
            'CREATE INDEX IF NOT EXISTS idx_adult_submission_date ON adult_partners(submission_date)',
            'CREATE INDEX IF NOT EXISTS idx_children_submission_date ON children_partners(submission_date)',
            'CREATE INDEX IF NOT EXISTS idx_teenager_submission_date ON teenager_partners(submission_date)',
            'CREATE INDEX IF NOT EXISTS idx_external_submission_date ON external_partners(submission_date)'
        ]
        
        for index in indices:
            try:
                c.execute(index)
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e):
                    raise e
        
        conn.commit()
    except Exception as e:
        st.error(f"Error initializing partner database: {e}")
    finally:
        conn.close()

def init_db():
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (username TEXT PRIMARY KEY,
                      password TEXT,
                      full_name TEXT,
                      email TEXT,
                      user_group TEXT,
                      sub_group TEXT,
                      region TEXT,
                      zone TEXT)''')
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"An error occurred while initializing the users database: {e}")
    finally:
        conn.close()

    try:
        conn = sqlite3.connect('reports.db')
        c = conn.cursor()
        # Create reports table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS reports
                     (id TEXT PRIMARY KEY,
                      username TEXT,
                      zone TEXT,
                      year INTEGER,
                      month INTEGER,
                      report_data TEXT,
                      submission_date DATETIME)''')
        
        # Create users table in reports.db if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (username TEXT PRIMARY KEY,
                      full_name TEXT,
                      email TEXT,
                      user_group TEXT,
                      sub_group TEXT,
                      region TEXT,
                      zone TEXT)''')
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"An error occurred while initializing the reports database: {e}")
    finally:
        conn.close()

# Add this function to get record_templates_ui
def get_record_templates_ui():
    from record_templates import record_templates_ui
    return record_templates_ui

# Add these lines at the beginning of the script, after the imports
st.set_page_config(
    page_title="GPD Reporting",  # Changed from "GPD ADMIN"
    page_icon="🏢",
    layout="wide"
)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.is_super_admin = False
    st.session_state.is_regional_manager = False

# Load zones data
try:
    with open('zones_data.json', 'r') as f:
        zones_data = json.load(f)
except FileNotFoundError:
    st.error("zones_data.json file not found")
    zones_data = {}
except json.JSONDecodeError:
    st.error("Invalid JSON in zones_data.json")
    zones_data = {}

# Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# User registration
def register_user(username, password, full_name, email, user_group, sub_group, region, zone):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        hashed_password = hash_password(password)
        c.execute("INSERT INTO users (username, password, full_name, email, user_group, sub_group, region, zone) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (username, hashed_password, full_name, email, user_group, sub_group, region, zone))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    except sqlite3.Error as e:
        st.error(f"An error occurred while registering the user: {e}")
        return False
    finally:
        conn.close()

# User login
def login_user(username, password):
    if username == "admin" and password == "12345":
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.is_super_admin = True
        st.session_state.is_regional_manager = False
        st.session_state.user_group = "GPD"
        st.session_state.sub_group = "Admin"
        return True

    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed_password = hash_password(password)
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    
    if user:
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.is_super_admin = False
        st.session_state.is_regional_manager = user[5] == "Regional Manager"
        st.session_state.region = user[6]
        st.session_state.user_group = user[4]
        st.session_state.sub_group = user[5]
        
        # Add full access flag for reporting/admin users
        st.session_state.has_full_access = (
            user[4] == "GPD" and 
            user[5] == "Reporting/Admin"
        )
        return True
    return False

# New function to fetch all users
def fetch_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username, full_name, email, user_group, sub_group, region, zone FROM users")
    users = c.fetchall()
    conn.close()
    return users

# New function to update user
def update_user(username, full_name, email, user_group, sub_group, region, zone):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("""UPDATE users SET full_name=?, email=?, user_group=?, sub_group=?, region=?, zone=?
                 WHERE username=?""", (full_name, email, user_group, sub_group, region, zone, username))
    conn.commit()
    conn.close()

# New function to delete user
def delete_user(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()

# Update the save_report function to remove the table creation
def save_report(username, zone, year, month, report_data):
    try:
        conn = sqlite3.connect('reports.db')
        c = conn.cursor()
        report_json = json.dumps(report_data)
        report_id = f"{year}-{month:02d}-{username}"

        c.execute("""INSERT INTO reports (id, username, zone, year, month, report_data, submission_date)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (report_id, username, zone, year, month, report_json, datetime.now()))
        conn.commit()
        return True, "Report submitted successfully!"
    except sqlite3.IntegrityError:
        # Update existing report
        c.execute("""UPDATE reports SET zone=?, report_data=?, submission_date=?
                     WHERE id=? AND username=?""",
                  (zone, report_json, datetime.now(), report_id, username))
        conn.commit()
        return True, "Existing report updated successfully!"
    except sqlite3.Error as e:
        return False, f"An error occurred while saving the report: {e}"
    finally:
        conn.close()

# New function to get user details
def get_user_details(username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT user_group, sub_group, region, zone FROM users WHERE username=?", (username,))
    user_details = c.fetchone()
    conn.close()
    return user_details

# New function to fetch reports
def fetch_reports(username=None, region=None):
    conn_reports = sqlite3.connect('reports.db')
    c_reports = conn_reports.cursor()
    if username:
        c_reports.execute("SELECT * FROM reports WHERE username=? ORDER BY id DESC", (username,))
        reports = c_reports.fetchall()
    elif region:
        # Connect to users.db to get usernames in the region
        conn_users = sqlite3.connect('users.db')
        c_users = conn_users.cursor()
        c_users.execute("SELECT username FROM users WHERE region=? AND user_group='RZM'", (region,))
        usernames = [row[0] for row in c_users.fetchall()]
        conn_users.close()
        if usernames:
            placeholders = ', '.join(['?'] * len(usernames))
            query = f"SELECT * FROM reports WHERE username IN ({placeholders}) ORDER BY id DESC"
            c_reports.execute(query, usernames)
            reports = c_reports.fetchall()
        else:
            reports = []
    else:
        c_reports.execute("SELECT * FROM reports ORDER BY id DESC")
        reports = c_reports.fetchall()
    conn_reports.close()
    return reports

# Add this new function to generate time period options
def get_time_period_options():
    current_year = datetime.now().year
    years = list(range(current_year, 2019, -1))
    quarters = ['Q1', 'Q2', 'Q3', 'Q4']
    half_years = ['H1', 'H2']
    months = ['January', 'February', 'March', 'April', 'May', 'June', 
              'July', 'August', 'September', 'October', 'November', 'December']
    
    return {
        'Annual': years,
        'Quarterly': [f"{year} {quarter}" for year in years for quarter in quarters],
        'Half-Year': [f"{year} {half}" for year in years for half in half_years],
        'Monthly': [f"{year} {month}" for year in years for month in months]
    }

# Add this new function to calculate report metrics
def calculate_report_metrics(reports):
    total_reports = len(reports)
    metrics_sum = {}
    for report in reports:
        report_data = json.loads(report[5])  # Assuming report_data is at index 5
        for key, value in report_data.items():
            if key in metrics_sum:
                metrics_sum[key] += int(value)
            else:
                metrics_sum[key] = int(value)
    return total_reports, metrics_sum

# Add these new functions
def request_edit_permission(username, report_id, reason):
    conn = sqlite3.connect('edit_requests.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS edit_requests
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT,
                  report_id TEXT,
                  reason TEXT,
                  status TEXT,
                  request_date DATETIME,
                  expiry_date DATETIME)''')
    c.execute("INSERT INTO edit_requests (username, report_id, reason, status, request_date) VALUES (?, ?, ?, ?, ?)",
              (username, report_id, reason, "Pending", datetime.now()))
    conn.commit()
    conn.close()

def get_edit_requests():
    conn = sqlite3.connect('edit_requests.db')
    c = conn.cursor()
    c.execute("SELECT * FROM edit_requests WHERE status='Pending'")
    requests = c.fetchall()
    conn.close()
    return requests

def update_edit_request(request_id, status, expiry_date=None):
    conn = sqlite3.connect('edit_requests.db')
    c = conn.cursor()
    if expiry_date:
        c.execute("UPDATE edit_requests SET status=?, expiry_date=? WHERE id=?", (status, expiry_date, request_id))
    else:
        c.execute("UPDATE edit_requests SET status=? WHERE id=?", (status, request_id))
    conn.commit()
    conn.close()

def check_edit_permission(username, report_id):
    conn = sqlite3.connect('edit_requests.db')
    c = conn.cursor()
    c.execute("SELECT * FROM edit_requests WHERE username=? AND report_id=? AND status='Approved' AND expiry_date > ?",
              (username, report_id, datetime.now()))
    permission = c.fetchone()
    conn.close()
    return permission is not None

# Add this new function to check if a report already exists
def check_existing_report(username, year, month):
    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    report_id = f"{year}-{month:02d}-{username}"
    c.execute("SELECT * FROM reports WHERE id=?", (report_id,))
    existing_report = c.fetchone()
    conn.close()
    return existing_report is not None

# Add this function to load saved conversion rates
def load_conversion_rates():
    try:
        with open('conversion_rates.json', 'r') as f:
            rates = json.load(f)
            # Update the CONVERSION_RATES in church_records
            for currency, rate in rates.items():
                CONVERSION_RATES[currency] = rate
    except FileNotFoundError:
        # If file doesn't exist, use default rates
        pass
    except Exception as e:
        st.error(f"Error loading conversion rates: {e}")

# Main app
def main():
    try:
        # Create two columns for title and logout button
        col1, col2 = st.columns([0.85, 0.15])
        with col1:
            st.title("GPD Reporting")
        
        if st.session_state.logged_in:
            with col2:
                if st.button("Logout", type="primary"):
                    st.session_state.logged_in = False
                    st.session_state.username = None
                    st.session_state.is_super_admin = False
                    st.session_state.is_regional_manager = False
                    st.session_state.user_group = None
                    st.session_state.sub_group = None
                    st.rerun()
            display_dashboard()
        else:
            display_login_register()
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

def display_login_register():
    # Remove the duplicate title here
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        if st.button("Login"):
            if login_user(username, password):
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid username or password")

    with tab2:
        st.subheader("Register")
        new_username = st.text_input("Username", key="register_username")
        new_password = st.text_input("Password", type="password", key="register_password")
        full_name = st.text_input("Full Name", key="register_full_name")
        email = st.text_input("Email", key="register_email")
        user_group = st.selectbox("User Group", ["Select...", "GPD", "RZM"], key="register_user_group")
        
        sub_group = None
        region = None
        zone = None
        
        if user_group == "GPD":
            sub_group = st.selectbox("Sub Group", ["Select...", "Finance", "IT", "Reporting/Admin", "Admin Manager", "Regional Manager"], key="register_sub_group")
            if sub_group in ["Admin Manager", "Regional Manager"]:
                region = st.selectbox("Region", ["Select..."] + [f"Region {i}" for i in range(1, 7)], key="register_region_gpd")
        elif user_group == "RZM":
            region = st.selectbox("Region", ["Select..."] + list(zones_data.keys()), key="register_region_rzm")
            if region and region != "Select...":
                zone = st.selectbox("Zone", ["Select..."] + zones_data[region], key="register_zone")
        
        if st.button("Register"):
            if user_group == "Select..." or (user_group == "GPD" and sub_group == "Select...") or (user_group == "RZM" and (region == "Select..." or zone == "Select...")):
                st.error("Please select all required fields.")
            elif register_user(new_username, new_password, full_name, email, user_group, sub_group, region, zone):
                st.success("Registration successful! Please login.")
            else:
                st.error("Username already exists")

def display_dashboard():
    if st.session_state.is_super_admin or (
        st.session_state.user_group == "GPD" and 
        st.session_state.sub_group == "IT"
    ):
        # Full admin access for super admin and IT
        display_admin_dashboard(is_full_admin=True)
    elif (
        st.session_state.user_group == "GPD" and 
        st.session_state.sub_group == "Reporting/Admin"
    ):
        # Limited admin access for reporting/admin
        display_admin_dashboard(is_full_admin=False)
    elif st.session_state.is_regional_manager or (
        st.session_state.user_group == "GPD" and 
        st.session_state.sub_group in ["Regional Manager", "Admin Manager"]
    ):
        # Regional manager view for RM and Admin Manager
        display_regional_dashboard(
            is_admin_manager=(
                st.session_state.user_group == "GPD" and 
                st.session_state.sub_group == "Admin Manager"
            )
        )
    else:
        display_user_dashboard()

def display_admin_dashboard(is_full_admin=False):
    st.title("Admin Dashboard")
    
    if is_full_admin:
        # Full admin tabs for super admin and IT
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
            "User Management", 
            "Record Templates", 
            "View Reports",
            "Partner Analytics",
            "Church Analytics",
            "ROR Analytics",
            "Debug Database",
            "Purge Database"
        ])
        
        with tab1:
            user_management_ui()
        
        with tab2:
            record_templates_ui()
        
        with tab3:
            view_reports_ui()
            
        with tab4:
            partner_analytics_ui()
            
        with tab5:
            church_analytics_ui()
            
        with tab6:
            ror_analytics_ui()
            
        with tab7:
            debug_database_ui()
            
        with tab8:
            purge_database_ui()
            
    else:
        # Limited tabs for reporting/admin users
        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
            "RZM Overview",
            "Record Templates", 
            "View Reports",
            "Partner Analytics",
            "Church Analytics",
            "ROR Analytics"
        ])
        
        with tab1:
            display_rzm_overview()
        
        with tab2:
            record_templates_ui()
        
        with tab3:
            view_reports_ui()
            
        with tab4:
            partner_analytics_ui()
            
        with tab5:
            church_analytics_ui()
            
        with tab6:
            ror_analytics_ui()

def display_rzm_overview():
    """Display overview of all RZMs and their zones"""
    st.subheader("RZM Overview")
    
    # Fetch all RZM users
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("""
        SELECT full_name, email, region, zone 
        FROM users 
        WHERE user_group = 'RZM'
        ORDER BY region, zone
    """)
    rzms = c.fetchall()
    conn.close()
    
    if not rzms:
        st.info("No RZMs registered in the system")
        return
    
    # Group RZMs by region
    regions = {}
    for rzm in rzms:
        full_name, email, region, zone = rzm
        if region not in regions:
            regions[region] = []
        regions[region].append({
            'name': full_name,
            'email': email,
            'zone': zone
        })
    
    # Display RZMs by region
    for region, rzm_list in regions.items():
        st.write(f"### {region}")
        
        # Create a DataFrame for this region's RZMs
        df = pd.DataFrame(rzm_list)
        df.columns = ['Name', 'Email', 'Zone']
        
        # Display as a styled table
        st.dataframe(
            df,
            column_config={
                "Name": st.column_config.TextColumn("Name", width="medium"),
                "Email": st.column_config.TextColumn("Email", width="medium"),
                "Zone": st.column_config.TextColumn("Zone", width="medium")
            },
            hide_index=True,
            use_container_width=True
        )
        
        st.write("---")  # Add separator between regions

def debug_database_ui():
    st.header("Database Management")
    
    # Create tabs for different database operations
    debug_tab1, debug_tab2, debug_tab3 = st.tabs([
        "View Records", 
        "Database Schema",
        "Database Operations"
    ])
    
    with debug_tab1:
        # ... existing view records code ...
        pass
        
    with debug_tab2:
        # ... existing schema code ...
        pass
        
    with debug_tab3:
        st.subheader("Database Operations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### Partner Records Database")
            
            if st.button("Reinitialize Partner Records DB"):
                try:
                    # Remove existing database
                    if os.path.exists('partner_records.db'):
                        os.remove('partner_records.db')
                    
                    # Initialize fresh database
                    from partner_records import init_partner_db
                    init_partner_db()
                    st.success("Partner Records database reinitialized successfully!")
                except Exception as e:
                    st.error(f"Error reinitializing Partner Records database: {e}")
            
            if st.button("Run Partner Records Migration"):
                try:
                    # Read and execute migration SQL
                    with open('migrations/add_grand_total_column.sql', 'r') as f:
                        migration_sql = f.read()
                    
                    conn = sqlite3.connect('partner_records.db')
                    c = conn.cursor()
                    
                    # Split and execute each statement
                    for statement in migration_sql.split(';'):
                        if statement.strip():
                            try:
                                c.execute(statement)
                            except sqlite3.OperationalError as e:
                                if "duplicate column" not in str(e).lower():
                                    raise e
                    
                    conn.commit()
                    conn.close()
                    st.success("Partner Records migration completed successfully!")
                except Exception as e:
                    st.error(f"Error running Partner Records migration: {e}")
        
        with col2:
            st.write("### Church Records Database")
            
            if st.button("Reinitialize Church Records DB"):
                try:
                    # Remove existing database
                    if os.path.exists('church_partners.db'):
                        os.remove('church_partners.db')
                    
                    # Initialize fresh database
                    from church_records import init_church_db
                    init_church_db()
                    st.success("Church Records database reinitialized successfully!")
                except Exception as e:
                    st.error(f"Error reinitializing Church Records database: {e}")
            
            if st.button("Run Church Records Migration"):
                try:
                    # Read and execute migration SQL
                    with open('migrations/init_church_db.sql', 'r') as f:
                        migration_sql = f.read()
                    
                    conn = sqlite3.connect('church_partners.db')
                    c = conn.cursor()
                    
                    # Split and execute each statement
                    for statement in migration_sql.split(';'):
                        if statement.strip():
                            try:
                                c.execute(statement)
                            except sqlite3.OperationalError as e:
                                if "duplicate column" not in str(e).lower():
                                    raise e
                    
                    conn.commit()
                    conn.close()
                    st.success("Church Records migration completed successfully!")
                except Exception as e:
                    st.error(f"Error running Church Records migration: {e}")
        
        # Add backup/restore functionality
        st.write("### Backup and Restore")
        
        col3, col4 = st.columns(2)
        
        with col3:
            if st.button("Backup Databases"):
                try:
                    backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
                    
                    # Backup partner records
                    if os.path.exists('partner_records.db'):
                        import shutil
                        shutil.copy2('partner_records.db', f'backups/partner_records_{backup_time}.db')
                    
                    # Backup church records
                    if os.path.exists('church_partners.db'):
                        import shutil
                        shutil.copy2('church_partners.db', f'backups/church_partners_{backup_time}.db')
                    
                    st.success(f"Databases backed up successfully! Timestamp: {backup_time}")
                except Exception as e:
                    st.error(f"Error backing up databases: {e}")
        
        with col4:
            # List available backups
            if os.path.exists('backups'):
                backup_files = [f for f in os.listdir('backups') if f.endswith('.db')]
                if backup_files:
                    selected_backup = st.selectbox(
                        "Select backup to restore",
                        backup_files,
                        format_func=lambda x: x.replace('.db', '').replace('_', ' ')
                    )
                    
                    if st.button("Restore Selected Backup"):
                        try:
                            import shutil
                            backup_path = os.path.join('backups', selected_backup)
                            
                            # Determine which database to restore
                            if 'partner_records' in selected_backup:
                                shutil.copy2(backup_path, 'partner_records.db')
                            elif 'church_partners' in selected_backup:
                                shutil.copy2(backup_path, 'church_partners.db')
                            
                            st.success("Database restored successfully!")
                        except Exception as e:
                            st.error(f"Error restoring backup: {e}")
                else:
                    st.info("No backups available")
            else:
                if st.button("Create Backups Directory"):
                    try:
                        os.makedirs('backups')
                        st.success("Backups directory created!")
                    except Exception as e:
                        st.error(f"Error creating backups directory: {e}")

# Add this function to handle database purging
def purge_database_ui():
    """Admin interface for purging databases"""
    st.subheader("Database Management")
    
    st.warning("""
    ⚠️ **WARNING**: This section allows permanent deletion of database records. 
    These actions cannot be undone. Please proceed with caution.
    """)
    
    # Create tabs for different databases
    tab1, tab2, tab3 = st.tabs([
        "Partner Records",
        "Church Records",
        "User Records"
    ])
    
    with tab1:
        st.subheader("Purge Partner Records")
        
        # Partner record types
        partner_types = [
            "All Partner Records",
            "Adult Partners",
            "Child Partners",
            "Teenager Partners",
            "External Partners"
        ]
        
        selected_partner_type = st.selectbox(
            "Select Record Type to Purge",
            partner_types,
            key="purge_partner_type"
        )
        
        if st.button("Purge Selected Partner Records", key="purge_partner"):
            if 'confirm_purge_partner' not in st.session_state:
                st.session_state.confirm_purge_partner = True
                st.warning(f"Are you sure you want to purge {selected_partner_type}? Click again to confirm.")
            else:
                try:
                    conn = sqlite3.connect('partner_records.db')
                    c = conn.cursor()
                    
                    if selected_partner_type == "All Partner Records":
                        tables = ['adult_partners', 'children_partners', 'teenager_partners', 'external_partners']
                        for table in tables:
                            c.execute(f"DELETE FROM {table}")
                    else:
                        table_map = {
                            'Adult Partners': 'adult_partners',
                            'Child Partners': 'children_partners',
                            'Teenager Partners': 'teenager_partners',
                            'External Partners': 'external_partners'
                        }
                        table = table_map.get(selected_partner_type)
                        if table:
                            c.execute(f"DELETE FROM {table}")
                    
                    conn.commit()
                    conn.close()
                    st.success(f"Successfully purged {selected_partner_type}")
                    del st.session_state.confirm_purge_partner
                except Exception as e:
                    st.error(f"Error purging records: {e}")
    
    with tab2:
        st.subheader("Purge Church Records")
        
        # Church record types
        church_types = [
            "All Church Records",
            "Category A Churches",
            "Category B Churches",
            "Churches",
            "Cell Records",
            "ROR Records"
        ]
        
        selected_church_type = st.selectbox(
            "Select Record Type to Purge",
            church_types,
            key="purge_church_type"
        )
        
        if st.button("Purge Selected Church Records", key="purge_church"):
            if 'confirm_purge_church' not in st.session_state:
                st.session_state.confirm_purge_church = True
                st.warning(f"Are you sure you want to purge {selected_church_type}? Click again to confirm.")
            else:
                try:
                    conn = sqlite3.connect('church_partners.db')
                    c = conn.cursor()
                    
                    if selected_church_type == "All Church Records":
                        c.execute("DELETE FROM church_partner_records")
                    else:
                        record_type_map = {
                            'Category A Churches': 'Category A',
                            'Category B Churches': 'Category B',
                            'Churches': 'Church',
                            'Cell Records': 'Cell',
                            'ROR Records': 'ROR'
                        }
                        record_type = record_type_map.get(selected_church_type)
                        if record_type:
                            c.execute("DELETE FROM church_partner_records WHERE record_type = ?", (record_type,))
                    
                    conn.commit()
                    conn.close()
                    st.success(f"Successfully purged {selected_church_type}")
                    del st.session_state.confirm_purge_church
                except Exception as e:
                    st.error(f"Error purging records: {e}")
    
    with tab3:
        st.subheader("Purge User Records")
        
        st.error("""
        ⚠️ **CRITICAL WARNING**: Purging user records will remove all user accounts except the admin account.
        This will require users to re-register.
        """)
        
        if st.button("Purge All User Records", key="purge_users"):
            if 'confirm_purge_users' not in st.session_state:
                st.session_state.confirm_purge_users = True
                st.warning("Are you sure you want to purge all user records? Click again to confirm.")
            else:
                try:
                    conn = sqlite3.connect('users.db')
                    c = conn.cursor()
                    c.execute("DELETE FROM users WHERE username != 'admin'")
                    conn.commit()
                    conn.close()
                    st.success("Successfully purged all user records (except admin)")
                    del st.session_state.confirm_purge_users
                except Exception as e:
                    st.error(f"Error purging user records: {e}")

def display_user_dashboard():
    try:
        st.write(f"Welcome, {st.session_state.username}!")
        st.subheader("User Dashboard")

        user_details = get_user_details(st.session_state.username)
        user_group, sub_group, region, zone = user_details

        # Create tabs for different sections
        if user_group == "RZM":
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "Dashboard", 
                "Partner Records", 
                "Church Records",
                "Upload Report",
                "View Reports"  # Added View Reports tab
            ])
        else:
            tab1, tab2, tab3 = st.tabs(["Dashboard", "View Your Submitted Reports", "Submit New Report"])

        with tab1:
            st.subheader("Your Dashboard")

        if user_group == "RZM":
            with tab2:
                partner_records_ui()

            with tab3:
                church_records_ui()
                
            with tab4:
                record_templates_ui()
                
            with tab5:
                # View Reports tab with read-only access
                view_reports_ui_readonly(zone)

    except Exception as e:
        st.error(f"An error occurred while displaying the user dashboard: {e}")

# Add this new function for read-only reports view
def view_reports_ui_readonly(user_zone):
    """View reports interface for RZMs with financial edit capability"""
    st.subheader("View Reports")
    
    # Create tabs for different types of reports
    tab1, tab2, tab3 = st.tabs([
        "Partner Reports",
        "Church Sponsorship Reports", 
        "ROR Outreaches Reports"
    ])
    
    with tab1:
        # Get filtered partner records for the RZM's zone
        filtered_df = get_filtered_partner_records(user_zone)
        if filtered_df.empty:
            st.warning("No partner records found for your zone.")
        else:
            # Enhanced search functionality for viewing
            view_search_term = st.text_input(
                "Search Records (ID, Name, Title, Email, Church, Group, Zone, Phone)", 
                key="rzm_partner_view_search"
            )
            if view_search_term:
                filtered_df = apply_partner_search(filtered_df, view_search_term)
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Separate search for edit section
            st.subheader("Edit Financial Records")
            edit_search_term = st.text_input(
                "Search Record to Edit (ID, Name, Title, Email, Church, Group, Zone, Phone)",
                key="rzm_partner_edit_search"
            )
            
            edit_results_df = filtered_df
            if edit_search_term:
                edit_results_df = apply_partner_search(filtered_df, edit_search_term)
            
            if not edit_results_df.empty:
                st.write("### Search Results")
                for idx, row in edit_results_df.iterrows():
                    record_id = str(row['id'])
                    unique_id = get_unique_record_id(record_id, row['record_type'])
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        st.write(f"""
                        **ID:** {record_id} ({row['record_type']})  
                        **Name:** {row['title']} {row['first_name']} {row['surname']}  
                        **Zone:** {row['zone']}
                        """)
                    
                    with col2:
                        if st.button("Edit", key=f"edit_btn_{unique_id}"):
                            st.session_state.editing_record = record_id
                            st.session_state.editing_type = row['record_type']
                
                # Show edit form if a record is selected
                if hasattr(st.session_state, 'editing_record'):
                    record = get_partner_record(
                        st.session_state.editing_record,
                        st.session_state.editing_type
                    )
                    
                    if record:
                        unique_id = get_unique_record_id(
                            st.session_state.editing_record,
                            st.session_state.editing_type
                        )
                        with st.form(key=f"edit_form_{unique_id}"):
                            st.write(f"""
                            ### Edit Financial Records
                            **Partner Type:** {st.session_state.editing_type}  
                            **Name:** {record.get('first_name')} {record.get('surname')}
                            """)
                            
                            # Financial fields with unique keys
                            col1, col2 = st.columns(2)
                            with col1:
                                wonder_challenge = st.number_input(
                                    "Wonder Challenge", 
                                    value=float(record.get('total_wonder_challenge', 0)),
                                    key=f"wc_{unique_id}"
                                )
                                kiddies_products = st.number_input(
                                    "Kiddies Products", 
                                    value=float(record.get('total_kiddies_products', 0)),
                                    key=f"kp_{unique_id}"
                                )
                                braille_nolb = st.number_input(
                                    "Braille(NOLB)", 
                                    value=float(record.get('total_braille_nolb', 0)),
                                    key=f"bn_{unique_id}"
                                )
                                local_distribution = st.number_input(
                                    "Local Distribution", 
                                    value=float(record.get('total_local_distribution', 0)),
                                    key=f"ld_{unique_id}"
                                )
                            
                            with col2:
                                rhapsody_languages = st.number_input(
                                    "Rhapsody Languages", 
                                    value=float(record.get('total_rhapsody_languages', 0)),
                                    key=f"rl_{unique_id}"
                                )
                                teevo = st.number_input(
                                    "Teevo", 
                                    value=float(record.get('total_teevo', 0)),
                                    key=f"tv_{unique_id}"
                                )
                                youth_aglow = st.number_input(
                                    "Youth Aglow", 
                                    value=float(record.get('total_youth_aglow', 0)),
                                    key=f"ya_{unique_id}"
                                )
                                subscriptions_dubais = st.number_input(
                                    "Subscriptions/Dubais", 
                                    value=float(record.get('total_subscriptions_dubais', 0)),
                                    key=f"sd_{unique_id}"
                                )
                            
                            col1, col2 = st.columns(2)
                            with col1:
                                submit = st.form_submit_button("Update Financial Records")
                            with col2:
                                cancel = st.form_submit_button("Cancel")
                            
                            if submit:
                                updated_amounts = {
                                    'total_wonder_challenge': wonder_challenge,
                                    'total_rhapsody_languages': rhapsody_languages,
                                    'total_kiddies_products': kiddies_products,
                                    'total_teevo': teevo,
                                    'total_braille_nolb': braille_nolb,
                                    'total_youth_aglow': youth_aglow,
                                    'total_local_distribution': local_distribution,
                                    'total_subscriptions_dubais': subscriptions_dubais
                                }
                                
                                success, message = edit_financial_record(
                                    st.session_state.editing_record,
                                    st.session_state.editing_type,
                                    updated_amounts
                                )
                                
                                if success:
                                    st.success(message)
                                    del st.session_state.editing_record
                                    del st.session_state.editing_type
                                    time.sleep(0.5)
                                    st.rerun()
                                else:
                                    st.error(message)
                            
                            if cancel:
                                del st.session_state.editing_record
                                del st.session_state.editing_type
                                st.rerun()

    with tab2:
        # Get filtered church records for the RZM's zone
        filtered_df = get_filtered_church_records(user_zone)
        if filtered_df.empty:
            st.warning("No church sponsorship records found for your zone.")
        else:
            # Enhanced search functionality
            search_term = st.text_input("Search by ID, Church Name, Cell Name, Pastor, Leader, Group, Zone", 
                                      key="rzm_church_search")
            if search_term:
                filtered_df = filtered_df[
                    filtered_df['ID'].astype(str).str.contains(search_term, case=False, na=False) |
                    filtered_df['Church Name'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Cell Name'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Church Pastor'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Cell Leader'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Group'].str.contains(search_term, case=False, na=False) |
                    filtered_df['Zone'].str.contains(search_term, case=False, na=False)
                ]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Add export functionality
            if st.button("Export to Excel", key="export_churches"):
                excel_data = download_excel(filtered_df, "church_records.xlsx")
                st.download_button(
                    label="Download Church Records",
                    data=excel_data,
                    file_name="church_records.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
    with tab3:
        # Get filtered ROR records for the RZM's zone
        filtered_df = get_filtered_ror_records(user_zone)
        if filtered_df.empty:
            st.warning("No ROR outreach records found for your zone.")
        else:
            # Add search functionality
            search_term = st.text_input("Search by Group Name or Program", key="rzm_ror_search")
            if search_term:
                filtered_df = filtered_df[
                    filtered_df['Group'].str.contains(search_term, case=False, na=False)
                ]
            
            st.dataframe(filtered_df, use_container_width=True)
            
            # Add export functionality
            if st.button("Export to Excel", key="export_ror"):
                excel_data = download_excel(filtered_df, "ror_records.xlsx")
                st.download_button(
                    label="Download ROR Records",
                    data=excel_data,
                    file_name="ror_records.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

def clean_value_for_excel(value):
    if isinstance(value, str):
        # Remove or replace illegal characters
        value = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', value)
        # Replace other potentially problematic characters
        value = value.replace('\x0D', '\n')  # Replace carriage return with newline
    return value

def download_excel(df, filename):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data

def delete_partner_record(record_id, record_type):
    """Delete a partner record from the appropriate table"""
    try:
        conn = sqlite3.connect('partner_records.db')
        c = conn.cursor()
        
        table_name = {
            'Adult Partner': 'adult_partners',
            'Child Partner': 'children_partners',
            'Teenager Partner': 'teenager_partners',
            'External Partner': 'external_partners'
        }[record_type]
        
        c.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
        conn.commit()
        return True, "Record deleted successfully!"
    except Exception as e:
        return False, f"Error deleting record: {e}"
    finally:
        conn.close()

def delete_church_record(record_id):
    """Delete a church record"""
    try:
        conn = sqlite3.connect('church_partners.db')
        c = conn.cursor()
        c.execute("DELETE FROM church_partner_records WHERE id = ?", (record_id,))
        conn.commit()
        return True, "Record deleted successfully!"
    except Exception as e:
        return False, f"Error deleting record: {e}"
    finally:
        conn.close()

# Add new function for full access dashboard
def display_full_access_dashboard():
    try:
        st.write(f"Welcome, {st.session_state.username}!")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "Dashboard",
            "Partner Records",
            "Church Records",
            "Upload Report"
        ])

        with tab1:
            st.subheader("Dashboard Overview")
            # Add dashboard content specific to role
            if st.session_state.is_regional_manager:
                region = st.session_state.region
                
                # Fetch and display regional-specific statistics
                rzms_in_region = fetch_rzms_in_region(region)
                st.write(f"RZMs in {region}:")
                rzm_df = pd.DataFrame(rzms_in_region, columns=["Username", "Full Name", "Email", "Zone"])
                st.dataframe(rzm_df)

                # Display regional reports and metrics
                reports = fetch_reports(region=region)
                if reports:
                    total_reports, metrics_sum = calculate_report_metrics(reports)
                    st.write(f"Total Reports Submitted in {region}: {total_reports}")
                    st.write("Metrics Summary:")
                    metrics_df = pd.DataFrame(list(metrics_sum.items()), columns=['Metric', 'Total'])
                    st.table(metrics_df)
            else:
                # Display admin/reporting dashboard content
                reports = fetch_reports()
                if reports:
                    total_reports, metrics_sum = calculate_report_metrics(reports)
                    st.write(f"Total Reports Submitted: {total_reports}")
                    st.write("Overall Metrics Summary:")
                    metrics_df = pd.DataFrame(list(metrics_sum.items()), columns=['Metric', 'Total'])
                    st.table(metrics_df)

        with tab2:
            partner_records_ui()

        with tab3:
            church_records_ui()

        with tab4:
            record_templates_ui()  # Use the imported function directly

    except Exception as e:
        st.error(f"An error occurred while displaying the dashboard: {e}")

# Add this after the other function definitions and before the main() function

def user_management_ui():
    st.subheader("User Management")
    
    # Fetch all users
    users = fetch_all_users()
    
    # Create DataFrame for better display
    users_df = pd.DataFrame(users, columns=[
        "Username", "Full Name", "Email", "User Group", 
        "Sub Group", "Region", "Zone"
    ])
    
    # Display users table
    st.write("### Current Users")
    st.dataframe(users_df)
    
    # Edit User Section
    st.write("### Edit User")
    username_to_edit = st.selectbox("Select user to edit", users_df["Username"])
    
    if username_to_edit:
        user_row = users_df[users_df["Username"] == username_to_edit].iloc[0]
        
        # Create form for editing
        with st.form("edit_user_form"):
            full_name = st.text_input("Full Name", value=user_row["Full Name"])
            email = st.text_input("Email", value=user_row["Email"])
            user_group = st.selectbox(
                "User Group", 
                ["GPD", "RZM"],
                index=0 if user_row["User Group"] == "GPD" else 1
            )
            
            # Dynamic fields based on user group
            if user_group == "GPD":
                sub_group = st.selectbox(
                    "Sub Group",
                    ["Finance", "IT", "Reporting/Admin", "Admin Manager", "Regional Manager"],
                    index=["Finance", "IT", "Reporting/Admin", "Admin Manager", "Regional Manager"].index(user_row["Sub Group"]) if user_row["Sub Group"] in ["Finance", "IT", "Reporting/Admin", "Admin Manager", "Regional Manager"] else 0
                )
                region = st.selectbox(
                    "Region",
                    ["Select..."] + [f"Region {i}" for i in range(1, 7)],
                    index=["Select..."] + [f"Region {i}" for i in range(1, 7)].index(user_row["Region"]) + 1 if user_row["Region"] in [f"Region {i}" for i in range(1, 7)] else 0
                )
                zone = None
            else:
                sub_group = None
                region = st.selectbox(
                    "Region",
                    ["Select..."] + list(zones_data.keys()),
                    index=list(zones_data.keys()).index(user_row["Region"]) + 1 if user_row["Region"] in zones_data.keys() else 0
                )
                if region and region != "Select...":
                    zone = st.selectbox(
                        "Zone",
                        ["Select..."] + zones_data[region],
                        index=zones_data[region].index(user_row["Zone"]) + 1 if user_row["Zone"] in zones_data[region] else 0
                    )
            
            submit = st.form_submit_button("Update User")
            
            if submit:
                if user_group == "RZM" and (region == "Select..." or zone == "Select..."):
                    st.error("Please select both Region and Zone for RZM users.")
                elif user_group == "GPD" and (sub_group == "Select..." or (sub_group in ["Admin Manager", "Regional Manager"] and region == "Select...")):
                    st.error("Please select all required fields for GPD users.")
                else:
                    update_user(username_to_edit, full_name, email, user_group, sub_group, region, zone)
                    st.success("User updated successfully!")
                    st.rerun()
    
    # Delete User Section
    st.write("### Delete User")
    username_to_delete = st.selectbox("Select user to delete", users_df["Username"], key="delete_user")
    
    if username_to_delete:
        if st.button("Delete User"):
            if username_to_delete == "admin":
                st.error("Cannot delete admin user!")
            else:
                delete_user(username_to_delete)
                st.success(f"User {username_to_delete} deleted successfully!")
                st.rerun()

def view_reports_ui():
    """View reports interface with separate tabs for different record types"""
    st.subheader("View Reports")
    
    # Create tabs for different types of reports (removed duplicate Partner Reports tab)
    tab1, tab2, tab3 = st.tabs([
        "Partner Reports",
        "Church Sponsorship Reports", 
        "ROR Outreaches Reports"
    ])
    
    # Only show edit/delete for admin users
    is_admin = st.session_state.is_super_admin
    
    # Get user's zone for filtering
    user_zone = None
    if not st.session_state.is_super_admin:
        user_zone = st.session_state.get('zone')
    
    with tab1:
        partner_reports_ui()
        
    with tab2:
        view_church_sponsorship_reports(is_admin=is_admin, user_zone=user_zone)
        
    with tab3:
        view_ror_reports(is_admin=is_admin, user_zone=user_zone)

def view_church_sponsorship_reports(is_admin=False, user_zone=None):
    """View church sponsorship records reports with edit/delete for admin"""
    st.subheader("Church Sponsorship Reports")
    
    # Display records in dataframe
    filtered_df = get_filtered_church_records(user_zone)
    if filtered_df.empty:
        st.warning("No church sponsorship records found.")
        return
        
    st.dataframe(filtered_df, use_container_width=True)
    
    # Add edit/delete section for admin
    if is_admin:
        st.subheader("Edit/Delete Records")
        
        # Initialize session state for delete confirmations
        if 'delete_confirmations' not in st.session_state:
            st.session_state.delete_confirmations = {}
        
        # Search across multiple fields
        search_term = st.text_input("Search by Church Name, Cell Name, Pastor, Leader, Group, or ID", key="church_search")
        if search_term:
            search_df = filtered_df[
                filtered_df['Church Name'].str.contains(search_term, case=False, na=False) |
                filtered_df['Cell Name'].str.contains(search_term, case=False, na=False) |
                filtered_df['Church Pastor'].str.contains(search_term, case=False, na=False) |
                filtered_df['Cell Leader'].str.contains(search_term, case=False, na=False) |
                filtered_df['Group'].str.contains(search_term, case=False, na=False) |
                filtered_df['ID'].astype(str).str.contains(search_term)
            ]
            
            if not search_df.empty:
                st.write("Search Results:")
                for idx, row in search_df.iterrows():
                    record_id = str(row['ID'])
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        # Display more comprehensive information
                        display_name = row['Church Name'] or row['Cell Name']
                        display_leader = row['Church Pastor'] or row['Cell Leader']
                        st.write(f"{display_name} ({display_leader}) - Group: {row['Group']} (ID: {record_id})")
                    
                    with col2:
                        if record_id not in st.session_state.delete_confirmations:
                            st.session_state.delete_confirmations[record_id] = False
                            
                        if not st.session_state.delete_confirmations[record_id]:
                            if st.button("Delete", key=f"del_{record_id}"):
                                st.session_state.delete_confirmations[record_id] = True
                                st.rerun()
                        else:
                            col3, col4 = st.columns(2)
                            with col3:
                                if st.button("✓", key=f"confirm_{record_id}", type="primary"):
                                    success, message = delete_church_record(record_id)
                                    if success:
                                        st.success(message)
                                        st.session_state.delete_confirmations[record_id] = False
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error(message)
                            with col4:
                                if st.button("✗", key=f"cancel_{record_id}"):
                                    st.session_state.delete_confirmations[record_id] = False
                                    st.rerun()
            else:
                st.info("No records found matching your search.")

def view_ror_reports(is_admin=False, user_zone=None):
    """View ROR outreach records reports with edit/delete for admin"""
    st.subheader("ROR Outreaches Reports")
    
    # Display records in dataframe
    filtered_df = get_filtered_ror_records(user_zone)
    if filtered_df.empty:
        st.warning("No ROR outreach records found.")
        return
        
    st.dataframe(filtered_df, use_container_width=True)
    
    # Add edit/delete section for admin
    if is_admin:
        st.subheader("Edit/Delete Records")
        
        # Initialize session state for edit/delete confirmations
        if 'edit_mode' not in st.session_state:
            st.session_state.edit_mode = {}
        if 'delete_confirmations' not in st.session_state:
            st.session_state.delete_confirmations = {}
        
        # Search by group name or ID
        search_term = st.text_input("Search by Group Name or ID", key="ror_report_search")
        if search_term:
            search_df = filtered_df[
                filtered_df['Group'].str.contains(search_term, case=False, na=False) |
                filtered_df['ID'].astype(str).str.contains(search_term)
            ]
            
            if not search_df.empty:
                st.write("Search Results:")
                for idx, row in search_df.iterrows():
                    record_id = str(row['ID'])
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        st.write(f"{row['Group']} (ID: {record_id})")
                    
                    with col2:
                        # Edit button
                        if record_id not in st.session_state.edit_mode:
                            st.session_state.edit_mode[record_id] = False
                            
                        if not st.session_state.edit_mode[record_id]:
                            if st.button("Edit", key=f"edit_{record_id}"):
                                st.session_state.edit_mode[record_id] = True
                                st.rerun()
                    
                    with col3:
                        # Delete button
                        if record_id not in st.session_state.delete_confirmations:
                            st.session_state.delete_confirmations[record_id] = False
                            
                        if not st.session_state.delete_confirmations[record_id]:
                            if st.button("Delete", key=f"del_{record_id}"):
                                st.session_state.delete_confirmations[record_id] = True
                                st.rerun()
                        else:
                            col4, col5 = st.columns(2)
                            with col4:
                                if st.button("✓", key=f"confirm_{record_id}", type="primary"):
                                    success, message = delete_church_record(record_id)
                                    if success:
                                        st.success(message)
                                        st.session_state.delete_confirmations[record_id] = False
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error(message)
                            with col5:
                                if st.button("✗", key=f"cancel_{record_id}"):
                                    st.session_state.delete_confirmations[record_id] = False
                                    st.rerun()
                    
                    # Edit form
                    if st.session_state.edit_mode.get(record_id, False):
                        with st.form(key=f"edit_form_{record_id}"):
                            st.write("### Edit ROR Record")
                            
                            # Fetch current record data
                            current_data = get_ror_record(record_id)
                            if current_data:
                                # Form fields
                                group_name = st.text_input("Group Name", value=current_data.get('group_name', ''))
                                zone_name = st.text_input("Zone", value=current_data.get('zone_name', ''))
                                total_outreaches = st.number_input("Total Outreaches", 
                                    value=int(current_data.get('total_outreaches', 0)), min_value=0)
                                
                                # Program quantities
                                st.write("#### Program Quantities")
                                col1, col2 = st.columns(2)
                                with col1:
                                    reachout_programs = st.number_input("Reachout Programs", 
                                        value=int(current_data.get('reachout_world_programs', 0)), min_value=0)
                                    rhapathon = st.number_input("Rhapathon", 
                                        value=int(current_data.get('rhapathon', 0)), min_value=0)
                                    world_nations = st.number_input("World Nations", 
                                        value=int(current_data.get('reachout_world_nations', 0)), min_value=0)
                                    say_yes_to_kids = st.number_input("Say Yes to Kids", 
                                        value=int(current_data.get('say_yes_to_kids', 0)), min_value=0)
                                    teevolution = st.number_input("Teevolution", 
                                        value=int(current_data.get('teevolution', 0)), min_value=0)
                                
                                with col2:
                                    youth_aglow = st.number_input("Youth Aglow", 
                                        value=int(current_data.get('youth_aglow', 0)), min_value=0)
                                    no_one_left_behind = st.number_input("No One Left Behind", 
                                        value=int(current_data.get('no_one_left_behind', 0)), min_value=0)
                                    penetrating_truth = st.number_input("Penetrating Truth", 
                                        value=int(current_data.get('penetrating_truth', 0)), min_value=0)
                                    penetrating_languages = st.number_input("Penetrating Languages", 
                                        value=int(current_data.get('penetrating_languages', 0)), min_value=0)
                                    adopt_a_street = st.number_input("Adopt a Street", 
                                        value=int(current_data.get('adopt_a_street', 0)), min_value=0)
                                
                                # Amount section
                                st.write("#### Amount")
                                col1, col2 = st.columns(2)
                                with col1:
                                    total_amount = st.number_input("Total Amount", 
                                        value=float(current_data.get('total_amount', 0.0)), min_value=0.0)
                                with col2:
                                    currency = st.selectbox("Currency", 
                                        options=list(CONVERSION_RATES.keys()),
                                        index=list(CONVERSION_RATES.keys()).index(current_data.get('currency', 'ESPEES')))
                                
                                # Calculate grand total
                                grand_total = convert_to_espees(total_amount, currency)
                                st.write(f"Grand Total: {grand_total:,.2f} ESPEES")
                                
                                # Submit buttons
                                col1, col2 = st.columns(2)
                                with col1:
                                    submit = st.form_submit_button("Update Record")
                                with col2:
                                    cancel = st.form_submit_button("Cancel")
                                
                                if submit:
                                    # Prepare updated data
                                    updated_data = {
                                        'group_name': group_name,
                                        'zone_name': zone_name,
                                        'total_outreaches': total_outreaches,
                                        'reachout_world_programs': reachout_programs,
                                        'rhapathon': rhapathon,
                                        'reachout_world_nations': world_nations,
                                        'say_yes_to_kids': say_yes_to_kids,
                                        'teevolution': teevolution,
                                        'youth_aglow': youth_aglow,
                                        'no_one_left_behind': no_one_left_behind,
                                        'penetrating_truth': penetrating_truth,
                                        'penetrating_languages': penetrating_languages,
                                        'adopt_a_street': adopt_a_street,
                                        'total_amount': total_amount,
                                        'currency': currency,
                                        'grand_total': grand_total
                                    }
                                    
                                    success, message = update_ror_record(record_id, updated_data)
                                    if success:
                                        st.success(message)
                                        st.session_state.edit_mode[record_id] = False
                                        time.sleep(0.5)
                                        st.rerun()
                                    else:
                                        st.error(message)
                                
                                if cancel:
                                    st.session_state.edit_mode[record_id] = False
                                    st.rerun()
            else:
                st.info("No records found matching your search.")

def church_analytics_ui():
    """Church analytics dashboard with fixed currency display"""
    st.title("Church Records Analytics")
    
    # Use ESPEES as default currency
    display_currency = 'ESPEES'
    
    # Fetch church records (excluding ROR)
    records = fetch_church_partner_records()
    church_records = [r for r in records if r[1] != "ROR"]
    
    if not church_records:
        st.warning("No church sponsorship records found.")
        return
        
    # Process records into DataFrame
    df = process_church_records(church_records, display_currency)
    
    if df.empty:
        st.warning("No records found after processing.")
        return
    
    # Add filters in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Record type filter
        record_types = ['All'] + sorted(df['Record Type'].unique().tolist())
        selected_type = st.selectbox(
            "Filter by Record Type", 
            record_types,
            key="church_record_type"
        )
    
    with col2:
        # Zone filter
        zones = ['All'] + sorted(df['Zone'].unique().tolist())
        selected_zone = st.selectbox(
            "Filter by Zone", 
            zones,
            key="church_zone"
        )
    
    with col3:
        # Analysis type selection
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Quantity", "Amount"],
            key="church_analysis_type"
        )
    
    # Add search filter with expanded functionality
    search_term = st.text_input("Search (Church Name, Pastor, Cell, Leader, Group, Zone)", key="church_analytics_search")
    
    # Apply filters
    filtered_df = df.copy()
    if selected_type != 'All':
        filtered_df = filtered_df[filtered_df['Record Type'] == selected_type]
    if selected_zone != 'All':
        filtered_df = filtered_df[filtered_df['Zone'] == selected_zone]
    if search_term:
        # Search across multiple fields
        filtered_df = filtered_df[
            filtered_df['Church Name'].str.contains(search_term, case=False, na=False) |
            filtered_df['Group'].str.contains(search_term, case=False, na=False) |
            filtered_df['Zone'].str.contains(search_term, case=False, na=False) |
            filtered_df.apply(lambda row: any(
                str(val).lower().contains(search_term.lower())
                for val in [
                    row.get('Church Pastor', ''),
                    row.get('Cell Name', ''),
                    row.get('Cell Leader', '')
                ]
            ), axis=1)
        ]
    
    # Prepare display columns based on analysis type
    if analysis_type == "Quantity":
        display_columns = [
            'Record Type', 'Zone', 'Church Name', 'Group',
            'Kiddies Products', 'Teevo', 'Braille',
            'Languages', 'Youth Aglow', 'Total Quantity',
            'Submission Date'
        ]
    else:  # Amount
        filtered_df['Display Amount'] = filtered_df.apply(
            lambda row: f"{row['Original Amount']:,.2f} {row['Currency']} "
                       f"({row['Converted Amount']:,.2f} {display_currency})",
            axis=1
        )
        display_columns = [
            'Record Type', 'Zone', 'Church Name', 'Group',
            'Display Amount', 'Total Quantity', 'Submission Date'
        ]
    
    # Display filtered results
    st.subheader("Filtered Results")
    st.dataframe(filtered_df[display_columns], use_container_width=True)

def ror_analytics_ui():
    """Dedicated ROR Analytics Interface"""
    st.title("ROR Outreaches Analytics")
    
    # Use ESPEES as default currency
    display_currency = 'ESPEES'
    
    # Fetch ROR records
    conn = sqlite3.connect('church_partners.db')
    query = "SELECT * FROM church_partner_records WHERE record_type = 'ROR'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    if df.empty:
        st.warning("No ROR outreach records found.")
        return
    
    # Process records
    records_data = []
    for _, row in df.iterrows():
        record_data = json.loads(row['record_data'])
        
        # Extract base data
        base_data = {
            'Zone': record_data.get('zone_name', ''),
            'Group': record_data.get('group_name', ''),
            'Total Outreaches': int(record_data.get('total_outreaches', 0)),
            'Original Amount': float(record_data.get('total_amount', 0)),
            'Currency': record_data.get('currency', 'ESPEES'),
            'Submission Date': row['submission_date'],
            # Program-specific data
            'Reachout Programs': int(record_data.get('reachout_world_programs', 0)),
            'Rhapathon': int(record_data.get('rhapathon', 0)),
            'World Nations': int(record_data.get('reachout_world_nations', 0)),
            'Say Yes to Kids': int(record_data.get('say_yes_to_kids', 0)),
            'Teevolution': int(record_data.get('teevolution', 0)),
            'Youth Aglow': int(record_data.get('youth_aglow', 0)),
            'No One Left Behind': int(record_data.get('no_one_left_behind', 0)),
            'Penetrating Truth': int(record_data.get('penetrating_truth', 0)),
            'Penetrating Languages': int(record_data.get('penetrating_languages', 0)),
            'Adopt a Street': int(record_data.get('adopt_a_street', 0))
        }
        
        # Convert amount to ESPEES
        base_data['Converted Amount'] = convert_to_espees(
            base_data['Original Amount'],
            base_data['Currency']
        )
        
        # Add formatted amount display
        base_data['Amount'] = (
            f"{base_data['Original Amount']:,.2f} {base_data['Currency']} "
            f"({base_data['Converted Amount']:,.2f} {display_currency})"
        )
        
        records_data.append(base_data)
    
    df = pd.DataFrame(records_data)
    
    # Add filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Zone filter
        zones = ['All'] + sorted(df['Zone'].unique().tolist())
        selected_zone = st.selectbox(
            "Filter by Zone", 
            zones,
            key="ror_analytics_zone"
        )
    
    with col2:
        # View type selection
        view_type = st.selectbox(
            "Select Program",
            [
                "All Programs",
                "Reachout Programs",
                "Rhapathon",
                "World Nations",
                "Say Yes to Kids",
                "Teevolution",
                "Youth Aglow",
                "No One Left Behind",
                "Penetrating Truth",
                "Penetrating Languages",
                "Adopt a Street"
            ],
            key="ror_view_type"
        )
    
    with col3:
        # Analysis type
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Quantity", "Amount"],
            key="ror_analysis_type"
        )
    
    # Add search filter with expanded functionality
    search_term = st.text_input("Search (Group Name, Zone, Programs)", key="ror_analytics_search")
    
    # Apply filters
    filtered_df = df.copy()
    if selected_zone != 'All':
        filtered_df = filtered_df[filtered_df['Zone'] == selected_zone]
    if search_term:
        # Search across multiple fields
        program_columns = [
            'Reachout Programs', 'Rhapathon', 'World Nations',
            'Say Yes to Kids', 'Teevolution', 'Youth Aglow',
            'No One Left Behind', 'Penetrating Truth',
            'Penetrating Languages', 'Adopt a Street'
        ]
        
        filtered_df = filtered_df[
            filtered_df['Group'].str.contains(search_term, case=False, na=False) |
            filtered_df['Zone'].str.contains(search_term, case=False, na=False) |
            # Search in program names
            filtered_df[program_columns].apply(
                lambda row: any(
                    col.lower().contains(search_term.lower())
                    for col in program_columns
                ), axis=1
            )
        ]
    
    # Prepare display columns based on view and analysis type
    if view_type == "All Programs":
        if analysis_type == "Quantity":
            display_columns = [
                'Zone', 'Group',
                'Reachout Programs', 'Rhapathon', 'World Nations',
                'Say Yes to Kids', 'Teevolution', 'Youth Aglow',
                'No One Left Behind', 'Penetrating Truth',
                'Penetrating Languages', 'Adopt a Street',
                'Total Outreaches'
            ]
        else:  # Amount
            display_columns = ['Zone', 'Group', 'Amount', 'Total Outreaches']
    else:
        if analysis_type == "Quantity":
            display_columns = ['Zone', 'Group', view_type, 'Total Outreaches']
        else:  # Amount
            display_columns = ['Zone', 'Group', view_type, 'Amount']
    
    # Add submission date to all views
    display_columns.append('Submission Date')
    
    # Display filtered results
    st.subheader("Filtered Results")
    st.dataframe(filtered_df[display_columns], use_container_width=True)

def process_church_records(records, display_currency):
    """Process church records into DataFrame"""
    records_data = []
    for record in records:
        record_id, record_type, record_data, submission_date = record
        if isinstance(record_data, str):
            record_data = json.loads(record_data)
            
        # Extract common fields
        base_data = {
            'ID': record_id,
            'Record Type': record_type,
            'Zone': record_data.get('zone_name', ''),
            'Group': record_data.get('group_name', ''),
            'Church Name': record_data.get('church_name', ''),
            'Total Quantity': int(record_data.get('total_quantity', 0)),
            'Original Amount': float(record_data.get('total_amount', 0)),
            'Currency': record_data.get('currency', 'ESPEES'),
            'Submission Date': submission_date
        }
        
        # Add product quantities
        base_data.update({
            'Kiddies Products': int(record_data.get('kiddies_products', 0)),
            'Teevo': int(record_data.get('teevo', 0)),
            'Braille': int(record_data.get('braille_nolb', 0)),
            'Languages': int(record_data.get('languages', 0)),
            'Youth Aglow': int(record_data.get('youth_aglow', 0))
        })
        
        # Convert amount to display currency
        base_data['Converted Amount'] = convert_to_espees(
            base_data['Original Amount'],
            base_data['Currency']
        )
        
        records_data.append(base_data)
    
    return pd.DataFrame(records_data)

def filter_church_records(df, record_type, zone):
    """Apply filters to church records DataFrame"""
    filtered_df = df.copy()
    
    if record_type != 'All':
        filtered_df = filtered_df[filtered_df['Record Type'] == record_type]
    if zone != 'All':
        filtered_df = filtered_df[filtered_df['Zone'] == zone]
        
    return filtered_df

def display_quantity_analysis(df):
    """Display quantity-based analysis"""
    st.subheader("Quantity Analysis")
    
    # Select quantity metric
    quantity_metrics = [
        'Total Quantity',
        'Kiddies Products',
        'Teevo',
        'Braille',
        'Languages',
        'Youth Aglow'
    ]
    
    selected_metric = st.selectbox(
        "Select Product Type",
        quantity_metrics,
        key="church_quantity_metric"
    )
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Records", len(df))
    
    with col2:
        total_qty = df[selected_metric].sum()
        st.metric(f"Total {selected_metric}", f"{total_qty:,}")
    
    with col3:
        avg_qty = total_qty / len(df) if len(df) > 0 else 0
        st.metric(f"Average {selected_metric}", f"{avg_qty:,.0f}")
    
    # Display detailed records
    st.subheader("Detailed Records")
    display_columns = ['Record Type', 'Zone', 'Church Name', selected_metric, 'Submission Date']
    st.dataframe(df[display_columns], use_container_width=True)

def display_amount_analysis(df, currency):
    """Display amount-based analysis"""
    st.subheader("Amount Analysis")
    
    # Display metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Records", len(df))
    
    with col2:
        total_amount = df['Converted Amount'].sum()
        st.metric(f"Total Amount ({currency})", f"{total_amount:,.2f}")
    
    with col3:
        avg_amount = total_amount / len(df) if len(df) > 0 else 0
        st.metric(f"Average Amount ({currency})", f"{avg_amount:,.2f}")
    
    # Display detailed records
    st.subheader("Detailed Records")
    df['Display Amount'] = df.apply(
        lambda row: f"{row['Original Amount']:,.2f} {row['Currency']} "
                   f"({row['Converted Amount']:,.2f} {currency})",
        axis=1
    )
    
    display_columns = ['Record Type', 'Zone', 'Church Name', 'Display Amount', 'Submission Date']
    st.dataframe(df[display_columns], use_container_width=True)

def get_filtered_partner_records(user_zone=None):
    """Get filtered partner records"""
    try:
        # Fetch all partner records
        conn = sqlite3.connect('partner_records.db')
        
        # Create a list to store DataFrames from different tables
        dfs = []
        
        # Query each partner table
        tables = {
            'adult_partners': 'Adult Partner',
            'children_partners': 'Child Partner',
            'teenager_partners': 'Teenager Partner',
            'external_partners': 'External Partner'
        }
        
        for table, record_type in tables.items():
            query = f"SELECT * FROM {table}"
            df = pd.read_sql_query(query, conn)
            if not df.empty:
                # Parse record_data JSON
                df['record_data'] = df['record_data'].apply(json.loads)
                
                # Extract fields from record_data
                df['title'] = df['record_data'].apply(lambda x: x.get('title', ''))
                df['first_name'] = df['record_data'].apply(lambda x: x.get('first_name', ''))
                df['surname'] = df['record_data'].apply(lambda x: x.get('surname', ''))
                df['zone'] = df['record_data'].apply(lambda x: x.get('zone', ''))
                df['currency'] = df['record_data'].apply(lambda x: x.get('currency', 'ESPEES'))
                df['original_amount'] = df['record_data'].apply(lambda x: float(x.get('total_amount', 0)))
                df['grand_total'] = df['record_data'].apply(lambda x: float(x.get('grand_total', 0)))
                df['record_type'] = record_type
                
                # Filter by user zone if specified
                if user_zone:
                    df = df[df['zone'] == user_zone]
                
                dfs.append(df)
        
        conn.close()
        
        # Combine all DataFrames
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # Format display columns
            combined_df['Amount'] = combined_df.apply(
                lambda row: f"{float(row['original_amount']):,.2f} {row['currency']} "
                          f"({float(row['grand_total']):,.2f} ESPEES)",
                axis=1
            )
            
            # Select display columns
            display_columns = [
                'id', 'record_type', 'title', 'first_name', 'surname',
                'zone', 'Amount', 'submission_date'
            ]
            
            return combined_df[display_columns]
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error getting partner records: {e}")
        return pd.DataFrame()

def get_filtered_church_records(user_zone=None):
    """Get filtered church records"""
    try:
        # Fetch church records (excluding ROR)
        conn = sqlite3.connect('church_partners.db')
        query = "SELECT * FROM church_partner_records WHERE record_type != 'ROR'"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # Process records
        records_data = []
        for _, row in df.iterrows():
            record_data = json.loads(row['record_data'])
            
            # Filter by user zone if specified
            if user_zone and record_data.get('zone_name') != user_zone:
                continue
            
            # Format record data
            base_data = {
                'ID': row['id'],
                'Record Type': row['record_type'],
                'Zone': record_data.get('zone_name', ''),
                'Group': record_data.get('group_name', ''),
                'Church Name': record_data.get('church_name', ''),
                'Church Pastor': record_data.get('church_pastor', ''),
                'Cell Name': record_data.get('cell_name', ''),
                'Cell Leader': record_data.get('cell_leader', ''),
                'Total Quantity': record_data.get('total_quantity', 0),
                'Amount': f"{float(record_data.get('total_amount', 0)):,.2f} {record_data.get('currency', 'ESPEES')} "
                         f"({float(record_data.get('grand_total', 0)):,.2f} ESPEES)",
                'Submission Date': row['submission_date']
            }
            records_data.append(base_data)
        
        return pd.DataFrame(records_data)
    except Exception as e:
        st.error(f"Error getting church records: {e}")
        return pd.DataFrame()

def get_filtered_ror_records(user_zone=None):
    """Get filtered ROR records"""
    try:
        # Fetch only ROR records
        conn = sqlite3.connect('church_partners.db')
        query = "SELECT * FROM church_partner_records WHERE record_type = 'ROR'"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return pd.DataFrame()
        
        # Process records
        records_data = []
        for _, row in df.iterrows():
            record_data = json.loads(row['record_data'])
            
            # Filter by user zone if specified
            if user_zone and record_data.get('zone_name') != user_zone:
                continue
            
            records_data.append({
                'ID': row['id'],
                'Zone': record_data.get('zone_name', ''),
                'Group': record_data.get('group_name', ''),
                'Total Outreaches': record_data.get('total_outreaches', 0),
                'Amount': f"{float(record_data.get('total_amount', 0)):,.2f} {record_data.get('currency', 'ESPEES')} "
                         f"({float(record_data.get('grand_total', 0)):,.2f} ESPEES)",
                'Reachout Programs': record_data.get('reachout_world_programs', 0),
                'Rhapathon': record_data.get('rhapathon', 0),
                'World Nations': record_data.get('reachout_world_nations', 0),
                'Say Yes to Kids': record_data.get('say_yes_to_kids', 0),
                'Teevolution': record_data.get('teevolution', 0),
                'Youth Aglow': record_data.get('youth_aglow', 0),
                'No One Left Behind': record_data.get('no_one_left_behind', 0),
                'Penetrating Truth': record_data.get('penetrating_truth', 0),
                'Penetrating Languages': record_data.get('penetrating_languages', 0),
                'Adopt a Street': record_data.get('adopt_a_street', 0),
                'Submission Date': row['submission_date']
            })
        
        return pd.DataFrame(records_data)
    except Exception as e:
        st.error(f"Error getting ROR records: {e}")
        return pd.DataFrame()

def fetch_church_partner_records():
    """Fetch all church partner records including ROR"""
    try:
        conn = sqlite3.connect('church_partners.db')
        c = conn.cursor()
        c.execute("""SELECT id, record_type, record_data, submission_date 
                    FROM church_partner_records""")
        records = c.fetchall()
        conn.close()
        return records
    except Exception as e:
        st.error(f"Error fetching church partner records: {e}")
        return []

def analytics_dashboard():
    """Partner analytics dashboard"""
    st.title("Partner Analytics")
    
    # Use ESPEES as default currency
    display_currency = 'ESPEES'
    
    # Fetch all partner records
    df = fetch_all_partner_records()
    
    if df.empty:
        st.warning("No partner records found.")
        return
    
    # Extract fields from record_data
    df['wonder_challenge'] = df['record_data'].apply(lambda x: float(x.get('total_wonder_challenge', 0)))
    df['rhapsody_languages'] = df['record_data'].apply(lambda x: float(x.get('total_rhapsody_languages', 0)))
    df['kiddies_products'] = df['record_data'].apply(lambda x: float(x.get('total_kiddies_products', 0)))
    df['teevo'] = df['record_data'].apply(lambda x: float(x.get('total_teevo', 0)))
    df['braille_nolb'] = df['record_data'].apply(lambda x: float(x.get('total_braille_nolb', 0)))
    df['youth_aglow'] = df['record_data'].apply(lambda x: float(x.get('total_youth_aglow', 0)))
    df['local_distribution'] = df['record_data'].apply(lambda x: float(x.get('total_local_distribution', 0)))
    df['subscriptions_dubais'] = df['record_data'].apply(lambda x: float(x.get('total_subscriptions_dubais', 0)))
    
    # Add filters in columns
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Partner type filter
        partner_types = ['All'] + sorted(df['record_type'].unique().tolist())
        selected_type = st.selectbox(
            "Filter by Partner Type", 
            partner_types,
            key="partner_type"
        )
    
    with col2:
        # Zone filter
        zones = ['All'] + sorted(df['zone'].unique().tolist())
        selected_zone = st.selectbox(
            "Filter by Zone", 
            zones,
            key="partner_zone"
        )
    
    with col3:
        # Analysis type selection
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Quantity", "Amount"],
            key="partner_analysis_type"
        )
    
    # Add search filter with expanded functionality
    search_term = st.text_input("Search (Name, Title, Zone, Email, Church, Group)", key="partner_analytics_search")
    
    # Apply filters
    filtered_df = df.copy()
    if selected_type != 'All':
        filtered_df = filtered_df[filtered_df['record_type'] == selected_type]
    if selected_zone != 'All':
        filtered_df = filtered_df[filtered_df['zone'] == selected_zone]
    if search_term:
        # Search across multiple fields
        filtered_df = filtered_df[
            filtered_df['id'].astype(str).str.contains(search_term, case=False, na=False) |
            filtered_df['first_name'].str.contains(search_term, case=False, na=False) |
            filtered_df['surname'].str.contains(search_term, case=False, na=False) |
            filtered_df['title'].str.contains(search_term, case=False, na=False) |
            filtered_df['zone'].str.contains(search_term, case=False, na=False) |
            filtered_df['record_data'].apply(lambda x: 
                str(x.get('email', '')).lower().contains(search_term.lower()) or
                str(x.get('church', '')).lower().contains(search_term.lower()) or
                str(x.get('group', '')).lower().contains(search_term.lower()) or
                str(x.get('kingschat_phone', '')).lower().contains(search_term.lower())
            )
        ]
    
    # Prepare display columns based on analysis type
    if analysis_type == "Quantity":
        display_columns = [
            'record_type', 'title', 'first_name', 'surname', 'zone',
            'wonder_challenge', 'rhapsody_languages', 'kiddies_products',
            'teevo', 'braille_nolb', 'youth_aglow', 'local_distribution',
            'subscriptions_dubais', 'submission_date'
        ]
    else:  # Amount
        filtered_df['Display Amount'] = filtered_df.apply(
            lambda row: f"{row['original_amount']:,.2f} {row['currency']} "
                       f"({row['grand_total']:,.2f} {display_currency})",
            axis=1
        )
        display_columns = [
            'record_type', 'title', 'first_name', 'surname', 'zone',
            'Display Amount', 'submission_date'
        ]
    
    # Display filtered results
    st.subheader("Filtered Results")
    st.dataframe(filtered_df[display_columns], use_container_width=True)

def view_partner_reports(is_admin=False, user_zone=None):
    """View partner records reports with financial edit for admin"""
    st.subheader("Partner Reports")
    
    # Display records in dataframe
    filtered_df = get_filtered_partner_records(user_zone)
    if filtered_df.empty:
        st.warning("No partner records found.")
        return
        
    # Enhanced search functionality
    search_term = st.text_input("Search by ID, Name, Title, Email, Church, Group, Zone, Phone", 
                               key="admin_partner_search")
    if search_term:
        filtered_df = filtered_df[
            filtered_df['id'].astype(str).str.contains(search_term, case=False, na=False) |
            filtered_df['first_name'].str.contains(search_term, case=False, na=False) |
            filtered_df['surname'].str.contains(search_term, case=False, na=False) |
            filtered_df['title'].str.contains(search_term, case=False, na=False) |
            filtered_df['zone'].str.contains(search_term, case=False, na=False) |
            filtered_df['record_data'].apply(lambda x: 
                str(x.get('email', '')).lower().contains(search_term.lower()) or
                str(x.get('church', '')).lower().contains(search_term.lower()) or
                str(x.get('group', '')).lower().contains(search_term.lower()) or
                str(x.get('kingschat_phone', '')).lower().contains(search_term.lower())
            )
        ]
    
    st.dataframe(filtered_df, use_container_width=True)
    
    # Add financial edit section for admin
    if is_admin:
        st.subheader("Edit Financial Records")
        
        # Add search functionality for editing
        edit_search_term = st.text_input(
            "Search Record to Edit (ID, Name, Title, Email, Church, Group, Zone, Phone)",
            key="admin_edit_search"
        )
        
        edit_results_df = filtered_df
        if edit_search_term:
            edit_results_df = apply_partner_search(filtered_df, edit_search_term)
        
        if not edit_results_df.empty:
            st.write("### Search Results")
            for idx, row in edit_results_df.iterrows():
                record_id = str(row['id'])
                unique_id = get_unique_record_id(record_id, row['record_type'])
                col1, col2 = st.columns([4, 1])
                
                with col1:
                    st.write(f"""
                    **ID:** {record_id} ({row['record_type']})  
                    **Name:** {row['title']} {row['first_name']} {row['surname']}  
                    **Zone:** {row['zone']}
                    """)
                
                with col2:
                    if st.button("Edit", key=f"admin_edit_btn_{unique_id}"):
                        st.session_state.admin_editing_record = record_id
                        st.session_state.admin_editing_type = row['record_type']
            
            # Show edit form if a record is selected
            if hasattr(st.session_state, 'admin_editing_record'):
                record = get_partner_record(
                    st.session_state.admin_editing_record,
                    st.session_state.admin_editing_type
                )
                
                if record:
                    unique_id = get_unique_record_id(
                        st.session_state.admin_editing_record,
                        st.session_state.admin_editing_type
                    )
                    with st.form(key=f"edit_form_{unique_id}"):
                        st.write(f"""
                        ### Edit Financial Records
                        **Partner Type:** {st.session_state.admin_editing_type}  
                        **Name:** {record.get('first_name')} {record.get('surname')}
                        """)
                        
                        # Financial fields with unique keys
                        col1, col2 = st.columns(2)
                        with col1:
                            wonder_challenge = st.number_input(
                                "Wonder Challenge", 
                                value=float(record.get('total_wonder_challenge', 0)),
                                key=f"wc_{unique_id}"
                            )
                            kiddies_products = st.number_input(
                                "Kiddies Products", 
                                value=float(record.get('total_kiddies_products', 0)),
                                key=f"kp_{unique_id}"
                            )
                            braille_nolb = st.number_input(
                                "Braille(NOLB)", 
                                value=float(record.get('total_braille_nolb', 0)),
                                key=f"bn_{unique_id}"
                            )
                            local_distribution = st.number_input(
                                "Local Distribution", 
                                value=float(record.get('total_local_distribution', 0)),
                                key=f"ld_{unique_id}"
                            )
                        
                        with col2:
                            rhapsody_languages = st.number_input(
                                "Rhapsody Languages", 
                                value=float(record.get('total_rhapsody_languages', 0)),
                                key=f"rl_{unique_id}"
                            )
                            teevo = st.number_input(
                                "Teevo", 
                                value=float(record.get('total_teevo', 0)),
                                key=f"tv_{unique_id}"
                            )
                            youth_aglow = st.number_input(
                                "Youth Aglow", 
                                value=float(record.get('total_youth_aglow', 0)),
                                key=f"ya_{unique_id}"
                            )
                            subscriptions_dubais = st.number_input(
                                "Subscriptions/Dubais", 
                                value=float(record.get('total_subscriptions_dubais', 0)),
                                key=f"sd_{unique_id}"
                            )
                        
                        submit = st.form_submit_button("Update Financial Records")
                        
                        if submit:
                            updated_amounts = {
                                'total_wonder_challenge': wonder_challenge,
                                'total_rhapsody_languages': rhapsody_languages,
                                'total_kiddies_products': kiddies_products,
                                'total_teevo': teevo,
                                'total_braille_nolb': braille_nolb,
                                'total_youth_aglow': youth_aglow,
                                'total_local_distribution': local_distribution,
                                'total_subscriptions_dubais': subscriptions_dubais
                            }
                            
                            success, message = edit_financial_record(
                                st.session_state.admin_editing_record, 
                                st.session_state.admin_editing_type,
                                updated_amounts
                            )
                            
                            if success:
                                st.success(message)
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                st.error(message)

# Add this helper function to generate unique record identifier
def get_unique_record_id(record_id, record_type):
    """Generate a unique identifier combining record ID and type"""
    type_prefix = {
        'Adult Partner': 'AP',
        'Child Partner': 'CP',
        'Teenager Partner': 'TP',
        'External Partner': 'EP'
    }.get(record_type, 'XX')
    return f"{type_prefix}_{record_id}"

# Modify the search results display in view_reports_ui_readonly
def view_reports_ui_readonly(user_zone):
    """View reports interface for RZMs with financial edit capability"""
    st.subheader("View Reports")
    
    # Display records in dataframe
    filtered_df = get_filtered_partner_records(user_zone)
    if filtered_df.empty:
        st.warning("No partner records found.")
        return
    
    # Enhanced search functionality
    search_term = st.text_input("Search by ID, Name, Title, Email, Church, Group, Zone, Phone", 
                               key="rzm_partner_search")
    if search_term:
        filtered_df = filtered_df[
            filtered_df['id'].astype(str).str.contains(search_term, case=False, na=False) |
            filtered_df['first_name'].str.contains(search_term, case=False, na=False) |
            filtered_df['surname'].str.contains(search_term, case=False, na=False) |
            filtered_df['title'].str.contains(search_term, case=False, na=False) |
            filtered_df['zone'].str.contains(search_term, case=False, na=False) |
            filtered_df['record_data'].apply(lambda x: 
                str(x.get('email', '')).lower().contains(search_term.lower()) or
                str(x.get('church', '')).lower().contains(search_term.lower()) or
                str(x.get('group', '')).lower().contains(search_term.lower()) or
                str(x.get('kingschat_phone', '')).lower().contains(search_term.lower())
            )
        ]
    
    st.dataframe(filtered_df, use_container_width=True)
    
    # Add financial edit section for RZMs
    st.subheader("Edit Financial Records")
    
    # Add search functionality for editing
    edit_search_term = st.text_input(
        "Search Record to Edit (ID, Name, Title, Email, Church, Group, Zone, Phone)",
        key="rzm_edit_search"
    )
    
    edit_results_df = filtered_df
    if edit_search_term:
        edit_results_df = apply_partner_search(filtered_df, edit_search_term)
    
    if not edit_results_df.empty:
        st.write("### Search Results")
        for idx, row in edit_results_df.iterrows():
            record_id = str(row['id'])
            unique_id = get_unique_record_id(record_id, row['record_type'])
            col1, col2 = st.columns([4, 1])
            
            with col1:
                st.write(f"""
                **ID:** {record_id} ({row['record_type']})  
                **Name:** {row['title']} {row['first_name']} {row['surname']}  
                **Zone:** {row['zone']}
                """)
            
            with col2:
                if st.button("Edit", key=f"edit_btn_{unique_id}"):
                    st.session_state.editing_record = record_id
                    st.session_state.editing_type = row['record_type']
        
        # Show edit form if a record is selected
        if hasattr(st.session_state, 'editing_record'):
            record = get_partner_record(
                st.session_state.editing_record,
                st.session_state.editing_type
            )
            
            if record:
                unique_id = get_unique_record_id(
                    st.session_state.editing_record,
                    st.session_state.editing_type
                )
                with st.form(key=f"edit_form_{unique_id}"):
                    st.write(f"""
                    ### Edit Financial Records
                    **Partner Type:** {st.session_state.editing_type}  
                    **Name:** {record.get('first_name')} {record.get('surname')}
                    """)
                    
                    # Financial fields with unique keys
                    col1, col2 = st.columns(2)
                    with col1:
                        wonder_challenge = st.number_input(
                            "Wonder Challenge", 
                            value=float(record.get('total_wonder_challenge', 0)),
                            key=f"wc_{unique_id}"
                        )
                        kiddies_products = st.number_input(
                            "Kiddies Products", 
                            value=float(record.get('total_kiddies_products', 0)),
                            key=f"kp_{unique_id}"
                        )
                        braille_nolb = st.number_input(
                            "Braille(NOLB)", 
                            value=float(record.get('total_braille_nolb', 0)),
                            key=f"bn_{unique_id}"
                        )
                        local_distribution = st.number_input(
                            "Local Distribution", 
                            value=float(record.get('total_local_distribution', 0)),
                            key=f"ld_{unique_id}"
                        )
                    
                    with col2:
                        rhapsody_languages = st.number_input(
                            "Rhapsody Languages", 
                            value=float(record.get('total_rhapsody_languages', 0)),
                            key=f"rl_{unique_id}"
                        )
                        teevo = st.number_input(
                            "Teevo", 
                            value=float(record.get('total_teevo', 0)),
                            key=f"tv_{unique_id}"
                        )
                        youth_aglow = st.number_input(
                            "Youth Aglow", 
                            value=float(record.get('total_youth_aglow', 0)),
                            key=f"ya_{unique_id}"
                        )
                        subscriptions_dubais = st.number_input(
                            "Subscriptions/Dubais", 
                            value=float(record.get('total_subscriptions_dubais', 0)),
                            key=f"sd_{unique_id}"
                        )
                    
                    submit = st.form_submit_button("Update Financial Records")
                    
                    if submit:
                        updated_amounts = {
                            'total_wonder_challenge': wonder_challenge,
                            'total_rhapsody_languages': rhapsody_languages,
                            'total_kiddies_products': kiddies_products,
                            'total_teevo': teevo,
                            'total_braille_nolb': braille_nolb,
                            'total_youth_aglow': youth_aglow,
                            'total_local_distribution': local_distribution,
                            'total_subscriptions_dubais': subscriptions_dubais
                        }
                        
                        success, message = edit_financial_record(
                            st.session_state.editing_record, 
                            st.session_state.editing_type,
                            updated_amounts
                        )
                        
                        if success:
                            st.success(message)
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(message)

# Also add these helper functions for partner record operations
def get_partner_record(record_id, record_type):
    """Fetch a specific partner record"""
    try:
        conn = sqlite3.connect('partner_records.db')
        c = conn.cursor()
        
        table_map = {
            'Adult Partner': 'adult_partners',
            'Child Partner': 'children_partners',
            'Teenager Partner': 'teenager_partners',
            'External Partner': 'external_partners'
        }
        
        table_name = table_map.get(record_type)
        if not table_name:
            return None
            
        c.execute(f"""SELECT record_data 
                    FROM {table_name} 
                    WHERE id = ?""", 
                 (record_id,))
        record = c.fetchone()
        conn.close()
        
        if record:
            return json.loads(record[0])
        return None
    except Exception as e:
        st.error(f"Error fetching partner record: {e}")
        return None

def update_partner_record(record_id, record_type, updated_data):
    """Update an existing partner record"""
    try:
        conn = sqlite3.connect('partner_records.db')
        c = conn.cursor()
        
        table_map = {
            'Adult Partner': 'adult_partners',
            'Child Partner': 'children_partners',
            'Teenager Partner': 'teenager_partners',
            'External Partner': 'external_partners'
        }
        
        table_name = table_map.get(record_type)
        if not table_name:
            return False, "Invalid record type"
        
        # Calculate totals and convert currency
        original_amount = sum([
            float(updated_data.get('total_wonder_challenge', 0)),
            float(updated_data.get('total_rhapsody_languages', 0)),
            float(updated_data.get('total_kiddies_products', 0)),
            float(updated_data.get('total_teevo', 0)),
            float(updated_data.get('total_braille_nolb', 0)),
            float(updated_data.get('total_youth_aglow', 0)),
            float(updated_data.get('total_local_distribution', 0)),
            float(updated_data.get('total_subscriptions_dubais', 0))
        ])
        
        grand_total = convert_to_espees(original_amount, updated_data['currency'])
        
        # Add calculated totals to updated data
        updated_data.update({
            'original_amount': original_amount,
            'grand_total': grand_total
        })
        
        # Convert data to JSON string
        record_json = json.dumps(updated_data)
        
        # Update the record
        c.execute(f"""UPDATE {table_name} 
                    SET record_data = ?, 
                        submission_date = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                 (record_json, record_id))
        
        conn.commit()
        conn.close()
        return True, "Record updated successfully!"
    except Exception as e:
        return False, f"Error updating record: {e}"

def edit_financial_record(record_id, record_type, updated_amounts):
    """Edit financial amounts for a partner record"""
    try:
        conn = sqlite3.connect('partner_records.db')
        c = conn.cursor()
        
        # Get the current record data
        table_map = {
            'Adult Partner': 'adult_partners',
            'Child Partner': 'children_partners',
            'Teenager Partner': 'teenager_partners',
            'External Partner': 'external_partners'
        }
        
        table_name = table_map.get(record_type)
        if not table_name:
            return False, "Invalid record type"
            
        c.execute(f"SELECT record_data FROM {table_name} WHERE id = ?", (record_id,))
        record = c.fetchone()
        
        if not record:
            return False, "Record not found"
            
        # Parse existing data
        record_data = json.loads(record[0])
        
        # Update only financial fields
        for field, value in updated_amounts.items():
            record_data[field] = value
        
        # Recalculate totals
        original_amount = sum(float(value) for value in updated_amounts.values())
        grand_total = convert_to_espees(original_amount, record_data['currency'])
        
        # Update totals
        record_data['original_amount'] = original_amount
        record_data['grand_total'] = grand_total
        
        # Save updated record
        record_json = json.dumps(record_data)
        c.execute(f"""UPDATE {table_name} 
                    SET record_data = ?, 
                        submission_date = CURRENT_TIMESTAMP
                    WHERE id = ?""",
                 (record_json, record_id))
        
        conn.commit()
        conn.close()
        return True, "Financial records updated successfully!"
    except Exception as e:
        return False, f"Error updating financial records: {e}"

if __name__ == "__main__":
    try:
        init_db()
        init_partner_db()
        load_conversion_rates()  # Add this line to load saved rates
        main()
    except Exception as e:
        st.error(f"A critical error occurred: {e}")

