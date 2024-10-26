from church_records import CURRENCIES, CONVERSION_RATES, convert_to_espees
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import io
import plotly.express as px
import plotly.graph_objects as go
import json

# Add these constants at the top of the file
TITLE_OPTIONS = ["Bro", "Sis", "Dcn", "Dcns", "Pastor", "Mr", "Mrs"]
CHILD_TITLE_OPTIONS = ["Bro", "Sis"]

# Initialize the partner records database
def init_partner_db():
    """Initialize the partner records database"""
    conn = sqlite3.connect('partner_records.db')
    c = conn.cursor()
    
    # Drop existing tables if they exist
    c.execute("DROP TABLE IF EXISTS adult_partners")
    c.execute("DROP TABLE IF EXISTS children_partners")
    c.execute("DROP TABLE IF EXISTS teenager_partners")
    c.execute("DROP TABLE IF EXISTS external_partners")
    
    # Create tables with simplified schema
    tables = ['adult_partners', 'children_partners', 'teenager_partners', 'external_partners']
    for table in tables:
        c.execute(f'''CREATE TABLE IF NOT EXISTS {table}
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      record_data TEXT NOT NULL,
                      submission_date DATETIME NOT NULL)''')
    
    conn.commit()
    conn.close()

# Add these functions at the top of the file
def save_partner_record(record_type, record_data):
    """Save partner record with currency conversion"""
    try:
        # Calculate original amount and converted amount (ESPEES)
        currency = record_data.get('currency', 'ESPEES')
        
        # Calculate total amount based on record type
        if record_type == "External Partner":
            original_amount = sum([
                float(record_data.get('rhapsody_subscriptions_dubais', 0)),
                float(record_data.get('sponsorship_retail_center', 0)),
                float(record_data.get('translators_network_international', 0)),
                float(record_data.get('rhapsody_influencers_network', 0)),
                float(record_data.get('rim', 0))
            ])
        else:
            original_amount = sum([
                float(record_data.get('total_wonder_challenge', 0)),
                float(record_data.get('total_rhapsody_languages', 0)),
                float(record_data.get('total_kiddies_products', 0)),
                float(record_data.get('total_teevo', 0)),
                float(record_data.get('total_braille_nolb', 0)),
                float(record_data.get('total_youth_aglow', 0)),
                float(record_data.get('total_local_distribution', 0)),
                float(record_data.get('total_subscriptions_dubais', 0))
            ])

        # Convert to ESPEES and store both amounts
        grand_total = convert_to_espees(original_amount, currency)
        
        # Store both original and converted amounts
        record_data.update({
            'original_amount': original_amount,
            'grand_total': grand_total,
            'currency': currency  # Ensure currency is stored
        })
        
        # Convert datetime objects to strings
        submission_date = datetime.now()
        processed_data = {}
        for key, value in record_data.items():
            if isinstance(value, datetime):
                processed_data[key] = value.isoformat()
            elif isinstance(value, pd._libs.tslibs.timestamps.Timestamp):
                processed_data[key] = value.isoformat()
            else:
                processed_data[key] = value

        # Store as JSON string
        record_json = json.dumps(processed_data)
        
        conn = sqlite3.connect('partner_records.db')
        c = conn.cursor()
        
        # Map record type to table name
        table_map = {
            'Adult Partner': 'adult_partners',
            'Child Partner': 'children_partners',
            'Teenager Partner': 'teenager_partners',
            'External Partner': 'external_partners'
        }
        
        table_name = table_map.get(record_type)
        if not table_name:
            raise ValueError(f"Invalid record type: {record_type}")

        # Insert record
        c.execute(f"""INSERT INTO {table_name} 
                     (record_data, submission_date)
                     VALUES (?, ?)""",
                  (record_json, submission_date))
        
        conn.commit()
        conn.close()
        
        return True, "Record saved successfully!"
    except Exception as e:
        st.error(f"Error saving record: {str(e)}")
        return False, f"Error saving record: {str(e)}"

# Function to add a new partner record
def add_partner_record(partner_data, is_child=False, is_teenager=False):
    """Add a new partner record"""
    try:
        # Determine record type
        if is_teenager:
            record_type = "Teenager Partner"
        elif is_child:
            record_type = "Child Partner"
        else:
            record_type = "Adult Partner"
            
        # Save record
        success, message = save_partner_record(record_type, partner_data)
        return success, message
    except Exception as e:
        st.error(f"Error adding partner record: {str(e)}")
        return False, f"Error adding partner record: {str(e)}"

