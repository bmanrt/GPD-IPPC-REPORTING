import streamlit as st
import sqlite3
import json
from datetime import datetime
import pandas as pd
import io

# Database initialization
def init_church_db():
    """Initialize the church partners database with proper schema"""
    try:
        conn = sqlite3.connect('church_partners.db')
        c = conn.cursor()
        
        # Create the table if it doesn't exist
        c.execute('''CREATE TABLE IF NOT EXISTS church_partner_records
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      record_type TEXT NOT NULL,
                      record_data TEXT NOT NULL,
                      submission_date DATETIME NOT NULL)''')
        
        conn.commit()
        return True, "Database initialized successfully!"
    except Exception as e:
        return False, f"Error initializing database: {e}"
    finally:
        conn.close()

# Add this function to run migrations
def run_church_db_migration():
    """Run database migrations for church partners"""
    try:
        # Read the migration SQL
        with open('migrations/init_church_db.sql', 'r') as f:
            migration_sql = f.read()
        
        # Connect to database and execute migration
        conn = sqlite3.connect('church_partners.db')
        c = conn.cursor()
        
        # Split and execute each statement
        for statement in migration_sql.split(';'):
            if statement.strip():
                c.execute(statement)
        
        conn.commit()
        conn.close()
        return True, "Migration completed successfully!"
    except Exception as e:
        return False, f"Migration failed: {e}"

# Update the main initialization code
def initialize_database():
    """Complete database initialization and migration"""
    success, message = init_church_db()
    if not success:
        st.error(message)
        return False
        
    success, message = run_church_db_migration()
    if not success:
        st.error(message)
        return False
    
    return True

# Function to save church partner record
def save_church_partner_record(record_type, record_data):
    """Save church partner record with currency conversion"""
    try:
        # Calculate original amount and converted amount (ESPEES)
        currency = record_data.get('currency', 'ESPEES')
        original_amount = float(record_data.get('total_amount', 0))
        
        # Convert to ESPEES and store both amounts
        grand_total = convert_to_espees(original_amount, currency)
        record_data['original_amount'] = original_amount
        record_data['grand_total'] = grand_total
        
        conn = sqlite3.connect('church_partners.db')
        c = conn.cursor()
        c.execute("""INSERT INTO church_partner_records 
                     (record_type, record_data, submission_date)
                     VALUES (?, ?, ?)""",
                  (record_type, json.dumps(record_data), datetime.now()))
        conn.commit()
        conn.close()
        return True, "Record saved successfully!"
    except Exception as e:
        return False, f"Error saving record: {e}"

# Function to fetch all church partner records
def fetch_church_partner_records():
    """Fetch church records with currency conversion support"""
    try:
        conn = sqlite3.connect('church_partners.db')
        c = conn.cursor()
        c.execute("SELECT * FROM church_partner_records")
        records = c.fetchall()
        conn.close()

        # Process records to include converted amounts
        processed_records = []
        for record in records:
            record_id, record_type, record_data_str, submission_date = record
            record_data = json.loads(record_data_str)
            
            # Ensure currency conversion data exists
            if 'currency' in record_data and 'total_amount' in record_data:
                if 'grand_total' not in record_data:
                    record_data['original_amount'] = float(record_data['total_amount'])
                    record_data['grand_total'] = convert_to_espees(
                        record_data['total_amount'],
                        record_data['currency']
                    )
                    # Update record with new data
                    conn = sqlite3.connect('church_partners.db')
                    c = conn.cursor()
                    c.execute("""UPDATE church_partner_records 
                                SET record_data = ? 
                                WHERE id = ?""",
                             (json.dumps(record_data), record_id))
                    conn.commit()
                    conn.close()
            
            processed_records.append((
                record_id,
                record_type,
                record_data,
                submission_date
            ))
        
        return processed_records
    except Exception as e:
        st.error(f"Error fetching church records: {e}")
        return []

# Add this list of currencies
CURRENCIES = ["ESPEES", "USD", "NGN", "EUR"]

# Update the CONVERSION_RATES dictionary to match the global system
CONVERSION_RATES = {
    "NGN": 1750.0,  # 1 USD = 1750 NGN
    "USD": 1.0,     # Base currency
    "EUR": 0.92,    # 1 USD = 0.92 EUR
    "ESPEES": 1.0   # ESPEES is equivalent to USD
}

