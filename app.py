import streamlit as st
import sqlite3
import hashlib
import os
import json
import pandas as pd
from datetime import datetime, timedelta
import io
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.filters import FilterColumn, Filters
from openpyxl.utils import get_column_letter
from calendar import month_name
import time
import struct
import re

# Add these lines at the beginning of the script, after the imports
st.set_page_config(
    page_title="GPD ADMIN",
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
with open('zones_data.json', 'r') as f:
    zones_data = json.load(f)

# Updated Database setup
def init_db():
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (username TEXT PRIMARY KEY, password TEXT, full_name TEXT, email TEXT, user_group TEXT, sub_group TEXT, region TEXT, zone TEXT)''')
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"An error occurred while initializing the users database: {e}")
    finally:
        conn.close()

    try:
        conn = sqlite3.connect('reports.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS reports
                     (id TEXT PRIMARY KEY,
                      username TEXT,
                      zone TEXT,
                      year INTEGER,
                      month INTEGER,
                      report_data TEXT,
                      submission_date DATETIME)''')
        conn.commit()
    except sqlite3.Error as e:
        st.error(f"An error occurred while initializing the reports database: {e}")
    finally:
        conn.close()

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
        st.session_state.is_regional_manager = user[5] == "Regional Manager"  # Assuming sub_group is at index 5
        st.session_state.region = user[6]  # Assuming region is stored in the 7th column of the users table
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

# Main app
def main():
    try:
        st.title("GPD ADMIN")
        if st.session_state.logged_in:
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
    if st.session_state.is_super_admin:
        display_admin_dashboard()
    elif st.session_state.is_regional_manager:
        display_regional_manager_dashboard()
    else:
        display_user_dashboard()

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.is_super_admin = False
        st.session_state.is_regional_manager = False
        st.rerun()

