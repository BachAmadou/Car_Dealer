# Import necessary tools:
# streamlit: For the web interface
# pandas: For organizing data into tables (DataFrames)
# sqlite3: For our permanent database storage
# os: For handling folders and file paths on your computer
# datetime: For managing dates (acquired/sold)
# plotly.express: For creating professional charts and graphs
import streamlit as st
import pandas as pd
import sqlite3
import os
import datetime
import plotly.express as px

# --- 1. SETUP & THEMING ---
# Engineering Note: If DATA_PATH is set in environment variables (like on a server), use it.
# Otherwise, use the current folder. This prevents errors during local development.
DATA_BASE_DIR = os.getenv("DATA_PATH", os.path.abspath(os.path.dirname(__file__)))
UPLOAD_DIR = os.path.join(DATA_BASE_DIR, "car_photos")
DOCS_DIR = os.path.join(DATA_BASE_DIR, "car_documents")
DB_NAME = os.path.join(DATA_BASE_DIR, "dealer_inventory.db")

# Create folders for storage if they don't exist yet
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)
if not os.path.exists(DOCS_DIR):
    os.makedirs(DOCS_DIR)

st.set_page_config(page_title="Car Dealer Pro", layout="wide", page_icon="🏎️")

# Custom CSS for a modern "Card" look
st.markdown("""
    <style>
    .main {
        background-color: var(--background-color);
    }
    .stMetric {
        background-color: var(--secondary-background-color);
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        color: var(--text-color);
    }
    div[data-testid="stExpander"] {
        background-color: var(--secondary-background-color);
        border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border-radius: 10px;
    }
    .car-card {
        background-color: var(--secondary-background-color);
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 20px;
        border-left: 5px solid #007bff;
        color: var(--text-color);
    }
    /* Ensures the card header wraps nicely on mobile devices */
    .car-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATABASE LOGIC (Same robust logic) ---
# This function creates the 'filing cabinet' (Database) structure if it's the first time running
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Create the 'cars' table. We add date_acquired and date_sold as TEXT 
    # because SQLite stores dates as strings in 'YYYY-MM-DD' format.
    c.execute('''CREATE TABLE IF NOT EXISTS cars (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 name TEXT, buy_price REAL, total_cost REAL, 
                 sale_price REAL DEFAULT 0,
                 date_acquired TEXT, date_sold TEXT,
                 notes TEXT)''')
    
    # Migration logic: This checks if columns exist and adds them if you are updating an old database
    c.execute("PRAGMA table_info(cars)")
    cols = [column[1] for column in c.fetchall()]
    
    # These IF statements check your 'filing cabinet' (DB) structure.
    # If you added a feature later (like 'notes'), we make sure the table is updated without breaking old data.
    if 'sale_price' not in cols:
        c.execute("ALTER TABLE cars ADD COLUMN sale_price REAL DEFAULT 0")
    if 'date_acquired' not in cols:
        c.execute("ALTER TABLE cars ADD COLUMN date_acquired TEXT")
    if 'date_sold' not in cols:
        c.execute("ALTER TABLE cars ADD COLUMN date_sold TEXT")
    if 'notes' not in cols:
        c.execute("ALTER TABLE cars ADD COLUMN notes TEXT")
        
    # Create 'expenses' table to track repairs, shipping, etc.
    c.execute('''CREATE TABLE IF NOT EXISTS expenses (
                 car_id INTEGER, label TEXT, amount REAL,
                 FOREIGN KEY(car_id) REFERENCES cars(id))''')
                 
    # Create 'images' table to store the file paths of uploaded photos
    c.execute('''CREATE TABLE IF NOT EXISTS images (
                 car_id INTEGER, path TEXT,
                 FOREIGN KEY(car_id) REFERENCES cars(id))''')
                 
    # Create 'documents' table to store other file types like Excel/Word
    c.execute('''CREATE TABLE IF NOT EXISTS documents (
                 car_id INTEGER, name TEXT, path TEXT,
                 FOREIGN KEY(car_id) REFERENCES cars(id))''')
    conn.commit()
    conn.close()

# Modified to also handle document files
def save_new_vehicle(name, buy_price, date_acquired, notes, exp_list, photo_files, doc_files):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Calculate total cost: Buy Price + all additional expenses
    total_c = buy_price + sum(item['amount'] for item in exp_list)
    
    # Insert the main car record including the acquisition date and notes
    c.execute("INSERT INTO cars (name, buy_price, total_cost, sale_price, date_acquired, notes) VALUES (?, ?, ?, 0, ?, ?)", 
              (name, buy_price, total_c, date_acquired, notes))
    car_id = c.lastrowid # Get the ID of the car we just saved
    
    # Save each expense associated with this car
    for item in exp_list:
        if item['amount'] > 0:
            c.execute("INSERT INTO expenses (car_id, label, amount) VALUES (?, ?, ?)", (car_id, item['label'], item['amount']))
            
    # Save photos to the computer and record their paths in the database
    # IF check: We only run this if the user actually uploaded files; otherwise, we skip it.
    if photo_files:
        for f in photo_files:
            path = os.path.join(UPLOAD_DIR, f"{car_id}_{f.name}")
            with open(path, "wb") as sf: sf.write(f.getbuffer())
            c.execute("INSERT INTO images (car_id, path) VALUES (?, ?)", (car_id, path))
            
    # IF check: Save documents (Excel, Word, etc.) if provided
    if doc_files:
        for f in doc_files:
            path = os.path.join(DOCS_DIR, f"{car_id}_{f.name}")
            with open(path, "wb") as sf: sf.write(f.getbuffer())
            # We store the original name too so it's easy to read in the list
            c.execute("INSERT INTO documents (car_id, name, path) VALUES (?, ?, ?)", (car_id, f.name, path))
            
    conn.commit()
    conn.close()

# This function updates an existing car's data
def update_vehicle_data(car_id, name, buy_price, sale_price, date_acquired, date_sold, notes, exp_list):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    total_c = buy_price + sum(item['amount'] for item in exp_list)
    
    # Update the main car table with all fields including new dates and notes
    c.execute("UPDATE cars SET name=?, buy_price=?, total_cost=?, sale_price=?, date_acquired=?, date_sold=?, notes=? WHERE id=?", 
              (name, buy_price, total_c, sale_price, date_acquired, date_sold, notes, car_id))
    
    # To update expenses, we delete the old ones and re-insert the updated list
    c.execute("DELETE FROM expenses WHERE car_id=?", (car_id,))
    for item in exp_list:
        if item['amount'] > 0:
            c.execute("INSERT INTO expenses (car_id, label, amount) VALUES (?, ?, ?)", (car_id, item['label'], item['amount']))
            
    conn.commit()
    conn.close()

# This function removes a car and all its related data (expenses, images, and files)
def delete_vehicle(car_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Find and delete physical image files from the computer
    c.execute("SELECT path FROM images WHERE car_id=?", (car_id,))
    for (path,) in c.fetchall():
        if os.path.exists(path):
            os.remove(path)
            
    # 3. Find and delete physical document files
    c.execute("SELECT path FROM documents WHERE car_id=?", (car_id,))
    for (path,) in c.fetchall():
        if os.path.exists(path):
            os.remove(path)
            
    # 4. Delete database records
    c.execute("DELETE FROM documents WHERE car_id=?", (car_id,))
    c.execute("DELETE FROM images WHERE car_id=?", (car_id,))
    c.execute("DELETE FROM expenses WHERE car_id=?", (car_id,))
    c.execute("DELETE FROM cars WHERE id=?", (car_id,))
    
    conn.commit()
    conn.close()

# This function deletes specific images from the folder and the database
def delete_images(image_paths):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for path in image_paths:
        # 1. Physically remove the file from your computer's folder
        if os.path.exists(path):
            os.remove(path)
        # 2. Remove the reference to this file from the database
        c.execute("DELETE FROM images WHERE path=?", (path,))
    
    conn.commit()
    conn.close()

# This function allows adding new photos to an existing car
def add_new_images(car_id, photo_files):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # IF check: Ensure there is at least one file to process before trying to save.
    if photo_files:
        for f in photo_files:
            # Create a unique filename using the car ID
            path = os.path.join(UPLOAD_DIR, f"{car_id}_{f.name}")
            with open(path, "wb") as sf: sf.write(f.getbuffer())
            # Record the new path in the database
            c.execute("INSERT INTO images (car_id, path) VALUES (?, ?)", (car_id, path))
    conn.commit()
    conn.close()

# This function allows adding documents to an existing car
def add_new_documents(car_id, doc_files):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if doc_files:
        for f in doc_files:
            path = os.path.join(DOCS_DIR, f"{car_id}_{f.name}")
            with open(path, "wb") as sf: sf.write(f.getbuffer())
            c.execute("INSERT INTO documents (car_id, name, path) VALUES (?, ?, ?)", (car_id, f.name, path))
    conn.commit()
    conn.close()

# This function removes specific documents
def delete_documents(doc_paths):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    for path in doc_paths:
        if os.path.exists(path):
            os.remove(path)
        c.execute("DELETE FROM documents WHERE path=?", (path,))
    conn.commit()
    conn.close()

# --- 3. UI LAYOUT ---
init_db() # Run database setup

# Session State acts as the app's "short-term memory" to remember which page we are on
# IF check: If the app just started, we set the default view to "Home".
if 'view' not in st.session_state: st.session_state.view = "Home"
if 'car_id' not in st.session_state: st.session_state.car_id = None
if 'delete_confirm' not in st.session_state: st.session_state.delete_confirm = False

STANDARD_EXPENSES = ["Shipping", "Registration", "Taxes", "Transport", "Repairs"]

# --- HOME VIEW ---
# IF/ELIF: This is the main "Router". It checks the session memory to see which page to draw.
if st.session_state.view == "Home":
    st.title("📊 Fleet Overview")
    
    # Fetch all cars from the database into a Pandas table
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM cars", conn)
    # Load expenses globally for some calculations
    all_expenses = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()
    
    # --- 4. SEARCH & FILTERING ---
    # We create a dedicated section for searching to keep the UI organized.
    st.write("### 🔍 Inventory Search")
    s_col1, s_col2 = st.columns([3, 1])
    
    # Keyword input for names or notes
    search_query = s_col1.text_input("Search", placeholder="Search by name or keywords in notes...", label_visibility="collapsed")
    # Dropdown to filter by availability
    status_choice = s_col2.selectbox("Filter Status", ["All Units", "In Stock", "Sold"], label_visibility="collapsed")

    # IF check: If the user typed something in the search box, we filter our data.
    # We use 'case=False' so the search is not picky about capital letters.
    if search_query:
        df = df[df['name'].str.contains(search_query, case=False, na=False) | 
                df['notes'].str.contains(search_query, case=False, na=False)]

    # IF/ELIF check: We further narrow down the list based on the "Sold" vs "In Stock" status.
    if status_choice == "In Stock":
        df = df[df['sale_price'] == 0]
    elif status_choice == "Sold":
        df = df[df['sale_price'] > 0]

    # Calculate business performance metrics
    df['profit'] = df['sale_price'] - df['total_cost']
    realized_profit = df[df['sale_price'] > 0]['profit'].sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Net Inventory Value", f"${df['total_cost'].sum():,.2f}")
    m2.metric("Total Units", len(df))
    m3.metric("Realized Profit", f"${realized_profit:,.2f}")

    st.write("##")

    # Sidebar: Area for adding new vehicles without cluttering the main screen
    with st.sidebar:
        st.header("Actions")
        with st.expander("➕ Add New Vehicle", expanded=False):
            with st.form("add_form", clear_on_submit=True):
                n = st.text_input("Model Name")
                p = st.number_input("Buy Price ($)", min_value=0.0)
                # New: Date picker for acquisition
                d_acq = st.date_input("Date Acquired", value=datetime.date.today())
                # New: Text area for comments/notes
                notes = st.text_area("Notes/Comments", placeholder="e.g., Clean title, needs oil change...")
                
                exps = []
                for label in STANDARD_EXPENSES:
                    amt = st.number_input(label, min_value=0.0)
                    exps.append({'label': label, 'amount': amt})
                up = st.file_uploader("Upload Photos", accept_multiple_files=True)
                docs = st.file_uploader("Upload Documents (Excel, Word, CSV, etc.)", accept_multiple_files=True)
                
                if st.form_submit_button("Submit to Fleet"):
                    # Convert the date object to a string before saving to database
                    # IF check: We only save if the name is provided to avoid empty entries.
                    if n: save_new_vehicle(n, p, d_acq.strftime('%Y-%m-%d'), notes, exps, up, docs); st.rerun()

        # --- NEW FEATURE: GENERATE REPORTS ---
        # This expander groups the report features in the sidebar to keep the interface clean.
        with st.expander("📄 Generate Reports", expanded=False):
            st.write("Export your inventory data to a CSV file for printing or bookkeeping.")
            
            # Select box to choose which group of cars to include in the report.
            report_choice = st.selectbox("Select Report Type", ["All Cars", "Sold Only", "In Stock Only"], key="report_type_select")
            
            # We fetch a fresh copy of all data specifically for the report to ensure no search filters affect it.
            conn = sqlite3.connect(DB_NAME); r_df = pd.read_sql_query("SELECT * FROM cars", conn); conn.close()
            
            # IF check: We only proceed if there are actually cars in the database.
            if not r_df.empty:
                # IF/ELIF: Filter the data based on what the user picked in the selectbox.
                if report_choice == "Sold Only":
                    r_df = r_df[r_df['sale_price'] > 0]
                elif report_choice == "In Stock Only":
                    r_df = r_df[r_df['sale_price'] == 0]
                
                # We manually add the Profit/Loss calculation to the report columns.
                r_df['Profit_Loss'] = r_df['sale_price'] - r_df['total_cost']
                
                # Convert the data into a CSV string (Excel-friendly format).
                csv_data = r_df.to_csv(index=False).encode('utf-8')
                
                # The download button creates the file and prompts the user to save it.
                st.download_button(
                    label=f"📥 Download {report_choice} Report",
                    data=csv_data,
                    file_name=f"car_report_{report_choice.lower().replace(' ', '_')}_{datetime.date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                # ELSE: If the database is empty, we show a warning instead of a button.
                st.warning("No data available to generate a report.")

        st.write("---")
        # NEW: Analytics shortcut added to the action list.
        # This provides a cleaner look by replacing the old radio button navigation.
        if st.button("📈 View Business Analytics", use_container_width=True):
            st.session_state.view = "Analytics"
            st.rerun()

    # Loop through each car in the database and display it as a card
    st.subheader("Active Fleet Records")
    # IF check: If the database is empty, show a helpful message instead of a blank screen.
    if df.empty:
        st.info("Your fleet is empty. Use the sidebar to add your first vehicle.")
    else: # If there ARE cars, we loop through them and draw the cards.
        for _, row in df.iterrows():
            with st.container():
                # Custom HTML/CSS card for the vehicle name and status
                st.markdown(f"""
                <div class="car-card">
                    <div class="car-header">
                        <div>
                            <span style="font-size: 24px; font-weight: bold; color: var(--text-color);">{row['name']}</span><br>
                            <span style="font-size: 14px; opacity: 0.8;">📅 Acquired: {row['date_acquired'] if row['date_acquired'] else 'N/A'}</span>
                        </div>
                        <span style="background-color: {'#d4edda' if row['sale_price'] > 0 else '#fff3cd'}; 
                                     color: {'#155724' if row['sale_price'] > 0 else '#856404'}; 
                                     padding: 5px 12px; border-radius: 20px; font-weight: bold; font-size: 14px;">
                            {'SOLD' if row['sale_price'] > 0 else 'IN STOCK'}
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.write(f"**Total Investment:**  \n${row['total_cost']:,.2f}")
                
                # IF/ELSE: If the car is sold (price > 0), show profit/loss. 
                # Otherwise, just show that the sale is pending.
                if row['sale_price'] > 0:
                    prof = row['sale_price'] - row['total_cost']
                    c2.write(f"**Profit:**  \n:{'green' if prof >= 0 else 'red'}[${prof:,.2f}]")
                else:
                    c2.write("**Sale Status:**  \nPending")
                
                c3.write(f"**Purchase Price:**  \n${row['buy_price']:,.2f}")
                
                # Button to switch to the "Details" page for this specific car
                # IF check: When clicked, we change the app's 'view' memory and refresh.
                if c4.button("Open Details", key=f"v_{row['id']}", use_container_width=True):
                    st.session_state.car_id = row['id']
                    st.session_state.view = "Details"
                    st.session_state.delete_confirm = False # Reset delete status when opening new car
                    st.rerun()
                st.write("##")

# --- ANALYTICS VIEW ---
elif st.session_state.view == "Analytics":
    st.title("📈 Business Analytics")
    
    # Load data for processing
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT * FROM cars", conn)
    exp_df = pd.read_sql_query("SELECT label, amount FROM expenses", conn)
    conn.close()

    # IF check: Don't show analytics if there's no data
    if df.empty:
        st.warning("Add some vehicles to your fleet to see analytics!")
    else:
        # --- 5. DATA PREPARATION ---
        # Convert date strings to actual Python dates for calculation
        df['date_acquired'] = pd.to_datetime(df['date_acquired'], errors='coerce')
        df['date_sold'] = pd.to_datetime(df['date_sold'], errors='coerce')
        
        # Calculate Profit
        df['profit'] = df['sale_price'] - df['total_cost']
        
        # Calculate "Days in Stock"
        # IF car is sold: Date Sold - Date Acquired
        # IF car is in stock: Today - Date Acquired
        today = pd.Timestamp(datetime.date.today())
        df['days_in_stock'] = df.apply(
            lambda x: (x['date_sold'] - x['date_acquired']).days if x['sale_price'] > 0 
            else (today - x['date_acquired']).days, axis=1
        )

        # --- 6. TOP LEVEL METRICS ---
        col_a, col_b, col_c = st.columns(3)
        avg_profit = df[df['sale_price'] > 0]['profit'].mean()
        col_a.metric("Avg. Profit per Sale", f"${avg_profit:,.2f}" if not pd.isna(avg_profit) else "$0.00")
        
        avg_days = df['days_in_stock'].mean()
        col_b.metric("Avg. Days in Stock", f"{int(avg_days)} Days" if not pd.isna(avg_days) else "0 Days")
        
        total_invested = df['total_cost'].sum()
        roi = (df[df['sale_price'] > 0]['profit'].sum() / total_invested * 100) if total_invested > 0 else 0
        col_c.metric("Return on Investment (ROI)", f"{roi:.1f}%")

        st.write("---")

        # --- 7. CHARTS SECTION ---
        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Monthly Profit Trends")
            # Process data for the bar chart
            sold_df = df[df['sale_price'] > 0].copy()
            if not sold_df.empty:
                sold_df['Month'] = sold_df['date_sold'].dt.strftime('%b %Y')
                monthly_chart = sold_df.groupby('Month')['profit'].sum().reset_index()
                fig_profit = px.bar(monthly_chart, x='Month', y='profit', 
                                   labels={'profit':'Total Profit ($)'},
                                   color_discrete_sequence=['#28a745'])
                st.plotly_chart(fig_profit, use_container_width=True)
            else:
                st.info("Profit data will appear here once cars are marked as sold.")

        with c2:
            st.subheader("Expense Distribution")
            # Process data for the pie chart
            if not exp_df.empty:
                pie_data = exp_df.groupby('label')['amount'].sum().reset_index()
                fig_pie = px.pie(pie_data, values='amount', names='label', hole=0.4,
                                color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("No expense breakdown available.")

        st.write("---")
        st.subheader("Inventory Aging Analysis")
        # Histogram to show how many cars fall into specific "Days in Stock" categories
        fig_aging = px.histogram(df, x='days_in_stock', color='name',
                                 title="How many days has each car been in stock?",
                                 labels={'days_in_stock': 'Number of Days'},
                                 nbins=20)
        st.plotly_chart(fig_aging, use_container_width=True)

        # Sidebar Action: Refresh Analytics
        if st.sidebar.button("🔄 Refresh Data"):
            st.rerun()

    # Back button to return to the dashboard
    if st.button("⬅️ Back to Fleet Overview"):
        st.session_state.view = "Home"
        st.rerun()

# --- DETAILS VIEW ---
elif st.session_state.view == "Details":
    # Load the specific car details from the DB using the saved ID
    cid = st.session_state.car_id
    conn = sqlite3.connect(DB_NAME)
    car = pd.read_sql_query(f"SELECT * FROM cars WHERE id={cid}", conn).iloc[0]
    saved_exps = pd.read_sql_query(f"SELECT label, amount FROM expenses WHERE car_id={cid}", conn).to_dict('records')
    imgs = pd.read_sql_query(f"SELECT path FROM images WHERE car_id={cid}", conn)
    docs_df = pd.read_sql_query(f"SELECT name, path FROM documents WHERE car_id={cid}", conn)
    conn.close()

    # Back button to return to the dashboard
    if st.button("⬅️ Back to Dashboard"):
        st.session_state.view = "Home"; st.rerun()

    st.title(f"Inventory Details: {car['name']}")

    # Display existing notes at the top of the details page if they exist
    # IF check: Only show the blue notes box if there is actually text to show.
    if car['notes']:
        st.info(f"📝 **Vehicle Notes:**\n\n{car['notes']}")

    # Organize info into two tabs: Financials and Photos
    tab1, tab2, tab3 = st.tabs(["📊 Financials & Notes", "🖼️ Media Gallery", "📄 Documents"])

    with tab1:
        # Form to edit existing data
        with st.form("edit_full_form", clear_on_submit=True):
            f1, f2 = st.columns(2)
            new_n = f1.text_input("Update Model Name", value=car['name'])
            new_p = f2.number_input("Original Buy Price ($)", value=float(car['buy_price']))
            new_s = f1.number_input("Final Sale Price ($)", value=float(car['sale_price']))
            
            # Beginner-friendly helper to convert DB strings ('2023-01-01') back to Date objects for the picker
            def parse_date(date_str):
                # TRY/EXCEPT: A special type of if/else. If the date is valid, use it. 
                # If the date is missing or weird, default to Today's date.
                try:
                    return datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
                except:
                    return datetime.date.today()

            # Add date inputs to the editing form
            new_acq = f2.date_input("Update Date Acquired", value=parse_date(car['date_acquired']))
            new_sold = f1.date_input("Update Date Sold", value=parse_date(car['date_sold']))
            
            # New note input: No 'value' parameter is set, so it remains empty after the form resets
            add_note = st.text_area("Add a new Note/Comment", placeholder="Type here to add new information to the vehicle history...")

            st.markdown("---")
            st.subheader("Cost Breakdown")
            updated_list = []
            # Display existing expenses for editing
            cols = st.columns(2)
            for i, item in enumerate(saved_exps):
                target = cols[i % 2]
                l_val = target.text_input(f"Label {i+1}", value=item['label'], key=f"l_{i}")
                a_val = target.number_input(f"Amount {i+1}", value=float(item['amount']), key=f"a_{i}")
                updated_list.append({'label': l_val, 'amount': a_val})
            
            # Ability to add one brand-new expense item
            st.markdown("#### ➕ Add New Expense")
            nc1, nc2 = st.columns([2, 1])
            new_row_l = nc1.text_input("New Label", key="new_exp_label_input")
            new_row_a = nc2.number_input("New Amount", min_value=0.0, key="new_exp_amt_input")
            
            # IF check: Only add the new expense to the list if the user typed a label and an amount.
            if new_row_l and new_row_a > 0:
                updated_list.append({'label': new_row_l, 'amount': new_row_a})
            
            st.write("---")
            confirm_edit = st.checkbox("Check this box to confirm these changes are correct")

            if st.form_submit_button("💾 Synchronize Data"):
                # IF/ELSE: Check the confirmation box before saving.
                if confirm_edit:
                    # Convert date objects back to strings for database storage
                    date_acq_str = new_acq.strftime('%Y-%m-%d')
                    date_sold_str = new_sold.strftime('%Y-%m-%d')
                    
                    # Logic to combine existing notes with the new entry
                    current_notes = car['notes'] if car['notes'] else ""
                    # IF check: If the user wrote a new note, we append it to the old ones.
                    if add_note:
                        # Append the new text with a double newline for clean spacing
                        updated_notes = (current_notes + "\n\n" + add_note).strip()
                    else:
                        updated_notes = current_notes
                    
                    update_vehicle_data(cid, new_n, new_p, new_s, date_acq_str, date_sold_str, updated_notes, updated_list)
                    st.success("Changes saved successfully.")
                else:
                    st.warning("Please check the confirmation box before saving.")
                st.rerun()

    with tab2:
        # Section to upload new photos
        st.write("### ➕ Add New Photos")
        with st.form("add_photos_form", clear_on_submit=True):
            new_photos = st.file_uploader("Select photos to add", accept_multiple_files=True, key="additional_photos")
            if st.form_submit_button("Upload to Gallery"):
                # IF/ELSE: Ensure files were selected before trying to upload.
                if new_photos:
                    add_new_images(cid, new_photos)
                    st.success(f"Added {len(new_photos)} new photo(s)!")
                    st.rerun()
                else:
                    st.warning("Please select at least one photo.")

        st.write("---")

        # Check if the car has any images stored
        # IF check: If no photos are in the DB for this car, show a simple info message.
        if imgs.empty:
            st.info("No images uploaded for this vehicle.")
        else: # If there are photos, show the grid.
            # This list will keep track of which image paths the user checks for deletion
            to_delete = []
            
            st.write("### Manage Photos")
            st.caption("Check the boxes below to select one or more photos you wish to remove.")
            
            # Display photos in a grid (3 columns)
            p_cols = st.columns(3)
            for idx, r in imgs.iterrows():
                with p_cols[idx % 3]:
                    st.image(r['path'], use_container_width=True)
                    # Unique checkbox for each image using its database index
                    # IF check: If the user checks the box, add the image path to our 'to_delete' list.
                    if st.checkbox("Select to delete", key=f"img_chk_{idx}"):
                        to_delete.append(r['path'])
            
            # Show the delete action area only if at least one photo is selected
            # IF check: Don't show the "Delete Selected Photos" button if nothing is selected.
            if to_delete:
                st.write("---")
                st.warning(f"⚠️ You have selected {len(to_delete)} photo(s) for removal.")
                
                # Confirmation checkbox for safety
                confirm_img_del = st.checkbox("Confirm: I want to permanently delete these photos")
                
                if st.button("🗑️ Delete Selected Photos", type="primary"):
                    # IF/ELSE: Check for confirmation before running the delete function.
                    if confirm_img_del:
                        delete_images(to_delete)
                        st.success(f"Successfully deleted {len(to_delete)} photo(s).")
                        st.rerun()
                    else:
                        st.error("Please check the confirmation box before deleting.")

    with tab3:
        # Section to upload new Documents
        st.write("### ➕ Attach New Documents")
        with st.form("add_docs_form", clear_on_submit=True):
            new_docs = st.file_uploader("Select files (PDF, XLSX, DOCX, CSV)", accept_multiple_files=True, key="additional_docs")
            if st.form_submit_button("Upload to Documents"):
                if new_docs:
                    add_new_documents(cid, new_docs)
                    st.success(f"Attached {len(new_docs)} new document(s)!")
                    st.rerun()
                else:
                    st.warning("Please select at least one file.")

        st.write("---")
        st.write("### 📂 Attached Files")
        
        # IF check: Show list of documents if they exist
        if docs_df.empty:
            st.info("No documents attached to this vehicle.")
        else:
            docs_to_delete = []
            for idx, d_row in docs_df.iterrows():
                # We use a container for each file to give it some space
                with st.container():
                    col_icon, col_name, col_actions = st.columns([1, 6, 3])
                    
                    col_icon.write("📄")
                    col_name.write(f"**{d_row['name']}**")
                    
                    # Action buttons for each file
                    with col_actions:
                        # 1. Download Button
                        with open(d_row['path'], "rb") as file:
                            st.download_button(label="📥 Download", data=file, file_name=d_row['name'], key=f"dl_{idx}")
                        
                        # 2. Delete Checkbox
                        if st.checkbox("Select for removal", key=f"doc_del_{idx}"):
                            docs_to_delete.append(d_row['path'])
                    
                    # --- FEATURE: "READ" CONTENT ---
                    # If the file is CSV or Excel, we offer a "Quick Preview"
                    ext = os.path.splitext(d_row['name'])[1].lower()
                    if ext in ['.csv', '.xlsx', '.xls']:
                        with st.expander(f"🔍 Preview Content: {d_row['name']}"):
                            try:
                                if ext == '.csv':
                                    preview_df = pd.read_csv(d_row['path'])
                                else:
                                    preview_df = pd.read_excel(d_row['path'])
                                st.dataframe(preview_df, hide_index=True)
                            except Exception as e:
                                st.error(f"Could not read file content: {e}")
                    
                    st.write("---")
            
            # Handle bulk deletion of documents
            if docs_to_delete:
                st.warning(f"You have selected {len(docs_to_delete)} document(s) for removal.")
                confirm_doc_del = st.checkbox("Confirm: I want to permanently delete these documents")
                if st.button("🗑️ Delete Selected Documents", type="primary"):
                    if confirm_doc_del:
                        delete_documents(docs_to_delete)
                        st.success("Documents deleted.")
                        st.rerun()
                    else:
                        st.error("Please check the confirmation box.")

    # --- DANGER ZONE ---
    st.write("##")
    st.write("---")
    with st.expander("⚠️ Danger Zone"):
        st.write("Deleting this vehicle will remove all records and photos permanently.")
        
        # IF/ELSE: This is the two-step delete logic.
        # If the user hasn't clicked "Delete" yet, show the first button.
        if not st.session_state.delete_confirm:
            if st.button(f"Delete {car['name']}", type="primary"):
                st.session_state.delete_confirm = True
                st.rerun()
        else: # If they DID click it, show the "Are you sure?" area with Yes/No buttons.
            st.error(f"Are you sure you want to delete {car['name']}?")
            col_del1, col_del2 = st.columns(2)
            # IF check: Final confirmation button.
            if col_del1.button("✅ Yes, Delete Permanently", type="primary"):
                delete_vehicle(cid)
                st.session_state.view = "Home"
                st.session_state.car_id = None
                st.rerun()
            # IF check: Cancel button to go back.
            if col_del2.button("❌ No, Cancel"):
                st.session_state.delete_confirm = False
                st.rerun()