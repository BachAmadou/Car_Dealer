import streamlit as st
import pandas as pd
from PIL import Image
import io

# --- CONFIGURATION ---
st.set_page_config(page_title="Car Dealer Pro", layout="wide")

# --- INITIALIZE SESSION STATE ---
# This acts like a temporary database while the app is running
if 'inventory' not in st.session_state:
    st.session_state.inventory = pd.DataFrame(columns=[
        'Car', 'Purchase Price', 'Total Expenses', 'Total Cost', 'Status'
    ])
if 'expense_details' not in st.session_state:
    st.session_state.expense_details = {} 
if 'shipping_photos' not in st.session_state:
    st.session_state.shipping_photos = {} 
if 'view_mode' not in st.session_state:
    st.session_state.view_mode = "Dashboard"
if 'selected_car' not in st.session_state:
    st.session_state.selected_car = None

# --- CATEGORY LIST (Standardized localized fees) ---
STANDARD_EXPENSES = [
    "Shipping & Opening", "Registration", "ECTN/BESC", "Taxes", 
    "Vehicle Transport", "Battery/Tires", "Storage Fees", 
    "Stickers/Labels", "Withdrawal Fees", "Transit Permit"
]

# --- NAVIGATION HELPER ---
def show_details(car_name):
    st.session_state.selected_car = car_name
    st.session_state.view_mode = "Details"

def go_home():
    st.session_state.view_mode = "Dashboard"

# --- PAGE 1: MAIN DASHBOARD ---
if st.session_state.view_mode == "Dashboard":
    st.title("🚗 Dealer Inventory Dashboard")
    
    # 1. Summary Metrics
    k1, k2, k3 = st.columns(3)
    total_val = st.session_state.inventory['Total Cost'].sum()
    k1.metric("Total Stock Value", f"${total_val:,.2f}")
    k2.metric("Vehicles in Stock", len(st.session_state.inventory))
    
    # 2. Add New Vehicle Section
    with st.expander("➕ Register New Vehicle"):
        with st.form("new_car_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            name = col1.text_input("Vehicle Name (Year/Make/Model)")
            buy_price = col2.number_input("Purchase Price ($)", min_value=0)
            
            st.write("---")
            st.subheader("Expenses Breakdown")
            exp_cols = st.columns(2)
            temp_expenses = {}
            
            # Standard Fees
            for i, exp in enumerate(STANDARD_EXPENSES):
                target_col = exp_cols[0] if i < 5 else exp_cols[1]
                temp_expenses[exp] = target_col.number_input(exp, min_value=0, key=f"std_{exp}")

            st.write("**Other / Miscellaneous Expenses**")
            custom_label = st.text_input("Custom Expense Name (e.g. Mechanic)")
            custom_val = st.number_input("Custom Amount ($)", min_value=0)
            
            st.write("---")
            photos = st.file_uploader("Upload Shipping/Arrival Photos", accept_multiple_files=True)
            
            if st.form_submit_button("Save Vehicle"):
                if name:
                    if custom_label and custom_val > 0:
                        temp_expenses[custom_label] = custom_val
                    
                    total_e = sum(temp_expenses.values())
                    new_row = {
                        'Car': name, 
                        'Purchase Price': buy_price, 
                        'Total Expenses': total_e, 
                        'Total Cost': buy_price + total_e, 
                        'Status': 'In Stock'
                    }
                    
                    st.session_state.inventory = pd.concat([st.session_state.inventory, pd.DataFrame([new_row])], ignore_index=True)
                    st.session_state.expense_details[name] = temp_expenses
                    st.session_state.shipping_photos[name] = photos
                    st.success(f"Vehicle {name} added successfully!")
                    st.rerun()

    # 3. Inventory Display
    st.subheader("Current Inventory")
    if st.session_state.inventory.empty:
        st.info("No vehicles registered yet.")
    else:
        for index, row in st.session_state.inventory.iterrows():
            with st.container():
                c1, c2, c3, c4 = st.columns([3, 1.5, 1, 1])
                c1.write(f"### {row['Car']}")
                c2.write(f"**Total Cost:** ${row['Total Cost']:,.2f}")
                c3.write(f"**Status:** {row['Status']}")
                if c4.button("View Details", key=f"view_{index}"):
                    show_details(row['Car'])
                    st.rerun()
                st.write("---")

# --- PAGE 2: DETAILED VEHICLE VIEW ---
elif st.session_state.view_mode == "Details":
    car = st.session_state.selected_car
    st.button("⬅️ Back to Dashboard", on_click=go_home)
    
    st.title(f"Detailed Analysis: {car}")
    
    col_left, col_right = st.columns([1, 2])
    
    with col_left:
        st.subheader("💰 Financials")
        details = st.session_state.expense_details.get(car, {})
        main_data = st.session_state.inventory[st.session_state.inventory['Car'] == car].iloc[0]
        
        st.write(f"**Initial Purchase:** ${main_data['Purchase Price']:,.2f}")
        st.write("---")
        for item, price in details.items():
            if price > 0:
                st.write(f"{item}: ${price:,.2f}")
        st.write("---")
        st.success(f"**Total Landed Cost:** ${main_data['Total Cost']:,.2f}")

    with col_right:
        st.subheader("📸 Logistics Photos")
        car_photos = st.session_state.shipping_photos.get(car, [])
        if car_photos:
            p_cols = st.columns(2)
            for i, p in enumerate(car_photos):
                p_cols[i % 2].image(p, use_container_width=True)
        else:
            st.warning("No photos uploaded for this vehicle.")