def display_admin_dashboard():
    try:
        # Remove "GPD Admin Portal" from here
        st.write("Welcome, Super Admin!")
        st.subheader("Super Admin Dashboard")

        # Create tabs for different admin functions
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Dashboard", "User Management", "View Reports", "Manage Reports", "Edit Requests"])

        with tab1:
            st.subheader("Admin Dashboard")
            
            # User Statistics
            users = fetch_all_users()
            total_users = len(users)
            st.write(f"Total Users: {total_users}")

            # User breakdown by role
            user_roles = pd.DataFrame(users, columns=["Username", "Full Name", "Email", "User Group", "Sub Group", "Region", "Zone"])
            role_counts = user_roles['User Group'].value_counts().reset_index()
            role_counts.columns = ['User Group', 'Count']
            st.write("User Breakdown by Role:")
            st.table(role_counts)

            # User breakdown by GPD sub-groups
            gpd_users = user_roles[user_roles['User Group'] == 'GPD']
            gpd_subgroup_counts = gpd_users['Sub Group'].value_counts().reset_index()
            gpd_subgroup_counts.columns = ['Sub Group', 'Count']
            st.write("GPD Users Breakdown by Sub-group:")
            st.table(gpd_subgroup_counts)

            # User breakdown by RZM regions
            rzm_users = user_roles[user_roles['User Group'] == 'RZM']
            rzm_region_counts = rzm_users['Region'].value_counts().reset_index()
            rzm_region_counts.columns = ['Region', 'Count']
            st.write("RZM Users Breakdown by Region:")
            st.table(rzm_region_counts)

            # Report Statistics
            reports = fetch_reports()
            total_reports, metrics_sum = calculate_report_metrics(reports)
            st.write(f"Total Reports Submitted: {total_reports}")
            st.write("Metrics Summary:")
            metrics_df = pd.DataFrame(list(metrics_sum.items()), columns=['Metric', 'Total'])
            st.table(metrics_df)

        with tab2:
            # User Management Section
            st.subheader("User Management")
            users = fetch_all_users()
            
            # Display users in a table
            user_df = pd.DataFrame(users, columns=["Username", "Full Name", "Email", "User Group", "Sub Group", "Region", "Zone"])
            st.dataframe(user_df)

            # User editing
            st.subheader("Edit User")
            selected_user = st.selectbox("Select a user to edit", [user[0] for user in users])
            user_to_edit = next((user for user in users if user[0] == selected_user), None)

            if user_to_edit:
                with st.form("edit_user_form"):
                    new_full_name = st.text_input("Full Name", value=user_to_edit[1])
                    new_email = st.text_input("Email", value=user_to_edit[2])
                    new_user_group = st.selectbox("User Group", ["GPD", "RZM"], index=["GPD", "RZM"].index(user_to_edit[3]))
                    
                    new_sub_group = None
                    new_region = None
                    new_zone = None

                    if new_user_group == "GPD":
                        new_sub_group = st.selectbox("Sub Group", ["Finance", "IT", "Reporting/Admin", "Admin Manager", "Regional Manager"], index=["Finance", "IT", "Reporting/Admin", "Admin Manager", "Regional Manager"].index(user_to_edit[4] or "Finance"))
                        if new_sub_group in ["Admin Manager", "Regional Manager"]:
                            new_region = st.selectbox("Region", [f"Region {i}" for i in range(1, 7)], index=[f"Region {i}" for i in range(1, 7)].index(user_to_edit[5] or "Region 1"))
                    elif new_user_group == "RZM":
                        new_region = st.selectbox("Region", list(zones_data.keys()), index=list(zones_data.keys()).index(user_to_edit[5] or list(zones_data.keys())[0]))
                        if new_region:
                            new_zone = st.selectbox("Zone", zones_data[new_region], index=zones_data[new_region].index(user_to_edit[6] or zones_data[new_region][0]))

                    if st.form_submit_button("Update User"):
                        update_user(selected_user, new_full_name, new_email, new_user_group, new_sub_group, new_region, new_zone)
                        st.success(f"User {selected_user} updated successfully!")
                        st.rerun()

            # User deletion
            st.subheader("Delete User")
            user_to_delete = st.selectbox("Select a user to delete", [user[0] for user in users])
            if st.button("Delete User"):
                delete_user(user_to_delete)
                st.success(f"User {user_to_delete} deleted successfully!")
                st.rerun()

        with tab3:
            # View Submitted Reports Section
            st.subheader("View Submitted Reports")
            reports = fetch_reports()
            if reports:
                report_df = pd.DataFrame(reports, columns=["ID", "Username", "Zone", "Year", "Month", "Report Data", "Submission Date"])
                
                # View detailed report
                view_report_details(report_df)

                # Remove the individual download button
                # Keep only the "Download All Reports as Excel" button, which is inside the view_report_details function
            else:
                st.write("No reports submitted yet.")

        with tab4:
            # Manage Submitted Reports Section
            st.subheader("Manage Submitted Reports")
            reports = fetch_reports()
            if reports:
                report_df = pd.DataFrame(reports, columns=["ID", "Username", "Zone", "Year", "Month", "Report Data", "Submission Date"])
                st.dataframe(report_df[["ID", "Username", "Zone", "Year", "Month", "Submission Date"]])

                # Edit report
                st.subheader("Edit Report")
                report_id_to_edit = st.selectbox("Select a report to edit", report_df['ID'])
                report_to_edit = report_df[report_df['ID'] == report_id_to_edit].iloc[0]
                
                with st.form("edit_report_form"):
                    new_username = st.text_input("Username", value=report_to_edit['Username'], key=f"username_{report_id_to_edit}")
                    new_zone = st.text_input("Zone", value=report_to_edit['Zone'], key=f"zone_{report_id_to_edit}")
                    
                    # Handle potentially binary data for Year and Month
                    try:
                        year_value = int(report_to_edit['Year'])
                    except (ValueError, TypeError):
                        year_value = datetime.now().year  # Default to current year if conversion fails
                    
                    try:
                        month_value = int(report_to_edit['Month'])
                    except (ValueError, TypeError):
                        month_value = 1  # Default to January if conversion fails
                
                    new_year = st.number_input("Year", min_value=2020, max_value=datetime.now().year, value=year_value, key=f"year_{report_id_to_edit}")
                    new_month = st.selectbox("Month", range(1, 13), index=month_value-1, format_func=lambda x: datetime(2000, x, 1).strftime('%B'), key=f"month_{report_id_to_edit}")
                    
                    report_data = json.loads(report_to_edit['Report Data'])
                    new_report_data = {}
                    for key, value in report_data.items():
                        try:
                            new_report_data[key] = st.number_input(key, value=int(value), key=f"admin_edit_{report_id_to_edit}_{key}")
                        except (ValueError, TypeError):
                            st.error(f"Invalid value for {key}: {value}")
                            new_report_data[key] = st.number_input(key, value=0, key=f"admin_edit_{report_id_to_edit}_{key}_error")

                    if st.form_submit_button("Update Report"):
                        update_report(report_id_to_edit, new_username, new_zone, new_year, new_month, new_report_data)
                        st.success(f"Report {report_id_to_edit} updated successfully!")
                        st.rerun()

                # Delete report
                st.subheader("Delete Report")
                report_id_to_delete = st.selectbox("Select a report to delete", report_df['ID'])
                if st.button("Delete Report"):
                    delete_report(report_id_to_delete)
                    st.success(f"Report {report_id_to_delete} deleted successfully!")
                    st.rerun()
            else:
                st.write("No reports submitted yet.")

        with tab5:
            st.subheader("Manage Edit Requests")
            edit_requests = get_edit_requests()
            if edit_requests:
                for request in edit_requests:
                    st.write(f"User: {request[1]}, Report ID: {request[2]}, Reason: {request[3]}")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"Approve {request[0]}"):
                            expiry_days = st.number_input("Edit access duration (days)", min_value=1, max_value=30, value=7)
                            expiry_date = datetime.now() + timedelta(days=expiry_days)
                            update_edit_request(request[0], "Approved", expiry_date)
                            st.success(f"Edit request {request[0]} approved for {expiry_days} days.")
                            time.sleep(1)  # Give the user a moment to see the success message
                            st.rerun()  # Reload the page
                    with col2:
                        if st.button(f"Reject {request[0]}"):
                            update_edit_request(request[0], "Rejected")
                            st.success(f"Edit request {request[0]} rejected.")
                            time.sleep(1)  # Give the user a moment to see the success message
                            st.rerun()  # Reload the page
            else:
                st.write("No pending edit requests.")
    except Exception as e:
        st.error(f"An error occurred while displaying the admin dashboard: {e}")