# Function to fetch all partner records
def fetch_partner_records(partner_type='all'):
    """Fetch partner records with proper currency conversion"""
    try:
        conn = sqlite3.connect('partner_records.db')
        
        # Initialize empty list to store all records
        all_records = []
        
        # Define table mappings
        tables = {
            'adult': ('adult_partners', 'Adult Partner'),
            'children': ('children_partners', 'Child Partner'),
            'teenager': ('teenager_partners', 'Teenager Partner'),
            'external': ('external_partners', 'External Partner')
        }
        
        # Fetch records based on partner type
        if partner_type != 'all':
            if partner_type in tables:
                table_name, record_type = tables[partner_type]
                query = f"SELECT id, record_data, submission_date FROM {table_name}"
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    df['record_type'] = record_type
                    all_records.append(df)
        else:
            # Fetch from all tables
            for table_name, record_type in tables.values():
                try:
                    query = f"SELECT id, record_data, submission_date FROM {table_name}"
                    df = pd.read_sql_query(query, conn)
                    if not df.empty:
                        df['record_type'] = record_type
                        all_records.append(df)
                except:
                    continue
        
        conn.close()
        
        # Combine all records
        if not all_records:
            return pd.DataFrame()
            
        combined_df = pd.concat(all_records, ignore_index=True)
        
        # Parse JSON data
        def parse_record_data(record_data):
            if isinstance(record_data, str):
                return json.loads(record_data)
            return record_data
            
        # Extract fields from JSON
        combined_df['record_data'] = combined_df['record_data'].apply(parse_record_data)
        
        # Extract common fields
        for field in ['title', 'first_name', 'surname', 'church', 'group_name', 
                     'kingschat_phone', 'email', 'zone', 'currency', 
                     'original_amount', 'grand_total']:
            combined_df[field] = combined_df['record_data'].apply(lambda x: x.get(field, ''))
        
        # Extract numeric fields with proper type conversion
        numeric_fields = [
            'total_wonder_challenge', 'total_rhapsody_languages',
            'total_kiddies_products', 'total_teevo', 'total_braille_nolb',
            'total_youth_aglow', 'total_local_distribution',
            'total_subscriptions_dubais'
        ]
        
        for field in numeric_fields:
            combined_df[field] = combined_df['record_data'].apply(
                lambda x: float(x.get(field, 0))
            )
        
        # Ensure numeric types
        for col in numeric_fields + ['original_amount', 'grand_total']:
            if col in combined_df.columns:
                combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce').fillna(0)
        
        return combined_df
        
    except Exception as e:
        st.error(f"Error fetching partner records: {e}")
        return pd.DataFrame()

