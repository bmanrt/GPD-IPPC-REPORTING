import sqlite3
import streamlit as st
from typing import Optional

def delete_partner_record(partner_id: int, record_type: str) -> tuple[bool, Optional[str]]:
    """
    Delete a partner record from the specified table based on record type.
    
    Args:
        partner_id: The ID of the partner record to delete
        record_type: The type of partner record ('Adult Partner', 'Child Partner', etc.)
        
    Returns:
        tuple: (success: bool, error_message: Optional[str])
    """
    table_mapping = {
        'Adult Partner': 'adult_partners',
        'Child Partner': 'children_partners',
        'Teenager Partner': 'teenager_partners',
        'External Partner': 'external_partners'
    }
    
    if record_type not in table_mapping:
        return False, f"Invalid record type: {record_type}"
    
    table_name = table_mapping[record_type]
    
    try:
        conn = sqlite3.connect('partner_records.db')
        cursor = conn.cursor()
        
        # First verify the record exists
        cursor.execute(f"SELECT id FROM {table_name} WHERE id = ?", (partner_id,))
        if not cursor.fetchone():
            conn.close()
            return False, f"No {record_type} found with ID {partner_id}"
        
        # Delete the record
        cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (partner_id,))
        conn.commit()
        conn.close()
        
        return True, None
        
    except sqlite3.Error as e:
        return False, f"Database error: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error: {str(e)}"

def manage_records_ui():
    """Streamlit UI for managing partner records"""
    st.title("Manage Partner Records")
    
    # Record type selection
    record_type = st.selectbox(
        "Select Partner Type",
        [
            'Adult Partner',
            'Child Partner',
            'Teenager Partner',
            'External Partner'
        ]
    )
    
    # Input for partner ID
    partner_id = st.number_input(
        "Enter Partner ID to Delete",
        min_value=1,
        step=1
    )
    
    # Confirmation and deletion
    if st.button("Delete Partner Record"):
        # Add confirmation dialog
        if st.session_state.get('confirm_delete') != partner_id:
            st.session_state.confirm_delete = partner_id
            st.warning(f"Are you sure you want to delete {record_type} with ID {partner_id}? "
                      "Click Delete again to confirm.")
        else:
            success, error_message = delete_partner_record(partner_id, record_type)
            
            if success:
                st.success(f"Successfully deleted {record_type} with ID {partner_id}")
                # Clear confirmation state
                st.session_state.confirm_delete = None
            else:
                st.error(f"Failed to delete record: {error_message}")
    
    # Help text
    st.markdown("""
    ### Instructions
    1. Select the type of partner record you want to delete
    2. Enter the Partner ID
    3. Click the Delete button
    4. Confirm the deletion when prompted
    
    **Note**: This action cannot be undone. Please make sure you have the correct Partner ID before deleting.
    """)

if __name__ == "__main__":
    manage_records_ui()