# Add these new functions to handle report updates and deletions
def update_report(report_id, username, zone, year, month, report_data):
    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    report_json = json.dumps(report_data)
    c.execute("""UPDATE reports SET username=?, zone=?, year=?, month=?, report_data=?, submission_date=?
                 WHERE id=?""", (username, zone, year, month, report_json, datetime.now(), report_id))
    conn.commit()
    conn.close()

def delete_report(report_id):
    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    c.execute("DELETE FROM reports WHERE id=?", (report_id,))
    conn.commit()
    conn.close()

def display_user_dashboard():
    try:
        st.write(f"Welcome, {st.session_state.username}!")
        st.subheader("User Dashboard")

        user_details = get_user_details(st.session_state.username)
        user_group, sub_group, region, zone = user_details

        # Create tabs for different sections
        if user_group == "GPD" and sub_group == "Reporting/Admin":
            tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "View All RZM Reports", "View Your Submitted Reports", "Submit New Report"])
        elif user_group == "RZM":
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["Dashboard", "View Your Submitted Reports", "Submit New Report", "Edit Reports", "Edit Requests"])
        else:
            tab1, tab2, tab3 = st.tabs(["Dashboard", "View Your Submitted Reports", "Submit New Report"])

        # Fetch user reports once and create report_df
        user_reports = fetch_reports(st.session_state.username)
        if user_reports:
            report_df = pd.DataFrame(user_reports, columns=["ID", "Username", "Zone", "Year", "Month", "Report Data", "Submission Date"])
        else:
            report_df = pd.DataFrame()

        with tab1:
            st.subheader("Your Dashboard")
            user_reports = fetch_reports(st.session_state.username)
            total_reports, metrics_sum = calculate_report_metrics(user_reports)
            st.write(f"Total Reports Submitted: {total_reports}")

            # Add filters
            st.subheader("Filter Dashboard")
            time_period_options = get_time_period_options()
            filter_type = st.selectbox("Filter by Time Period", ['All Time', 'Annual', 'Quarterly', 'Half-Year', 'Monthly'], key="dashboard_filter_type")
            
            if filter_type != 'All Time':
                filter_value = st.selectbox(f"Select {filter_type}", time_period_options[filter_type], key="dashboard_filter_value")

                # Apply filters
                filtered_reports = user_reports
                if filter_type == 'Annual':
                    filtered_reports = [r for r in user_reports if r[3] == int(filter_value)]
                elif filter_type == 'Quarterly':
                    year, quarter = filter_value.split()
                    quarter_month_map = {'Q1': [1, 2, 3], 'Q2': [4, 5, 6], 'Q3': [7, 8, 9], 'Q4': [10, 11, 12]}
                    filtered_reports = [r for r in user_reports if r[3] == int(year) and r[4] in quarter_month_map[quarter]]
                elif filter_type == 'Half-Year':
                    year, half = filter_value.split()
                    half_year_month_map = {'H1': [1, 2, 3, 4, 5, 6], 'H2': [7, 8, 9, 10, 11, 12]}
                    filtered_reports = [r for r in user_reports if r[3] == int(year) and r[4] in half_year_month_map[half]]
                elif filter_type == 'Monthly':
                    year, month = filter_value.split()
                    month_num = datetime.strptime(month, '%B').month
                    filtered_reports = [r for r in user_reports if r[3] == int(year) and r[4] == month_num]

                total_reports, metrics_sum = calculate_report_metrics(filtered_reports)
                st.write(f"Filtered Reports: {total_reports}")

            st.write("Metrics Summary:")
            metrics_df = pd.DataFrame(list(metrics_sum.items()), columns=['Metric', 'Total'])
            st.table(metrics_df)

        if user_group == "GPD" and sub_group == "Reporting/Admin":
            with tab2:
                st.subheader("View All RZM Reports")
                all_rzm_reports = fetch_reports()
                if all_rzm_reports:
                    all_rzm_report_df = pd.DataFrame(all_rzm_reports, columns=["ID", "Username", "Zone", "Year", "Month", "Report Data", "Submission Date"])
                    view_report_details(all_rzm_report_df)
                else:
                    st.write("No RZM reports submitted yet.")

        with tab3:
            st.subheader("Submit New Report")
            if user_group == "GPD":
                st.write("Reporting functionality for GPD users is coming soon!")
            elif user_group == "RZM":
                st.write(f"RZM: {st.session_state.username}")
                st.write(f"Zone: {zone}")

                year = st.selectbox("Year", range(datetime.now().year, 2020, -1))
                month = st.selectbox("Month", range(1, 13), format_func=lambda x: datetime(2000, x, 1).strftime('%B'))

                # Check if a report already exists for this year and month
                existing_report = check_existing_report(st.session_state.username, year, month)
                if existing_report:
                    st.warning(f"A report for {month_name[month]} {year} has already been submitted. To make changes, please request edit access.")
                
                report_fields = [
                    "Wonder Alerts", "SYTK Alerts", "RRM", "Total Distribution", "No of Souls Won",
                    "No of Rhapsody Outreaches", "No of Rhapsody Cells", "No of New Churches",
                    "No of New Partners Enlisted", "No of Lingual Cells", "No of Language Churches",
                    "No of Languages Sponsored", "No of Distribution Centers", "No of Groups Who Have Selected 1M",
                    "No of Groups Achieved 1M Copies", "No of Groups Achieved 500k Copies",
                    "No of Groups Achieved 250k Copies", "No of Groups Achieved 100k Copies",
                    "Prayer Programs", "Partner Programs", "No of External Ministers",
                    "ISEED Daily Partners", "Language Ambassadors"
                ]

                report_data = {}
                for field in report_fields:
                    report_data[field] = st.number_input(field, min_value=0, value=0)

                if st.button("Submit Report"):
                    if existing_report:
                        st.error("A report for this month already exists. To make changes, please request edit access.")
                    else:
                        success, message = save_report(st.session_state.username, zone, year, month, report_data)
                        if success:
                            st.success(message)
                            time.sleep(1)  # Give the user a moment to see the success message
                            st.rerun()
                        else:
                            st.error(message)

        if user_group == "RZM":
            with tab4:
                st.subheader("Edit Reports")
                if not report_df.empty:
                    report_to_edit = st.selectbox("Select a report to edit", report_df['ID'])
                    
                    if check_edit_permission(st.session_state.username, report_to_edit):
                        # Allow editing
                        edit_report(report_to_edit, report_df)
                    else:
                        st.warning("You don't have permission to edit this report. Please request edit access.")
                else:
                    st.write("You haven't submitted any reports yet.")

            with tab5:
                st.subheader("Edit Requests")
                if not report_df.empty:
                    report_to_request = st.selectbox("Select a report to request edit access", report_df['ID'])
                    reason = st.text_area("Reason for edit request")
                    if st.button("Submit Edit Request"):
                        request_edit_permission(st.session_state.username, report_to_request, reason)
                        st.success("Edit request submitted successfully!")
                        time.sleep(1)  # Give the user a moment to see the success message
                        st.rerun()
                else:
                    st.write("You haven't submitted any reports yet. You can't request edits for non-existent reports.")
    except Exception as e:
        st.error(f"An error occurred while displaying the user dashboard: {e}")

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

