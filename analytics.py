import streamlit as st
import sqlite3
import pandas as pd
import json
from datetime import datetime
from calendar import month_name
import io
from church_records import CURRENCIES, CONVERSION_RATES

def fetch_all_partner_records():
    """Fetch all partner records for analytics"""
    try:
        conn = sqlite3.connect('partner_records.db')
        
        # Initialize empty list to store all records
        all_records = []
        
        # Define table mappings
        tables = {
            'adult_partners': 'Adult Partner',
            'children_partners': 'Child Partner',
            'teenager_partners': 'Teenager Partner',
            'external_partners': 'External Partner'
        }
        
        # Fetch from all tables
        for table_name, record_type in tables.items():
            try:
                query = f"SELECT id, record_data, submission_date FROM {table_name}"
                df = pd.read_sql_query(query, conn)
                if not df.empty:
                    df['record_type'] = record_type
                    all_records.append(df)
            except:
                continue
        
        conn.close()
        
        if not all_records:
            return pd.DataFrame()
            
        # Combine all records
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
                     'kingschat_phone', 'email', 'zone', 'currency']:
            combined_df[field] = combined_df['record_data'].apply(lambda x: x.get(field, ''))
        
        # Extract amount fields
        combined_df['original_amount'] = combined_df['record_data'].apply(
            lambda x: float(x.get('original_amount', 0))
        )
        combined_df['grand_total'] = combined_df['record_data'].apply(
            lambda x: float(x.get('grand_total', 0))
        )
        
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
        
        # Format amount display
        combined_df['Display Amount'] = combined_df.apply(
            lambda row: f"{row['original_amount']:,.2f} {row['currency']} "
                      f"({row['grand_total']:,.2f} ESPEES)",
            axis=1
        )
        
        return combined_df
        
    except Exception as e:
        st.error(f"Error fetching partner records: {e}")
        return pd.DataFrame()