# Make sure this function is defined and exported
def partner_records_ui():
    st.subheader("Partner Records Management")
    
    # Create tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs(["Adult Partner", "Child Partner", "Teenager Partner", "External Partner"])
    
    with tab1:
        st.subheader("Adult Partner Form")
        with st.form("adult_partner_form"):
            # Basic Info
            title = st.selectbox("Title", TITLE_OPTIONS, key="adult_title")
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("First Name")
            with col2:
                surname = st.text_input("Surname")
            
            # Contact Info
            col1, col2 = st.columns(2)
            with col1:
                kingschat_phone = st.text_input("KingsChat Phone Number")
            with col2:
                email = st.text_input("Email Address")
            
            # Church Info
            col1, col2 = st.columns(2)
            with col1:
                church = st.text_input("Church")
            with col2:
                group_name = st.text_input("Group")
            
            # Financial Info
            currency = st.selectbox("Currency", CURRENCIES)
            
            col1, col2 = st.columns(2)
            with col1:
                wonder_challenge = st.number_input("Total Amount for Wonder Challenge", min_value=0.0)
                kiddies_products = st.number_input("Total Amount for Kiddies Products", min_value=0.0)
                braille_nolb = st.number_input("Total Amount for Braille(NOLB)", min_value=0.0)
                local_distribution = st.number_input("Total for Local Distribution", min_value=0.0)
            with col2:
                rhapsody_languages = st.number_input("Total Amount for Rhapsody Languages", min_value=0.0)
                teevo = st.number_input("Total Amount for Teevo", min_value=0.0)
                youth_aglow = st.number_input("Total Amount for Youth Aglow", min_value=0.0)
                subscriptions_dubais = st.number_input("Total for Subscriptions/Dubais", min_value=0.0)
            
            submit = st.form_submit_button("Submit Adult Partner Record")
            
            if submit:
                partner_data = {
                    "title": title,
                    "first_name": first_name,
                    "surname": surname,
                    "church": church,
                    "group_name": group_name,
                    "kingschat_phone": kingschat_phone,
                    "email": email,
                    "currency": currency,
                    "total_wonder_challenge": wonder_challenge,
                    "total_rhapsody_languages": rhapsody_languages,
                    "total_kiddies_products": kiddies_products,
                    "total_teevo": teevo,
                    "total_braille_nolb": braille_nolb,
                    "total_youth_aglow": youth_aglow,
                    "total_local_distribution": local_distribution,
                    "total_subscriptions_dubais": subscriptions_dubais
                }
                
                success, message = add_partner_record(partner_data)
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    with tab2:
        st.subheader("Child Partner Form")
        with st.form("child_partner_form"):
            # Basic Info
            title = st.selectbox("Title", CHILD_TITLE_OPTIONS, key="child_title")
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("First Name", key="child_first_name")
            with col2:
                surname = st.text_input("Surname", key="child_surname")
            
            # Additional Child Info
            col1, col2 = st.columns(2)
            with col1:
                age = st.number_input("Age", min_value=1, max_value=12)
            with col2:
                birthday = st.date_input("Birthday")
            
            # Contact Info
            col1, col2 = st.columns(2)
            with col1:
                kingschat_phone = st.text_input("KingsChat Phone Number", key="child_phone")
            with col2:
                email = st.text_input("Email Address", key="child_email")
            
            # Church Info
            col1, col2 = st.columns(2)
            with col1:
                church = st.text_input("Church", key="child_church")
            with col2:
                group_name = st.text_input("Group", key="child_group")
            
            # Financial Info
            currency = st.selectbox("Currency", CURRENCIES, key="child_currency")
            
            col1, col2 = st.columns(2)
            with col1:
                wonder_challenge = st.number_input("Total Amount for Wonder Challenge", min_value=0.0, key="child_wonder")
                kiddies_products = st.number_input("Total Amount for Kiddies Products", min_value=0.0, key="child_kiddies")
                braille_nolb = st.number_input("Total Amount for Braille(NOLB)", min_value=0.0, key="child_braille")
                local_distribution = st.number_input("Total for Local Distribution", min_value=0.0, key="child_local")
            with col2:
                rhapsody_languages = st.number_input("Total Amount for Rhapsody Languages", min_value=0.0, key="child_rhapsody")
                teevo = st.number_input("Total Amount for Teevo", min_value=0.0, key="child_teevo")
                youth_aglow = st.number_input("Total Amount for Youth Aglow", min_value=0.0, key="child_youth")
                subscriptions_dubais = st.number_input("Total for Subscriptions/Dubais", min_value=0.0, key="child_subs")
            
            submit = st.form_submit_button("Submit Child Partner Record")
            
            if submit:
                partner_data = {
                    "title": title,
                    "first_name": first_name,
                    "surname": surname,
                    "age": age,
                    "birthday": birthday,
                    "kingschat_phone": kingschat_phone,
                    "email": email,
                    "church": church,
                    "group_name": group_name,
                    "currency": currency,
                    "total_wonder_challenge": wonder_challenge,
                    "total_rhapsody_languages": rhapsody_languages,
                    "total_kiddies_products": kiddies_products,
                    "total_teevo": teevo,
                    "total_braille_nolb": braille_nolb,
                    "total_youth_aglow": youth_aglow,
                    "total_local_distribution": local_distribution,
                    "total_subscriptions_dubais": subscriptions_dubais
                }
                
                success, message = add_partner_record(partner_data, is_child=True)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    with tab3:
        st.subheader("Teenager Partner Form")
        with st.form("teenager_partner_form"):
            # Basic Info
            title = st.selectbox("Title", CHILD_TITLE_OPTIONS, key="teen_title")
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("First Name", key="teen_first_name")
            with col2:
                surname = st.text_input("Surname", key="teen_surname")
            
            # Contact Info
            col1, col2 = st.columns(2)
            with col1:
                kingschat_phone = st.text_input("KingsChat Phone Number", key="teen_phone")
            with col2:
                email = st.text_input("Email Address", key="teen_email")
            
            birthdays = st.date_input("Birthday", key="teen_birthday")
            
            # Church Info
            col1, col2 = st.columns(2)
            with col1:
                church = st.text_input("Church", key="teen_church")
            with col2:
                group_name = st.text_input("Group", key="teen_group")
            
            # Financial Info
            currency = st.selectbox("Currency", CURRENCIES, key="teen_currency")
            
            col1, col2 = st.columns(2)
            with col1:
                wonder_challenge = st.number_input("Total Amount for Wonder Challenge", min_value=0.0, key="teen_wonder")
                kiddies_products = st.number_input("Total Amount for Kiddies Products", min_value=0.0, key="teen_kiddies")
                braille_nolb = st.number_input("Total Amount for Braille(NOLB)", min_value=0.0, key="teen_braille")
                local_distribution = st.number_input("Total for Local Distribution", min_value=0.0, key="teen_local")
            with col2:
                rhapsody_languages = st.number_input("Total Amount for Rhapsody Languages", min_value=0.0, key="teen_rhapsody")
                teevo = st.number_input("Total Amount for Teevo", min_value=0.0, key="teen_teevo")
                youth_aglow = st.number_input("Total Amount for Youth Aglow", min_value=0.0, key="teen_youth")
                subscriptions_dubais = st.number_input("Total for Subscriptions/Dubais", min_value=0.0, key="teen_subs")
            
            submit = st.form_submit_button("Submit Teenager Partner Record")
            
            if submit:
                partner_data = {
                    "title": title,
                    "first_name": first_name,
                    "surname": surname,
                    "kingschat_phone": kingschat_phone,
                    "email": email,
                    "birthdays": birthdays,
                    "church": church,
                    "group_name": group_name,
                    "currency": currency,
                    "total_wonder_challenge": wonder_challenge,
                    "total_rhapsody_languages": rhapsody_languages,
                    "total_kiddies_products": kiddies_products,
                    "total_teevo": teevo,
                    "total_braille_nolb": braille_nolb,
                    "total_youth_aglow": youth_aglow,
                    "total_local_distribution": local_distribution,
                    "total_subscriptions_dubais": subscriptions_dubais
                }
                
                success, message = add_partner_record(partner_data, is_teenager=True)
                if success:
                    st.success(message)
                else:
                    st.error(message)

    with tab4:
        st.subheader("External Partner Form")
        with st.form("external_partner_form"):
            # Basic Info
            title = st.selectbox("Title", TITLE_OPTIONS, key="external_title")
            col1, col2 = st.columns(2)
            with col1:
                first_name = st.text_input("First Name", key="external_first_name")
            with col2:
                surname = st.text_input("Surname", key="external_surname")
            
            # Contact Info
            col1, col2 = st.columns(2)
            with col1:
                kingschat_phone = st.text_input("KingsChat Phone Number", key="external_phone")
            with col2:
                email = st.text_input("Email Address", key="external_email")
            
            # Financial Info
            currency = st.selectbox("Currency", CURRENCIES, key="external_currency")
            
            col1, col2 = st.columns(2)
            with col1:
                rhapsody_subs = st.number_input("Rhapsody Subscriptions and Dubais", min_value=0.0)
                retail_center = st.number_input("Sponsorship Through Retail Center", min_value=0.0)
            with col2:
                translators = st.number_input("Translators Network International", min_value=0.0)
                influencers = st.number_input("Rhapsody Influencers Network", min_value=0.0)
                rim = st.number_input("RIM", min_value=0.0)
            
            submit = st.form_submit_button("Submit External Partner Record")
            
            if submit:
                partner_data = {
                    "title": title,
                    "first_name": first_name,
                    "surname": surname,
                    "kingschat_phone": kingschat_phone,
                    "email": email,
                    "currency": currency,
                    "rhapsody_subscriptions_dubais": rhapsody_subs,
                    "sponsorship_retail_center": retail_center,
                    "translators_network_international": translators,
                    "rhapsody_influencers_network": influencers,
                    "rim": rim
                }
                
                success, message = add_external_partner_record(partner_data)
                if success:
                    st.success(message)
                else:
                    st.error(message)