# Add these at the top of the file with other global variables
DISPLAY_CURRENCY = 'ESPEES'

def set_display_currency(currency):
    """Set the currency to use for displaying amounts"""
    global DISPLAY_CURRENCY
    DISPLAY_CURRENCY = currency

# Update the convert_to_espees function to format decimals better
def convert_to_espees(amount, from_currency):
    """Convert amount from given currency to ESPEES"""
    if amount is None or amount == 0:
        return 0.0
        
    try:
        amount = float(amount)
        if from_currency == "ESPEES":
            return round(amount, 2)
            
        rate = CONVERSION_RATES.get(from_currency)
        if not rate:
            return round(amount, 2)
            
        # All conversions now use the same formula for consistency
        converted = amount / rate if from_currency != "USD" else amount
        return round(converted, 2)
            
    except (TypeError, ValueError, ZeroDivisionError) as e:
        st.error(f"Conversion error: {e}")
        return 0.0

# Add these handler functions after the convert_to_espees function

def handle_ror_outreaches_submit(form_data):
    """Handle ROR outreaches form submission with currency conversion"""
    try:
        currency = form_data['currency']
        total_amount = float(form_data['total_amount'])
        
        # Convert to ESPEES
        grand_total = convert_to_espees(total_amount, currency)
        form_data['original_amount'] = total_amount
        form_data['grand_total'] = grand_total
        
        success, message = save_church_partner_record("ROR", form_data)
        return success, message
    except Exception as e:
        return False, f"Error processing submission: {e}"

def handle_church_submit(form_data, category):
    """Handle church form submission with currency conversion"""
    try:
        currency = form_data['currency']
        total_amount = float(form_data['total_amount'])
        
        # Convert to ESPEES
        grand_total = convert_to_espees(total_amount, currency)
        form_data['original_amount'] = total_amount
        form_data['grand_total'] = grand_total
        
        record_type = "Church" if category == "C" else f"Category {category}"
        success, message = save_church_partner_record(record_type, form_data)
        return success, message
    except Exception as e:
        return False, f"Error processing submission: {e}"

def handle_cell_submit(form_data):
    """Handle cell form submission with currency conversion"""
    try:
        currency = form_data['currency']
        total_amount = float(form_data.get('total_amount_given', 0))
        total_amount_received = float(form_data.get('total_amount_received', 0))
        
        # Convert both amounts to ESPEES
        grand_total = convert_to_espees(total_amount, currency)
        received_total = convert_to_espees(total_amount_received, currency)
        
        form_data['original_amount'] = total_amount
        form_data['grand_total'] = grand_total
        form_data['original_amount_received'] = total_amount_received
        form_data['received_total_espees'] = received_total
        
        success, message = save_church_partner_record("Cell", form_data)
        return success, message
    except Exception as e:
        return False, f"Error processing submission: {e}"

