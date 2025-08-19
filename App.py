import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime
import json

# ------------------------
# Page Config
# ------------------------
st.set_page_config(page_title="Supabase Real Estate Portal", layout="wide")

# ------------------------
# Sidebar Config
# ------------------------
st.sidebar.title("🔑 Supabase Connection")
url = st.sidebar.text_input("Supabase URL", "https://your-project.supabase.co")
key = st.sidebar.text_input("Supabase API Key (service_role for demo)", type="password")

@st.cache_resource
def init_client(url, key):
    return create_client(url, key)

if url and key:
    supabase: Client = init_client(url, key)
    st.sidebar.success("Connected ✅")
else:
    st.warning("Enter Supabase credentials in the sidebar to continue")
    st.stop()

# ------------------------
# Schema Bootstrap (ensure tables exist)
# ------------------------
SCHEMA_SQL = """
-- put your schema here (truncated for brevity)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'subscriber',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_usage (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT 'property_search',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    response_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS properties (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    property_hash VARCHAR(32) UNIQUE,
    data JSONB NOT NULL,
    search_params JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_favorite BOOLEAN DEFAULT FALSE,
    notes TEXT,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[]
);

CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    user_data JSONB NOT NULL,
    last_login TIMESTAMPTZ DEFAULT NOW(),
    session_count INTEGER DEFAULT 1,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_alerts (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    alert_name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    location VARCHAR(255),
    criteria JSONB NOT NULL,
    threshold DECIMAL(10,2),
    notification_method VARCHAR(20) DEFAULT 'email',
    is_active BOOLEAN DEFAULT TRUE,
    last_triggered TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS property_comparisons (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    comparison_name VARCHAR(255),
    property_ids INTEGER[] NOT NULL,
    comparison_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    notifications JSONB DEFAULT '{}',
    display_settings JSONB DEFAULT '{}',
    api_settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolio_analytics (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    calculation_date DATE DEFAULT CURRENT_DATE,
    total_properties INTEGER DEFAULT 0,
    total_value DECIMAL(15,2) DEFAULT 0,
    total_monthly_rent DECIMAL(10,2) DEFAULT 0,
    average_cap_rate DECIMAL(5,2) DEFAULT 0,
    total_cash_flow DECIMAL(10,2) DEFAULT 0,
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    search_name VARCHAR(255) NOT NULL,
    search_criteria JSONB NOT NULL,
    auto_notify BOOLEAN DEFAULT FALSE,
    last_run TIMESTAMPTZ,
    results_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
"""

if st.sidebar.button("🛠️ Ensure Schema Exists"):
    try:
        supabase.postgrest.rpc("exec_sql", {"sql": SCHEMA_SQL}).execute()
        st.success("Schema ensured ✅ (tables created if missing)")
    except Exception as e:
        st.error(f"Schema creation failed: {e}")

# ------------------------
# Table Viewer & Editor
# ------------------------
tables = [
    "users",
    "api_usage",
    "properties",
    "user_sessions",
    "market_alerts",
    "property_comparisons",
    "user_preferences",
    "portfolio_analytics",
    "saved_searches"
]
choice = st.sidebar.selectbox("Choose Table", tables)

st.title(f"📊 {choice.capitalize()} Data")

def fetch_data(table):
    try:
        data = supabase.table(table).select("*").limit(100).execute()
        return pd.DataFrame(data.data) if data.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Fetch error: {e}")
        return pd.DataFrame()

df = fetch_data(choice)
if df.empty:
    st.info("No records yet.")
else:
    st.dataframe(df, use_container_width=True)

# ------------------------
# Insert Form (Generic)
# ------------------------
st.subheader(f"➕ Insert into {choice}")

if choice == "users":
    email = st.text_input("Email")
    full_name = st.text_input("Full Name")
    role = st.selectbox("Role", ["subscriber", "agent", "admin"])
    if st.button("Add User"):
        supabase.table("users").insert({
            "email": email,
            "full_name": full_name,
            "role": role,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        st.success("User added")
        st.experimental_rerun()

elif choice == "properties":
    user_id = st.number_input("User ID", min_value=1)
    data_json = st.text_area("Property JSON", '{"address": "123 Main St", "price": "500000"}')
    if st.button("Add Property"):
        supabase.table("properties").insert({
            "user_id": user_id,
            "data": json.loads(data_json),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        st.success("Property added")
        st.experimental_rerun()

else:
    st.write("⚡ Insert form not yet built for this table. (Add JSON input form here)")

# ------------------------
# Delete
# ------------------------
if not df.empty:
    st.subheader("🗑️ Delete Record")
    row_id = st.selectbox("Select ID", df["id"].tolist())
    if st.button("Delete"):
        supabase.table(choice).delete().eq("id", row_id).execute()
        st.success(f"Deleted record {row_id}")
        st.experimental_rerun()
