import streamlit as st
import sqlite3
import hashlib
import os
import json
import pandas as pd
from datetime import datetime
import io
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.filters import FilterColumn, Filters
from openpyxl.utils import get_column_letter
from calendar import month_name

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.is_super_admin = False

# Load zones data
with open('zones_data.json', 'r') as f:
    zones_data = json.load(f)

# Updated Database setup
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (username TEXT PRIMARY KEY, password TEXT, full_name TEXT, email TEXT, user_group TEXT, sub_group TEXT, region TEXT, zone TEXT)''')
    conn.commit()
    conn.close()

    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT,
                  zone TEXT,
                  year INTEGER,
                  month INTEGER,
                  report_data TEXT,
                  submission_date DATETIME)''')
    conn.commit()
    conn.close()

# Hash password
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# User registration
def register_user(username, password, full_name, email, user_group, sub_group, region, zone):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    hashed_password = hash_password(password)
    try:
        c.execute("INSERT INTO users (username, password, full_name, email, user_group, sub_group, region, zone) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (username, hashed_password, full_name, email, user_group, sub_group, region, zone))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

# User login
def login_user(username, password):
    if username == "admin" and password == "12345":
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.is_super_admin = True
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
    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    report_json = json.dumps(report_data)
    report_id = f"{year}{month:02d}"  # Create ID as YYYYMM
    
    # Check if a report with this ID already exists
    c.execute("SELECT * FROM reports WHERE id=?", (report_id,))
    existing_report = c.fetchone()
    
    if existing_report:
        # Update existing report
        c.execute("""UPDATE reports SET username=?, zone=?, report_data=?, submission_date=?
                     WHERE id=?""", (username, zone, report_json, datetime.now(), report_id))
    else:
        # Insert new report
        c.execute("""INSERT INTO reports (id, username, zone, year, month, report_data, submission_date)
                     VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (report_id, username, zone, year, month, report_json, datetime.now()))
    
    conn.commit()
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
def fetch_reports(username=None):
    conn = sqlite3.connect('reports.db')
    c = conn.cursor()
    if username:
        c.execute("SELECT * FROM reports WHERE username=? ORDER BY id DESC", (username,))
    else:
        c.execute("SELECT * FROM reports ORDER BY id DESC")
    reports = c.fetchall()
    conn.close()
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

# Main app
def main():
    st.title("GPD Admin Portal")

    if st.session_state.logged_in:
        display_dashboard()
    else:
        display_login_register()

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
        user_group = st.selectbox("User Group", ["GPD", "RZM"], key="register_user_group")
        
        sub_group = None
        region = None
        zone = None
        
        if user_group == "GPD":
            sub_group = st.selectbox("Sub Group", ["Finance", "IT", "Reporting/Admin", "Admin Manager"], key="register_sub_group")
            if sub_group == "Admin Manager":
                region = st.selectbox("Region", [f"Region {i}" for i in range(1, 7)], key="register_region_gpd")
        elif user_group == "RZM":
            region = st.selectbox("Region", list(zones_data.keys()), key="register_region_rzm")
            if region:
                zone = st.selectbox("Zone", zones_data[region], key="register_zone")
        
        if st.button("Register"):
            if register_user(new_username, new_password, full_name, email, user_group, sub_group, region, zone):
                st.success("Registration successful! Please login.")
            else:
                st.error("Username already exists")

def display_dashboard():
    if st.session_state.is_super_admin:
        display_admin_dashboard()
    else:
        display_user_dashboard()

    if st.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.is_super_admin = False
        st.rerun()

def display_admin_dashboard():
    # Remove "GPD Admin Portal" from here
    st.write("Welcome, Super Admin!")
    st.subheader("Super Admin Dashboard")

    # Create tabs for different admin functions
    tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "User Management", "View Reports", "Manage Reports"])

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
                    new_sub_group = st.selectbox("Sub Group", ["Finance", "IT", "Reporting/Admin", "Admin Manager"], index=["Finance", "IT", "Reporting/Admin", "Admin Manager"].index(user_to_edit[4] or "Finance"))
                    if new_sub_group == "Admin Manager":
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
            
            # Search feature
            search_term = st.text_input("Search reports", "")
            
            # Filter reports based on search term
            if search_term:
                report_df = report_df[
                    report_df.apply(lambda row: search_term.lower() in ' '.join(row.astype(str)).lower(), axis=1)
                ]

            # Filter reports
            st.subheader("Filter Reports")
            
            # Username dropdown
            usernames = ['All'] + sorted(report_df['Username'].unique().tolist())
            filter_username = st.selectbox("Filter by Username", usernames)
            
            # Zone dropdown
            zones = ['All'] + sorted(report_df['Zone'].unique().tolist())
            filter_zone = st.selectbox("Filter by Zone", zones)
            
            time_period_options = get_time_period_options()
            filter_type = st.selectbox("Filter by Time Period", ['All'] + list(time_period_options.keys()))
            
            if filter_type != 'All':
                filter_value = st.selectbox(f"Select {filter_type}", time_period_options[filter_type])

            # Apply filters
            if filter_username != 'All':
                report_df = report_df[report_df['Username'] == filter_username]
            if filter_zone != 'All':
                report_df = report_df[report_df['Zone'] == filter_zone]

            if filter_type != 'All':
                if filter_type == 'Annual':
                    report_df = report_df[report_df['Year'] == int(filter_value)]
                elif filter_type == 'Quarterly':
                    year, quarter = filter_value.split()
                    quarter_month_map = {'Q1': [1, 2, 3], 'Q2': [4, 5, 6], 'Q3': [7, 8, 9], 'Q4': [10, 11, 12]}
                    report_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'].isin(quarter_month_map[quarter]))
                    ]
                elif filter_type == 'Half-Year':
                    year, half = filter_value.split()
                    half_year_month_map = {'H1': [1, 2, 3, 4, 5, 6], 'H2': [7, 8, 9, 10, 11, 12]}
                    report_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'].isin(half_year_month_map[half]))
                    ]
                elif filter_type == 'Monthly':
                    year, month = filter_value.split()
                    month_num = datetime.strptime(month, '%B').month
                    report_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'] == month_num)
                    ]

            st.subheader("Filtered Reports")
            st.dataframe(report_df[["ID", "Username", "Zone", "Year", "Month", "Submission Date"]])

            # Add download button
            if not report_df.empty:
                excel_data = download_excel(report_df, "reports.xlsx")
                st.download_button(
                    label="Download Reports as Excel",
                    data=excel_data,
                    file_name="reports.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # View detailed report
            view_report_details(report_df)

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
                new_username = st.text_input("Username", value=report_to_edit['Username'])
                new_zone = st.text_input("Zone", value=report_to_edit['Zone'])
                new_year = st.number_input("Year", min_value=2020, max_value=datetime.now().year, value=int(report_to_edit['Year']))
                new_month = st.selectbox("Month", range(1, 13), index=int(report_to_edit['Month'])-1, format_func=lambda x: datetime(2000, x, 1).strftime('%B'))
                
                report_data = json.loads(report_to_edit['Report Data'])
                new_report_data = {}
                for key, value in report_data.items():
                    new_report_data[key] = st.number_input(key, value=int(value))

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
    st.write(f"Welcome, {st.session_state.username}!")
    st.subheader("User Dashboard")

    user_details = get_user_details(st.session_state.username)
    user_group, sub_group, region, zone = user_details

    # Create tabs for different sections
    if user_group == "GPD" and sub_group == "Reporting/Admin":
        tab1, tab2, tab3, tab4 = st.tabs(["Dashboard", "View All RZM Reports", "View Your Submitted Reports", "Submit New Report"])
    else:
        tab1, tab2, tab3 = st.tabs(["Dashboard", "View Your Submitted Reports", "Submit New Report"])

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
            all_rzm_reports = fetch_reports()  # Fetch all reports
            if all_rzm_reports:
                report_df = pd.DataFrame(all_rzm_reports, columns=["ID", "Username", "Zone", "Year", "Month", "Report Data", "Submission Date"])
                
                # Filter options
                st.subheader("Filter Reports")
                usernames = ['All'] + sorted(report_df['Username'].unique().tolist())
                filter_username = st.selectbox("Filter by Username", usernames)
                
                zones = ['All'] + sorted(report_df['Zone'].unique().tolist())
                filter_zone = st.selectbox("Filter by Zone", zones)
                
                time_period_options = get_time_period_options()
                filter_type = st.selectbox("Filter by Time Period", ['All'] + list(time_period_options.keys()))
                
                if filter_type != 'All':
                    filter_value = st.selectbox(f"Select {filter_type}", time_period_options[filter_type])

                # Apply filters
                if filter_username != 'All':
                    report_df = report_df[report_df['Username'] == filter_username]
                if filter_zone != 'All':
                    report_df = report_df[report_df['Zone'] == filter_zone]

                if filter_type != 'All':
                    if filter_type == 'Annual':
                        report_df = report_df[report_df['Year'] == int(filter_value)]
                    elif filter_type == 'Quarterly':
                        year, quarter = filter_value.split()
                        quarter_month_map = {'Q1': [1, 2, 3], 'Q2': [4, 5, 6], 'Q3': [7, 8, 9], 'Q4': [10, 11, 12]}
                        report_df = report_df[
                            (report_df['Year'] == int(year)) & 
                            (report_df['Month'].isin(quarter_month_map[quarter]))
                        ]
                    elif filter_type == 'Half-Year':
                        year, half = filter_value.split()
                        half_year_month_map = {'H1': [1, 2, 3, 4, 5, 6], 'H2': [7, 8, 9, 10, 11, 12]}
                        report_df = report_df[
                            (report_df['Year'] == int(year)) & 
                            (report_df['Month'].isin(half_year_month_map[half]))
                        ]
                    elif filter_type == 'Monthly':
                        year, month = filter_value.split()
                        month_num = datetime.strptime(month, '%B').month
                        report_df = report_df[
                            (report_df['Year'] == int(year)) & 
                            (report_df['Month'] == month_num)
                        ]

                st.subheader("Filtered Reports")
                st.dataframe(report_df[["ID", "Username", "Zone", "Year", "Month", "Submission Date"]])

                # Add download button
                if not report_df.empty:
                    excel_data = download_excel(report_df, "rzm_reports.xlsx")
                    st.download_button(
                        label="Download RZM Reports as Excel",
                        data=excel_data,
                        file_name="rzm_reports.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                # View detailed report
                view_report_details(report_df)

            else:
                st.write("No reports submitted yet.")

        with tab3:
            st.subheader("View Your Submitted Reports")
            user_reports = fetch_reports(st.session_state.username)
            if user_reports:
                report_df = pd.DataFrame(user_reports, columns=["ID", "Username", "Zone", "Year", "Month", "Report Data", "Submission Date"])
                st.dataframe(report_df[["ID", "Zone", "Year", "Month", "Submission Date"]])

                # Filter reports
                st.subheader("Filter Your Reports")
                time_period_options = get_time_period_options()
                filter_type = st.selectbox("Filter by Time Period", ['Annual', 'Quarterly', 'Half-Year', 'Monthly'])
                filter_value = st.selectbox(f"Select {filter_type}", time_period_options[filter_type])

                # Apply filters
                if filter_type == 'Annual':
                    filtered_df = report_df[report_df['Year'] == int(filter_value)]
                elif filter_type == 'Quarterly':
                    year, quarter = filter_value.split()
                    quarter_month_map = {'Q1': [1, 2, 3], 'Q2': [4, 5, 6], 'Q3': [7, 8, 9], 'Q4': [10, 11, 12]}
                    filtered_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'].isin(quarter_month_map[quarter]))
                    ]
                elif filter_type == 'Half-Year':
                    year, half = filter_value.split()
                    half_year_month_map = {'H1': [1, 2, 3, 4, 5, 6], 'H2': [7, 8, 9, 10, 11, 12]}
                    filtered_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'].isin(half_year_month_map[half]))
                    ]
                elif filter_type == 'Monthly':
                    year, month = filter_value.split()
                    month_num = datetime.strptime(month, '%B').month
                    filtered_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'] == month_num)
                    ]

                st.subheader("Filtered Reports")
                st.dataframe(filtered_df[["ID", "Zone", "Year", "Month", "Submission Date"]])

                # View detailed report
                view_report_details(filtered_df)

            else:
                st.write("You haven't submitted any reports yet.")

        with tab4:
            st.subheader("Submit New Report")
            if user_group == "GPD":
                st.write("Reporting functionality for GPD users is coming soon!")
            elif user_group == "RZM":
                st.write(f"RZM: {st.session_state.username}")
                st.write(f"Zone: {zone}")

                year = st.selectbox("Year", range(datetime.now().year, 2020, -1))
                month = st.selectbox("Month", range(1, 13), format_func=lambda x: datetime(2000, x, 1).strftime('%B'))

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
                    save_report(st.session_state.username, zone, year, month, report_data)
                    st.success("Report submitted successfully!")
                    st.rerun()

    else:
        with tab2:
            st.subheader("View Your Submitted Reports")
            user_reports = fetch_reports(st.session_state.username)
            if user_reports:
                report_df = pd.DataFrame(user_reports, columns=["ID", "Username", "Zone", "Year", "Month", "Report Data", "Submission Date"])
                st.dataframe(report_df[["ID", "Zone", "Year", "Month", "Submission Date"]])

                # Filter reports
                st.subheader("Filter Your Reports")
                time_period_options = get_time_period_options()
                filter_type = st.selectbox("Filter by Time Period", ['Annual', 'Quarterly', 'Half-Year', 'Monthly'])
                filter_value = st.selectbox(f"Select {filter_type}", time_period_options[filter_type])

                # Apply filters
                if filter_type == 'Annual':
                    filtered_df = report_df[report_df['Year'] == int(filter_value)]
                elif filter_type == 'Quarterly':
                    year, quarter = filter_value.split()
                    quarter_month_map = {'Q1': [1, 2, 3], 'Q2': [4, 5, 6], 'Q3': [7, 8, 9], 'Q4': [10, 11, 12]}
                    filtered_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'].isin(quarter_month_map[quarter]))
                    ]
                elif filter_type == 'Half-Year':
                    year, half = filter_value.split()
                    half_year_month_map = {'H1': [1, 2, 3, 4, 5, 6], 'H2': [7, 8, 9, 10, 11, 12]}
                    filtered_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'].isin(half_year_month_map[half]))
                    ]
                elif filter_type == 'Monthly':
                    year, month = filter_value.split()
                    month_num = datetime.strptime(month, '%B').month
                    filtered_df = report_df[
                        (report_df['Year'] == int(year)) & 
                        (report_df['Month'] == month_num)
                    ]

                st.subheader("Filtered Reports")
                st.dataframe(filtered_df[["ID", "Zone", "Year", "Month", "Submission Date"]])

                # View detailed report
                view_report_details(filtered_df)

            else:
                st.write("You haven't submitted any reports yet.")

        with tab3:
            st.subheader("Submit New Report")
            if user_group == "GPD":
                st.write("Reporting functionality for GPD users is coming soon!")
            elif user_group == "RZM":
                st.write(f"RZM: {st.session_state.username}")
                st.write(f"Zone: {zone}")

                year = st.selectbox("Year", range(datetime.now().year, 2020, -1))
                month = st.selectbox("Month", range(1, 13), format_func=lambda x: datetime(2000, x, 1).strftime('%B'))

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
                    save_report(st.session_state.username, zone, year, month, report_data)
                    st.success("Report submitted successfully!")
                    st.rerun()

def download_excel(df, filename):
    output = io.BytesIO()
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Report Data"

    # Add title
    sheet['A1'] = "GPD Admin Portal - Report Data"
    sheet['A1'].font = Font(size=16, bold=True)
    sheet.merge_cells('A1:E1')

    # Add data headers
    headers = df.columns.tolist()
    for col, header in enumerate(headers, start=1):
        cell = sheet.cell(row=3, column=col, value=header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="DDDDDD", end_color="DDDDDD", fill_type="solid")

    # Add data
    for row, data in df.iterrows():
        for col, value in enumerate(data, start=1):
            sheet.cell(row=row+4, column=col, value=value)

    # Adjust column widths
    for col in range(1, sheet.max_column + 1):
        max_length = 0
        column_letter = get_column_letter(col)
        for row in range(1, sheet.max_row + 1):
            cell = sheet.cell(row=row, column=col)
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(cell.value)
            except:
                pass
        adjusted_width = (max_length + 2)
        sheet.column_dimensions[column_letter].width = adjusted_width

    workbook.save(output)
    output.seek(0)
    
    return output.getvalue()

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
                    st.write(report['Year'])
                    st.write(month_name[report['Month']])
                
                st.write("---")
                st.write("Report Data:")
                
                # Create a DataFrame for the report data
                report_data_df = pd.DataFrame(list(report_data.items()), columns=['Metric', 'Value'])
                st.table(report_data_df)
    else:
        st.write("No reports available for the selected filters.")

if __name__ == "__main__":
    init_db()
    main()