def analytics_dashboard(key_prefix=""):
    """Main analytics dashboard function"""
    st.title("Partner Records Analytics")
    
    # Currency selection with unique key
    available_currencies = ['ESPEES'] + list(CONVERSION_RATES.keys())
    display_currency = st.selectbox(
        "Display amounts in:",
        available_currencies,
        key=f"{key_prefix}_currency_selector"
    )
    
    partners_df = fetch_all_partner_records()
    
    if not partners_df.empty:
        # Partner type selection with unique key
        partner_types = ["All Partners"] + sorted(partners_df['record_type'].unique().tolist())
        selected_partner_type = st.selectbox(
            "Select Partner Category",
            partner_types,
            key=f"{key_prefix}_partner_type_selector"
        )
        
        # Filter by partner type if not "All Partners"
        if selected_partner_type != "All Partners":
            partners_df = partners_df[partners_df['record_type'] == selected_partner_type]
        
        # Use grand_total for filtering and display
        partners_df['converted_amount'] = partners_df['grand_total']
        
        # Filter by amount range
        col1, col2 = st.columns(2)
        with col1:
            min_amount = st.number_input(
                f"Minimum Amount (ESPEES)",
                value=0.0,
                step=100.0
            )
        with col2:
            max_amount = st.number_input(
                f"Maximum Amount (ESPEES)",
                value=float(partners_df['converted_amount'].max()),
                step=100.0
            )
        
        # Apply amount range filter
        filtered_df = partners_df[
            (partners_df['converted_amount'] >= min_amount) &
            (partners_df['converted_amount'] <= max_amount)
        ]
        
        # Number of top partners to show
        max_records = len(filtered_df) if not filtered_df.empty else 1
        default_n = min(10, max_records)
        top_n = st.number_input(
            "Number of Partners to Show",
            min_value=1,
            max_value=max_records,
            value=default_n
        )
        
        # Filter by category
        if selected_partner_type == "External Partner":
            sponsorship_categories = [
                "Total Amount",
                "Rhapsody Subscriptions/Dubais",
                "Sponsorship Through Retail Center",
                "Quantity Sponsored Through IRCON",
                "Translators Network International",
                "Rhapsody Influencers Network",
                "RIM"
            ]
        else:
            sponsorship_categories = [
                "Total Amount",
                "Wonder Challenge",
                "Rhapsody Languages",
                "Kiddies Products",
                "Teevo",
                "Braille(NOLB)",
                "Youth Aglow",
                "Local Distribution",
                "Subscriptions/Dubais"
            ]
        
        # Category selection with unique key
        selected_category = st.selectbox(
            "Analyze by Category",
            sponsorship_categories,
            key=f"{key_prefix}_category_selector"
        )
        
        # Category mapping for analysis
        if selected_partner_type == "External Partner":
            category_column_map = {
                "Rhapsody Subscriptions/Dubais": "rhapsody_subscriptions_dubais",
                "Sponsorship Through Retail Center": "sponsorship_retail_center",
                "Quantity Sponsored Through IRCON": "quantity_sponsored_retail",
                "Translators Network International": "translators_network_international",
                "Rhapsody Influencers Network": "rhapsody_influencers_network",
                "RIM": "rim",
                "Total Amount": "converted_amount"
            }
        else:
            category_column_map = {
                "Wonder Challenge": "total_wonder_challenge",
                "Rhapsody Languages": "total_rhapsody_languages",
                "Kiddies Products": "total_kiddies_products",
                "Teevo": "total_teevo",
                "Braille(NOLB)": "total_braille_nolb",
                "Youth Aglow": "total_youth_aglow",
                "Local Distribution": "total_local_distribution",
                "Subscriptions/Dubais": "total_subscriptions_dubais",
                "Total Amount": "converted_amount"
            }
        
        analysis_column = category_column_map[selected_category]
        
        # Ensure numeric values for sorting
        filtered_df[analysis_column] = pd.to_numeric(filtered_df[analysis_column], errors='coerce').fillna(0)
        top_partners = filtered_df.nlargest(top_n, analysis_column)
        
        # Create display DataFrame
        display_df = pd.DataFrame({
            'Record Type': top_partners['record_type'],
            'Title': top_partners['title'],
            'First Name': top_partners['first_name'],
            'Surname': top_partners['surname'],
            'Zone': top_partners['zone'],
            'Amount': top_partners['Display Amount']
        })
        
        # Display final DataFrame
        st.write(f"#### Top {top_n} Partners by {selected_category}")
        st.dataframe(display_df, use_container_width=True)
        
        # Summary Statistics
        st.write("#### Summary Statistics")
        col4, col5, col6 = st.columns(3)
        
        with col4:
            st.metric("Total Partners", len(filtered_df))
        
        with col5:
            st.metric(
                f"Total Amount (ESPEES)",
                f"{filtered_df['grand_total'].sum():,.2f}"
            )
        
        with col6:
            avg_amount = filtered_df['grand_total'].sum() / len(filtered_df) if len(filtered_df) > 0 else 0
            st.metric(
                f"Average Amount (ESPEES)",
                f"{avg_amount:,.2f}"
            )
        
        # Export options
        st.write("### Export Options")
        col7, col8 = st.columns(2)
        
        with col7:
            if st.button("Export Top Partners"):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    display_df.to_excel(
                        writer,
                        sheet_name=f"Top {top_n} Partners",
                        index=False
                    )
                
                output.seek(0)
                st.download_button(
                    label=f"Download Top {top_n} Partners Excel",
                    data=output,
                    file_name=f"top_{top_n}_partners_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col8:
            if st.button("Export All Filtered Data"):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Export all filtered data
                    filtered_df.to_excel(
                        writer,
                        sheet_name="All Filtered Data",
                        index=False
                    )
                    
                    # Summary Statistics sheet
                    summary_stats = pd.DataFrame({
                        'Metric': ['Total Partners', f'Total Amount (ESPEES)', f'Average Amount (ESPEES)'],
                        'Value': [len(filtered_df), filtered_df['grand_total'].sum(), avg_amount]
                    })
                    summary_stats.to_excel(
                        writer,
                        sheet_name="Summary Statistics",
                        index=False
                    )
                
                output.seek(0)
                st.download_button(
                    label="Download Complete Analysis Excel",
                    data=output,
                    file_name=f"complete_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
    else:
        st.warning("No partner records found.")

if __name__ == "__main__":
    analytics_dashboard()
