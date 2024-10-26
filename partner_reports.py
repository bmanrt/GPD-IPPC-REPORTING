import streamlit as st
import pandas as pd
from partner_records import fetch_partner_records, delete_partner_record, update_partner_record, CURRENCIES, TITLE_OPTIONS
import io
from datetime import datetime
import time

def partner_reports_ui():
    st.header("Partner Reports")
    
    # Fetch all partner records
    df = fetch_partner_records()
    
    if df.empty:
        st.warning("No partner records found")
        return

    # Convert submission_date to datetime
    df['submission_date'] = pd.to_datetime(df['submission_date'])

    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Records", len(df))
    with col2:
        st.metric("Total ESPEES", f"{df['grand_total'].sum():,.2f}")
    with col3:
        unique_partners = len(df[['first_name', 'surname', 'email']].drop_duplicates())
        st.metric("Unique Partners", unique_partners)

    # Display detailed records
    st.subheader("Partner Records")
    display_cols = [
        'submission_date', 
        'record_type', 
        'title', 
        'first_name', 
        'surname', 
        'email', 
        'currency', 
        'original_amount', 
        'grand_total'
    ]
    
    # Format the display
    display_df = df[display_cols].copy()
    display_df['Partner Name'] = display_df.apply(
        lambda x: f"{x['title']} {x['first_name']} {x['surname']}", axis=1
    )
    display_df['Amount'] = display_df.apply(
        lambda x: f"{x['currency']} {x['original_amount']:,.2f} (ESPEES {x['grand_total']:,.2f})",
        axis=1
    )
    
    # Final display columns
    final_display_cols = [
        'submission_date',
        'Partner Name',
        'record_type',
        'email',
        'Amount'
    ]
    
    st.dataframe(
        display_df[final_display_cols],
        use_container_width=True
    )

    # Edit/Delete section
    st.subheader("Edit/Delete Records")
    
    # Initialize session state for edit/delete confirmations
    if 'edit_mode' not in st.session_state:
        st.session_state.edit_mode = {}
    if 'delete_confirmations' not in st.session_state:
        st.session_state.delete_confirmations = {}
    
    # Search functionality
    search_term = st.text_input("Search by Name, Email, or ID", key="partner_search")
    if search_term:
        search_df = display_df[
            display_df['Partner Name'].str.contains(search_term, case=False, na=False) |
            display_df['email'].str.contains(search_term, case=False, na=False) |
            df['id'].astype(str).str.contains(search_term)
        ]
        
        if not search_df.empty:
            st.write("Search Results:")
            for idx, row in search_df.iterrows():
                record_id = str(df.iloc[idx]['id'])
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"{row['Partner Name']} ({row['record_type']}) - {row['Amount']}")
                
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
                                success, message = delete_partner_record(record_id, df.iloc[idx]['record_type'])
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
                        st.write("### Edit Partner Record")
                        
                        # Basic Info
                        title = st.selectbox("Title", TITLE_OPTIONS, 
                            index=TITLE_OPTIONS.index(df.iloc[idx]['title']))
                        col1, col2 = st.columns(2)
                        with col1:
                            first_name = st.text_input("First Name", 
                                value=df.iloc[idx]['first_name'])
                        with col2:
                            surname = st.text_input("Surname", 
                                value=df.iloc[idx]['surname'])
                        
                        # Contact Info
                        col1, col2 = st.columns(2)
                        with col1:
                            email = st.text_input("Email", 
                                value=df.iloc[idx]['email'])
                        with col2:
                            currency = st.selectbox("Currency", CURRENCIES,
                                index=CURRENCIES.index(df.iloc[idx]['currency']))
                        
                        # Amount fields based on record type
                        record_data = df.iloc[idx]['record_data']
                        if df.iloc[idx]['record_type'] == 'External Partner':
                            col1, col2 = st.columns(2)
                            with col1:
                                rhapsody_subs = st.number_input("Rhapsody Subscriptions/Dubais", 
                                    value=float(record_data.get('rhapsody_subscriptions_dubais', 0)))
                                retail_center = st.number_input("Retail Center", 
                                    value=float(record_data.get('sponsorship_retail_center', 0)))
                            with col2:
                                translators = st.number_input("Translators Network", 
                                    value=float(record_data.get('translators_network_international', 0)))
                                influencers = st.number_input("Influencers Network", 
                                    value=float(record_data.get('rhapsody_influencers_network', 0)))
                                rim = st.number_input("RIM", 
                                    value=float(record_data.get('rim', 0)))
                        else:
                            col1, col2 = st.columns(2)
                            with col1:
                                wonder_challenge = st.number_input("Wonder Challenge", 
                                    value=float(record_data.get('total_wonder_challenge', 0)))
                                kiddies_products = st.number_input("Kiddies Products", 
                                    value=float(record_data.get('total_kiddies_products', 0)))
                                braille_nolb = st.number_input("Braille(NOLB)", 
                                    value=float(record_data.get('total_braille_nolb', 0)))
                                local_distribution = st.number_input("Local Distribution", 
                                    value=float(record_data.get('total_local_distribution', 0)))
                            with col2:
                                rhapsody_languages = st.number_input("Rhapsody Languages", 
                                    value=float(record_data.get('total_rhapsody_languages', 0)))
                                teevo = st.number_input("Teevo", 
                                    value=float(record_data.get('total_teevo', 0)))
                                youth_aglow = st.number_input("Youth Aglow", 
                                    value=float(record_data.get('total_youth_aglow', 0)))
                                subscriptions_dubais = st.number_input("Subscriptions/Dubais", 
                                    value=float(record_data.get('total_subscriptions_dubais', 0)))
                        
                        # Submit buttons
                        col1, col2 = st.columns(2)
                        with col1:
                            submit = st.form_submit_button("Update Record")
                        with col2:
                            cancel = st.form_submit_button("Cancel")
                        
                        if submit:
                            # Prepare updated data based on record type
                            if df.iloc[idx]['record_type'] == 'External Partner':
                                updated_data = {
                                    'title': title,
                                    'first_name': first_name,
                                    'surname': surname,
                                    'email': email,
                                    'currency': currency,
                                    'rhapsody_subscriptions_dubais': rhapsody_subs,
                                    'sponsorship_retail_center': retail_center,
                                    'translators_network_international': translators,
                                    'rhapsody_influencers_network': influencers,
                                    'rim': rim
                                }
                            else:
                                updated_data = {
                                    'title': title,
                                    'first_name': first_name,
                                    'surname': surname,
                                    'email': email,
                                    'currency': currency,
                                    'total_wonder_challenge': wonder_challenge,
                                    'total_rhapsody_languages': rhapsody_languages,
                                    'total_kiddies_products': kiddies_products,
                                    'total_teevo': teevo,
                                    'total_braille_nolb': braille_nolb,
                                    'total_youth_aglow': youth_aglow,
                                    'total_local_distribution': local_distribution,
                                    'total_subscriptions_dubais': subscriptions_dubais
                                }
                            
                            success, message = update_partner_record(record_id, df.iloc[idx]['record_type'], updated_data)
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

    # Export options
    st.subheader("Export Options")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        display_df[final_display_cols].to_excel(
            writer, 
            sheet_name='Partner Records', 
            index=False
        )
    
    st.download_button(
        label="Download Excel Report",
        data=output.getvalue(),
        file_name=f"partner_report_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    partner_reports_ui()