# UI for ROR Outreaches Sub-campaigns
def ror_outreaches_ui():
    st.subheader("ROR Outreaches Sub-campaigns")
    
    with st.form("ror_outreaches_form"):
        # Basic Information
        st.write("### Basic Information")
        zone_name = st.text_input(
            "NAME OF ZONE",
            value=st.session_state.get('zone', ''),
            disabled=True
        )
        group_name = st.text_input("NAME OF GROUP")
        
        # Outreach Programs
        st.write("### OUTREACH PROGRAMS")
        reachout_world_programs = st.number_input("REACHOUT/WORLD PROGRAMS", min_value=0)
        rhapathon = st.number_input("RHAPATHON WITH PASTOR CHRIS", min_value=0)
        reachout_world_nations = st.number_input("REACHOUT WORLD NATIONS (DURING YOUR NATIONAL HOLIDAYS)", min_value=0)
        say_yes_to_kids = st.number_input("SAY YES TO KIDS", min_value=0)
        teevolution = st.number_input("TEEVOLUTION", min_value=0)
        youth_aglow = st.number_input("YOUTH AGLOW", min_value=0)
        no_one_left_behind = st.number_input("NO ONE LEFT BEHIND", min_value=0)
        penetrating_truth = st.number_input("PENETRATING WITH TRUTH", min_value=0)
        penetrating_languages = st.number_input("PENETRATING WITH LANGUAGES", min_value=0)
        adopt_a_street = st.number_input("ADOPT A STREET", min_value=0)
        
        # Totals
        total_outreaches = (
            reachout_world_programs + rhapathon + reachout_world_nations +
            say_yes_to_kids + teevolution + youth_aglow + no_one_left_behind +
            penetrating_truth + penetrating_languages + adopt_a_street
        )
        st.write(f"TOTAL NO OF OUTREACHES THAT WAS CARRIED OUT: {total_outreaches}")
        
        currency = st.selectbox("Currency", CURRENCIES, key="ror_currency")
        total_amount = st.number_input(f"Total Amount ({currency})", min_value=0.0)

        if st.form_submit_button("Submit ROR Outreaches Record"):
            record_data = {
                "zone_name": zone_name,
                "group_name": group_name,
                "reachout_world_programs": reachout_world_programs,
                "rhapathon": rhapathon,
                "reachout_world_nations": reachout_world_nations,
                "say_yes_to_kids": say_yes_to_kids,
                "teevolution": teevolution,
                "youth_aglow": youth_aglow,
                "no_one_left_behind": no_one_left_behind,
                "penetrating_truth": penetrating_truth,
                "penetrating_languages": penetrating_languages,
                "adopt_a_street": adopt_a_street,
                "total_outreaches": total_outreaches,
                "currency": currency,
                "total_amount": total_amount,
            }
            success, message = handle_ror_outreaches_submit(record_data)
            if success:
                st.success(message)
            else:
                st.error(message)

# UI for Churches (formerly Category A/B/C)
def group_churches_ui(category):
    title = "Churches" if category == "C" else f"Category {category} Group Churches"
    st.subheader(title)
    
    with st.form(f"category_{category}_form"):
        # Basic Information
        st.write("### Basic Information")
        zone_name = st.text_input(
            "NAME OF ZONE", 
            value=st.session_state.get('zone', ''),
            disabled=True
        )
        group_name = st.text_input("NAME OF GROUP")
        
        # Church Information
        st.write("### Church Information")
        church_name = st.text_input("NAME OF CHURCH")
        church_pastor = st.text_input("NAME OF CHURCH PASTOR")
        
        # Contact Information
        st.write("### Contact Information")
        kingschat_phone = st.text_input("KINGSCHAT PHONE NUMBER")
        email = st.text_input("EMAIL ADDRESS")
        
        # Sponsorship Information
        st.write("### Sponsorship Information")
        total_quantity = st.number_input("TOTAL QUANTITY SPONSORED(NOT INCOME)", min_value=0)
        currency = st.selectbox("Currency", CURRENCIES, key=f"category_{category}_currency")
        total_amount = st.number_input("Total Amount Received for Rhapsody Partnership by the Group Church", min_value=0.0)
        
        # Breakdown of Sponsorship
        st.write("### BREAKDOWN OF SPONSORSHIP INTO FORMATS")
        kiddies_products = st.number_input("KIDDIES PRODUCTS", min_value=0)
        teevo = st.number_input("TEEVO", min_value=0)
        braille = st.number_input("BRAILLE(NOLB)", min_value=0)
        languages = st.number_input("LANGUAGES", min_value=0)
        youth_aglow = st.number_input("YOUTH AGLOW", min_value=0)

        if st.form_submit_button(f"Submit {'Church' if category == 'C' else f'Category {category}'} Record"):
            record_data = {
                "zone_name": zone_name,
                "group_name": group_name,
                "church_name": church_name,
                "church_pastor": church_pastor,
                "kingschat_phone": kingschat_phone,
                "email": email,
                "church_level_category": "Church" if category == "C" else f"Category {category}",  # Still store it in the data but don't display
                "total_quantity": total_quantity,
                "currency": currency,
                "total_amount": total_amount,
                # Sponsorship breakdown
                "kiddies_products": kiddies_products,
                "teevo": teevo,
                "braille_nolb": braille,
                "languages": languages,
                "youth_aglow": youth_aglow,
            }
            success, message = handle_church_submit(record_data, category)
            if success:
                st.success(message)
            else:
                st.error(message)