# Initialize the database
init_partner_db()

# This allows the file to be imported without running the UI
if __name__ == "__main__":
    partner_records_ui()

# Update the add_external_partner_record function
def add_external_partner_record(partner_data):
    """Add a new external partner record"""
    try:
        # Save record
        success, message = save_partner_record("External Partner", partner_data)
        return success, message
    except Exception as e:
        st.error(f"Error adding external partner record: {str(e)}")
        return False, f"Error adding external partner record: {str(e)}"

def get_filtered_partner_records(user_zone=None):
    """Get filtered partner records focusing on amounts"""
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
                df['original_amount'] = df['record_data'].apply(lambda x: float(x.get('original_amount', 0)))
                df['grand_total'] = df['record_data'].apply(lambda x: float(x.get('grand_total', 0)))
                df['record_type'] = record_type
                
                # Update the Amount display format to clearly show both amounts
                df['Amount'] = df.apply(
                    lambda row: f"{row['currency']} {row['original_amount']:,.2f} "
                              f"(ESPEES {row['grand_total']:,.2f})",
                    axis=1
                )
                
                # Filter by user zone if specified
                if user_zone:
                    df = df[df['zone'] == user_zone]
                
                dfs.append(df)
        
        conn.close()
        
        # Combine all DataFrames
        if dfs:
            combined_df = pd.concat(dfs, ignore_index=True)
            
            # Select display columns - focusing on partner info and amounts
            display_columns = [
                'id', 'record_type', 'title', 'first_name', 'surname',
                'zone', 'Amount', 'submission_date'
            ]
            
            return combined_df[display_columns]
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error getting partner records: {e}")
        return pd.DataFrame()