# Modify the "View Report Details" section in both admin and user dashboards
def view_report_details(report_df):
    st.subheader("View Report Details")

    # Add search functionality
    search_term = st.text_input("Search reports", "")
    if search_term:
        report_df = report_df[report_df.apply(lambda row: search_term.lower() in ' '.join(row.astype(str)).lower(), axis=1)]

    # Add filters
    filter_options = ['Annual', 'Half-Year', 'Quarterly', 'Monthly', 'Individual']
    filter_type = st.selectbox("Select filter type", filter_options)

    years = sorted(report_df['Year'].unique(), reverse=True)
    selected_year = st.selectbox("Select Year", years)

    filtered_df = report_df[report_df['Year'] == selected_year]

    if filter_type == 'Half-Year':
        half_year = st.selectbox("Select Half", ['H1', 'H2'])
        if half_year == 'H1':
            filtered_df = filtered_df[filtered_df['Month'].isin([1, 2, 3, 4, 5, 6])]
        else:
            filtered_df = filtered_df[filtered_df['Month'].isin([7, 8, 9, 10, 11, 12])]
    elif filter_type == 'Quarterly':
        quarter = st.selectbox("Select Quarter", ['Q1', 'Q2', 'Q3', 'Q4'])
        quarter_months = {'Q1': [1, 2, 3], 'Q2': [4, 5, 6], 'Q3': [7, 8, 9], 'Q4': [10, 11, 12]}
        filtered_df = filtered_df[filtered_df['Month'].isin(quarter_months[quarter])]
    elif filter_type == 'Monthly':
        month = st.selectbox("Select Month", range(1, 13), format_func=lambda x: month_name[x])
        filtered_df = filtered_df[filtered_df['Month'] == month]
    elif filter_type == 'Individual':
        if 'Username' in filtered_df.columns:
            usernames = sorted(filtered_df['Username'].unique())
            selected_username = st.selectbox("Select RZM", usernames)
            filtered_df = filtered_df[filtered_df['Username'] == selected_username]

    if 'Zone' in filtered_df.columns:
        zones = ['All'] + sorted(filtered_df['Zone'].unique())
        selected_zone = st.selectbox("Select Zone", zones)
        if selected_zone != 'All':
            filtered_df = filtered_df[filtered_df['Zone'] == selected_zone]

    if not filtered_df.empty:
        report_ids = ['All'] + filtered_df['ID'].tolist()
        selected_report_id = st.selectbox("Select a report to view details", report_ids)
        
        if st.button("View Report Details"):
            if selected_report_id == 'All':
                st.write("All Selected Reports")
                st.write("---")
                
                total_reports = len(filtered_df)
                st.write(f"Total Reports: {total_reports}")
                
                if 'Username' in filtered_df.columns:
                    unique_rzms = filtered_df['Username'].nunique()
                    st.write(f"Unique RZMs: {unique_rzms}")
                
                if 'Zone' in filtered_df.columns:
                    unique_zones = filtered_df['Zone'].nunique()
                    st.write(f"Unique Zones: {unique_zones}")
                
                st.write("---")
                st.write("Report Data:")
                
                # Create a DataFrame for all report data
                all_reports_data = []
                for _, row in filtered_df.iterrows():
                    report_data = json.loads(row['Report Data'])
                    report_row = {
                        "RZM Name": row['Username'],
                        "Zone": row['Zone'],
                        "Year": row['Year'],
                        "Month": month_name[row['Month']]
                    }
                    report_row.update(report_data)
                    all_reports_data.append(report_row)
                
                all_reports_df = pd.DataFrame(all_reports_data)
                
                # Display the DataFrame
                st.dataframe(all_reports_df)
                
                # Add download button for all data
                excel_data = download_excel(all_reports_df, "all_reports.xlsx")
                st.download_button(
                    label="Download All Reports as Excel",
                    data=excel_data,
                    file_name="all_reports.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                report = filtered_df[filtered_df['ID'] == selected_report_id].iloc[0]
                report_data = json.loads(report['Report Data'])
                
                # Ensure all values in report_data are properly decoded
                for key, value in report_data.items():
                    if isinstance(value, bytes):
                        try:
                            report_data[key] = struct.unpack('q', value)[0]
                        except struct.error:
                            report_data[key] = value.decode('utf-8', errors='replace')
                
                st.write("GPD Admin Portal - Report Data")
                st.write("---")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write("RZM Name:")
                    st.write("Zone:")
                    st.write("Year:")
                    st.write("Month:")
                with col2:
                    st.write(report['Username'])
                    st.write(report['Zone'])
                    try:
                        year = int(report['Year'])
                        month = int(report['Month'])
                        st.write(year)
                        st.write(month_name[month])
                    except (ValueError, TypeError):
                        st.write("Invalid Year/Month")
                
                st.write("---")
                st.write("Report Data:")
                
                # Create a DataFrame for the report data
                report_data_df = pd.DataFrame(list(report_data.items()), columns=['Metric', 'Value'])
                st.table(report_data_df)
    else:
        st.write("No reports available for the selected filters.")

# Add this new function to handle report editing
def edit_report(report_id, report_df):
    report = report_df[report_df['ID'] == report_id].iloc[0]
    report_data = json.loads(report['Report Data'])
    
    # Extract year and month from the report ID or use the values from the report
    try:
        year, month, _ = report_id.split('-')
        year = int(year)
        month = int(month)
    except ValueError:
        try:
            year = int(report['Year'])
            month = int(report['Month'])
        except (ValueError, TypeError):
            st.error(f"Invalid year or month value: Year={report['Year']}, Month={report['Month']}")
            return
    
    st.write(f"Editing report for {report['Zone']} - {month_name[month]} {year}")
    
    new_report_data = {}
    for field, value in report_data.items():
        try:
            new_report_data[field] = st.number_input(field, value=int(value), key=f"edit_{report_id}_{field}")
        except (ValueError, TypeError):
            st.error(f"Invalid value for {field}: {value}")
            new_report_data[field] = st.number_input(field, value=0, key=f"edit_{report_id}_{field}_error")
    
    if st.button("Save Changes", key=f"save_{report_id}"):
        update_report(report_id, report['Username'], report['Zone'], year, month, new_report_data)
        st.success("Report updated successfully!")
        time.sleep(1)  # Give the user a moment to see the success message
        st.rerun()

# Add this new function to fetch RZMs in a specific region
def fetch_rzms_in_region(region):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute("SELECT username, full_name, email, zone FROM users WHERE user_group='RZM' AND region=?", (region,))
    rzms = c.fetchall()
    conn.close()
    return rzms

# Modify the Regional Manager dashboard
def display_regional_manager_dashboard():
    try:
        st.write(f"Welcome, {st.session_state.username}!")
        st.subheader("Regional Manager Dashboard")

        # Get the regional manager's region
        region = st.session_state.region

        # Create tabs for Dashboard and View Reports
        tab1, tab2 = st.tabs(["Dashboard", "View Reports"])

        with tab1:
            st.subheader(f"Regional Dashboard for {region}")
            
            # Fetch the list of RZMs in the region
            rzms_in_region = fetch_rzms_in_region(region)
            st.write(f"RZMs in {region}:")
            rzm_df = pd.DataFrame(rzms_in_region, columns=["Username", "Full Name", "Email", "Zone"])
            st.dataframe(rzm_df)

            # Fetch and display regional-specific statistics and metrics
            reports = fetch_reports(region=region)
            if reports:
                total_reports, metrics_sum = calculate_report_metrics(reports)
                st.write(f"Total Reports Submitted in {region}: {total_reports}")
                st.write("Metrics Summary:")
                metrics_df = pd.DataFrame(list(metrics_sum.items()), columns=['Metric', 'Total'])
                st.table(metrics_df)
            else:
                st.write("No reports submitted yet in your region.")

        with tab2:
            st.subheader("View Submitted Reports")
            reports = fetch_reports(region=region)
            if reports:
                report_df = pd.DataFrame(reports, columns=["ID", "Username", "Zone", "Year", "Month", "Report Data", "Submission Date"])
                # View detailed report
                view_report_details(report_df)
            else:
                st.write("No reports submitted yet in your region.")
    except Exception as e:
        st.error(f"An error occurred while displaying the regional manager dashboard: {e}")

if __name__ == "__main__":
    try:
        init_db()
        main()
    except Exception as e:
        st.error(f"A critical error occurred: {e}")