# UI for Cell Records
def cell_records_ui():
    st.subheader("Cell Records")
    
    with st.form("cell_records_form"):
        # Basic Information
        st.write("### Basic Information")
        zone_name = st.text_input(
            "NAME OF ZONE",
            value=st.session_state.get('zone', ''),
            disabled=True
        )
        cell_name = st.text_input("NAME OF CELL")
        cell_leader = st.text_input("NAME OF CELL LEADER")
        
        # Contact Information
        st.write("### Contact Information")
        kingschat_phone = st.text_input("KINGSCHAT PHONE NUMBER")
        email = st.text_input("EMAIL ADDRESS")
        
        # Church Information
        st.write("### Church Information")
        church = st.text_input("CHURCH")
        group = st.text_input("GROUP")
        
        # Sponsorship Information
        st.write("### Sponsorship Information")
        total_quantity = st.number_input("TOTAL QUANTITY SPONSORSHIP(NOT INCOME)", min_value=0)
        currency = st.selectbox("Currency", CURRENCIES, key="cell_currency")
        total_amount_received = st.number_input("Total Amount Received for Rhapsody Partnership by the Group Church", min_value=0.0)
        total_amount_given = st.number_input("TOTAL AMOUNT GIVEN", min_value=0.0)
        
        # Breakdown of Sponsorship
        st.write("### BREAKDOWN OF SPONSORSHIP INTO FORMATS")
        kiddies_products = st.number_input("KIDDIES PRODUCTS", min_value=0)
        teevo = st.number_input("TEEVO", min_value=0)
        braille = st.number_input("BRAILLE", min_value=0)
        languages = st.number_input("LANGUAGE", min_value=0)
        youth_aglow = st.number_input("YOUTH AGLOW", min_value=0)

        if st.form_submit_button("Submit Cell Record"):
            record_data = {
                "zone_name": zone_name,
                "cell_name": cell_name,
                "cell_leader": cell_leader,
                "kingschat_phone": kingschat_phone,
                "email": email,
                "church": church,
                "group": group,
                "total_quantity": total_quantity,
                "currency": currency,
                "total_amount_received": total_amount_received,
                "total_amount_given": total_amount_given,
                # Sponsorship breakdown
                "kiddies_products": kiddies_products,
                "teevo": teevo,
                "braille": braille,
                "languages": languages,
                "youth_aglow": youth_aglow,
            }
            success, message = handle_cell_submit(record_data)
            if success:
                st.success(message)
            else:
                st.error(message)

# Main function for church records UI
def church_records_ui():
    st.title("Church Records")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "ROR Outreaches",
        "Category A Churches",
        "Category B Churches",
        "Churches",
        "Cell Records"  # Removed View All Records and Export Data tabs
    ])

    with tab1:
        ror_outreaches_ui()
    
    with tab2:
        group_churches_ui("A")
    
    with tab3:
        group_churches_ui("B")
    
    with tab4:
        group_churches_ui("C")
    
    with tab5:
        cell_records_ui()

# Add this function to load saved conversion rates
def load_saved_rates():
    try:
        with open('conversion_rates.json', 'r') as f:
            saved_rates = json.load(f)
            CONVERSION_RATES.update(saved_rates)
    except FileNotFoundError:
        pass  # Use default rates if file doesn't exist
    except Exception as e:
        st.error(f"Error loading conversion rates: {e}")

# Initialize the database when the script is run
init_church_db()

# At the top of the file, after imports
def ensure_database_ready():
    """Ensure database is initialized and migrated"""
    if check_db_needs_migration():
        success, message = run_church_db_migration()
        if not success:
            st.error(f"Database migration failed: {message}")
            return False
    return True

# Update the main execution block
if __name__ == "__main__":
    if ensure_database_ready():
        load_saved_rates()
        church_records_ui()
    else:
        st.error("Database initialization failed. Please contact support.")

def check_db_needs_migration():
    """Check if the database needs migration"""
    try:
        conn = sqlite3.connect('church_partners.db')
        c = conn.cursor()
        
        # Try to get table info
        c.execute("PRAGMA table_info(church_partner_records)")
        columns = c.fetchall()
        
        # Check if we have all required columns
        required_columns = {'id', 'record_type', 'record_data', 'submission_date'}
        existing_columns = {col[1] for col in columns}
        
        return not required_columns.issubset(existing_columns)
    except:
        return True
    finally:
        conn.close()