# Add these functions to partner_records.py

def delete_partner_record(record_id, record_type):
    """Delete a partner record"""
    try:
        conn = sqlite3.connect('partner_records.db')
        c = conn.cursor()
        
        # Map record type to table name
        table_map = {
            'Adult Partner': 'adult_partners',
            'Child Partner': 'children_partners',
            'Teenager Partner': 'teenager_partners',
            'External Partner': 'external_partners'
        }
        
        table_name = table_map.get(record_type)
        if not table_name:
            return False, f"Invalid record type: {record_type}"

        # Delete the record
        c.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()
        
        return True, "Record deleted successfully!"
    except Exception as e:
        return False, f"Error deleting record: {str(e)}"

def update_partner_record(record_id, record_type, updated_data):
    """Update an existing partner record"""
    try:
        conn = sqlite3.connect('partner_records.db')
        c = conn.cursor()
        
        # Map record type to table name
        table_map = {
            'Adult Partner': 'adult_partners',
            'Child Partner': 'children_partners',
            'Teenager Partner': 'teenager_partners',
            'External Partner': 'external_partners'
        }
        
        table_name = table_map.get(record_type)
        if not table_name:
            return False, f"Invalid record type: {record_type}"

        # Calculate original amount and converted amount (ESPEES)
        currency = updated_data.get('currency', 'ESPEES')
        
        # Calculate total amount based on record type
        if record_type == "External Partner":
            original_amount = sum([
                float(updated_data.get('rhapsody_subscriptions_dubais', 0)),
                float(updated_data.get('sponsorship_retail_center', 0)),
                float(updated_data.get('translators_network_international', 0)),
                float(updated_data.get('rhapsody_influencers_network', 0)),
                float(updated_data.get('rim', 0))
            ])
        else:
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

        # Convert to ESPEES and store both amounts
        grand_total = convert_to_espees(original_amount, currency)
        
        # Store both original and converted amounts
        updated_data.update({
            'original_amount': original_amount,
            'grand_total': grand_total,
            'currency': currency
        })
        
        # Convert datetime objects to strings
        processed_data = {}
        for key, value in updated_data.items():
            if isinstance(value, datetime):
                processed_data[key] = value.isoformat()
            elif isinstance(value, pd._libs.tslibs.timestamps.Timestamp):
                processed_data[key] = value.isoformat()
            else:
                processed_data[key] = value

        # Store as JSON string
        record_json = json.dumps(processed_data)
        
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
        return False, f"Error updating record: {str(e)}"
