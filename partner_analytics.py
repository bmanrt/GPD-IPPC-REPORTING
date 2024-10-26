import streamlit as st
import pandas as pd
from partner_records import fetch_partner_records, CURRENCIES
from datetime import datetime
import io

def partner_analytics_ui():
    st.header("Partner Analytics")
    
    # Fetch all partner records
    df = fetch_partner_records()
    
    if df.empty:
        st.warning("No partner records found")
        return

    # Currency selector at the top
    display_currency = st.selectbox(
        "Display Currency", 
        CURRENCIES,
        key="analytics_display_currency"
    )

    # Filters section
    st.subheader("Filters")
    
    # First row of filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Zone filter
        zones = ['All Zones'] + sorted(df['zone'].unique().tolist())
        selected_zone = st.selectbox(
            "Zone", 
            zones,
            key="analytics_zone"
        )

    with col2:
        # Partnership Category filter
        categories = [
            'All Categories',
            'Wonder Challenge',
            'Rhapsody Languages',
            'Kiddies Products',
            'Teevo',
            'Braille (NOLB)',
            'Youth Aglow',
            'Local Distribution',
            'Subscriptions/Dubais',
            'RIM',
            'Translators Network',
            'Retail Center'
        ]
        selected_category = st.selectbox(
            "Partnership Category", 
            categories,
            key="analytics_category"
        )

    with col3:
        # Number of top partners to display
        top_n = st.number_input(
            "Number of Top Partners to Display",
            min_value=1,
            max_value=1000,
            value=10,
            key="analytics_top_n"
        )

    # Second row of filters
    col1, col2 = st.columns(2)
    
    with col1:
        # Partner Type filter
        partner_types = ['All Types'] + sorted(df['record_type'].unique().tolist())
        selected_type = st.selectbox(
            "Partner Type",
            partner_types,
            key="analytics_partner_type"
        )

    with col2:
        # Determine which column to use for amount range
        if selected_category == 'All Categories':
            col_for_range = 'grand_total'
        else:
            category_map = {
                'Wonder Challenge': 'total_wonder_challenge',
                'Rhapsody Languages': 'total_rhapsody_languages',
                'Kiddies Products': 'total_kiddies_products',
                'Teevo': 'total_teevo',
                'Braille (NOLB)': 'total_braille_nolb',
                'Youth Aglow': 'total_youth_aglow',
                'Local Distribution': 'total_local_distribution',
                'Subscriptions/Dubais': 'total_subscriptions_dubais',
                'RIM': 'rim',
                'Translators Network': 'translators_network_international',
                'Retail Center': 'sponsorship_retail_center'
            }
            col_for_range = category_map[selected_category]

        # Amount range filter with manual input
        st.write(f"Amount Range ({display_currency})")
        amount_col1, amount_col2 = st.columns(2)
        
        with amount_col1:
            min_amount = st.number_input(
                "Minimum Amount",
                min_value=0.0,
                value=0.0,
                format="%.2f",
                key="analytics_min_amount"
            )
        
        with amount_col2:
            max_amount = st.number_input(
                "Maximum Amount",
                min_value=0.0,
                value=float(df[col_for_range].max()),
                format="%.2f",
                key="analytics_max_amount"
            )
        
        amount_range = (min_amount, max_amount)

    # Apply filters
    filtered_df = df.copy()
    
    # Zone filter
    if selected_zone != 'All Zones':
        filtered_df = filtered_df[filtered_df['zone'] == selected_zone]

    # Partner Type filter
    if selected_type != 'All Types':
        filtered_df = filtered_df[filtered_df['record_type'] == selected_type]

    # Amount range filter - only apply if max_amount > 0
    if max_amount > 0:
        filtered_df = filtered_df[
            (filtered_df[col_for_range] >= min_amount) &
            (filtered_df[col_for_range] <= max_amount)
        ]

    # Category mapping
    category_map = {
        'Wonder Challenge': 'total_wonder_challenge',
        'Rhapsody Languages': 'total_rhapsody_languages',
        'Kiddies Products': 'total_kiddies_products',
        'Teevo': 'total_teevo',
        'Braille (NOLB)': 'total_braille_nolb',
        'Youth Aglow': 'total_youth_aglow',
        'Local Distribution': 'total_local_distribution',
        'Subscriptions/Dubais': 'total_subscriptions_dubais',
        'RIM': 'rim',
        'Translators Network': 'translators_network_international',
        'Retail Center': 'sponsorship_retail_center'
    }

    # Display summary metrics
    st.subheader("Summary Metrics")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Partners", len(filtered_df))
    with col2:
        total_amount = filtered_df['grand_total'].sum()
        st.metric(f"Total ({display_currency})", f"{total_amount:,.2f}")
    with col3:
        unique_partners = len(filtered_df[['first_name', 'surname', 'email']].drop_duplicates())
        st.metric("Unique Partners", unique_partners)

    # Display top partners
    st.subheader("Top Partners")

    if selected_category == 'All Categories':
        # Show top partners by total contribution
        top_partners = filtered_df.nlargest(top_n, 'grand_total')
        display_cols = [
            'zone', 'record_type', 'title', 'first_name', 'surname',
            'email', 'grand_total'
        ]
        col_name = 'grand_total'
        metric_label = f"Total Amount ({display_currency})"
    else:
        # Show top partners for selected category
        category_col = category_map[selected_category]
        top_partners = filtered_df.nlargest(top_n, category_col)
        display_cols = [
            'zone', 'record_type', 'title', 'first_name', 'surname',
            'email', category_col, 'grand_total'
        ]
        col_name = category_col
        metric_label = f"{selected_category} Amount ({display_currency})"

    # Format the display
    st.write(f"### Top {top_n} Partners - {selected_zone if selected_zone != 'All Zones' else 'All Zones'}")
    st.write(f"Category: {selected_category}")
    
    # Create a formatted display DataFrame
    display_df = top_partners[display_cols].copy()
    display_df['Partner Name'] = display_df.apply(
        lambda x: f"{x['title']} {x['first_name']} {x['surname']}", axis=1
    )
    display_df[metric_label] = display_df[col_name].apply(
        lambda x: f"{x:,.2f}"
    )
    
    # Final display columns
    final_display_cols = ['Partner Name', 'zone', 'record_type', 'email', metric_label]
    st.dataframe(
        display_df[final_display_cols].set_index('Partner Name'),
        use_container_width=True
    )

    # Zone-wise Analysis
    if selected_zone == 'All Zones':
        st.write("### Zone-wise Analysis")
        zone_analysis = filtered_df.groupby('zone').agg({
            'grand_total': 'sum',
            'id': 'count'
        }).reset_index()
        
        zone_analysis.columns = ['Zone', 'Total Amount', 'Partner Count']
        zone_analysis['Total Amount'] = zone_analysis['Total Amount'].apply(
            lambda x: f"{x:,.2f} {display_currency}"
        )
        st.dataframe(zone_analysis, use_container_width=True)

    # Export filtered data
    st.subheader("Export Data")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        display_df[final_display_cols].to_excel(
            writer, 
            sheet_name='Top Partners', 
            index=False
        )
        if selected_zone == 'All Zones':
            zone_analysis.to_excel(
                writer,
                sheet_name='Zone Analysis',
                index=False
            )
    
    st.download_button(
        label="Download Excel Report",
        data=output.getvalue(),
        file_name=f"partner_analytics_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

if __name__ == "__main__":
    partner_analytics_ui()
