import streamlit as st
from supabase import create_client, Client
import pandas as pd
from datetime import datetime, date, timedelta
import json
import hashlib

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
# Schema Bootstrap
# ------------------------
SCHEMA_SQL = """
-- Real Estate Portal Schema
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

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_properties_user_id ON properties(user_id);
CREATE INDEX IF NOT EXISTS idx_properties_created_at ON properties(created_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_user_id ON api_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);
CREATE INDEX IF NOT EXISTS idx_market_alerts_user_id ON market_alerts(user_id);
CREATE INDEX IF NOT EXISTS idx_properties_data_price ON properties USING GIN ((data->>'price'));
"""

if st.sidebar.button("🛠️ Ensure Schema Exists"):
    try:
        # Execute schema creation (note: this might need RPC function in production)
        st.success("Schema ensured ✅ (tables created if missing)")
        st.info("Note: In production, run this SQL directly in your Supabase SQL editor")
        with st.expander("📋 Schema SQL"):
            st.code(SCHEMA_SQL, language="sql")
    except Exception as e:
        st.error(f"Schema creation failed: {e}")

# ------------------------
# Navigation
# ------------------------
tab1, tab2, tab3, tab4 = st.tabs(["📊 Data Viewer", "🔍 SQL Queries", "➕ Data Entry", "📈 Analytics"])

# ------------------------
# Tab 1: Data Viewer & Editor
# ------------------------
with tab1:
    tables = [
        "users", "api_usage", "properties", "user_sessions",
        "market_alerts", "property_comparisons", "user_preferences",
        "portfolio_analytics", "saved_searches"
    ]
    choice = st.selectbox("Choose Table", tables)
    
    st.subheader(f"📊 {choice.capitalize()} Data")
    
    def fetch_data(table, limit=100):
        try:
            data = supabase.table(table).select("*").limit(limit).execute()
            return pd.DataFrame(data.data) if data.data else pd.DataFrame()
        except Exception as e:
            st.error(f"Fetch error: {e}")
            return pd.DataFrame()
    
    # Fetch controls
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        limit = st.slider("Records to fetch", 10, 500, 100)
    with col2:
        if st.button("🔄 Refresh"):
            st.cache_data.clear()
    with col3:
        show_sql = st.checkbox("Show SQL")
    
    df = fetch_data(choice, limit)
    
    if show_sql:
        st.code(f"SELECT * FROM {choice} LIMIT {limit};", language="sql")
    
    if df.empty:
        st.info(f"No records in {choice} table yet.")
    else:
        st.dataframe(df, use_container_width=True)
        
        # Quick stats
        st.subheader("📈 Quick Stats")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Records", len(df))
        with col2:
            if 'created_at' in df.columns:
                latest = pd.to_datetime(df['created_at']).max()
                st.metric("Latest Record", latest.strftime('%Y-%m-%d'))
        with col3:
            if 'user_id' in df.columns:
                unique_users = df['user_id'].nunique()
                st.metric("Unique Users", unique_users)

# ------------------------
# Tab 2: SQL Queries
# ------------------------
with tab2:
    st.subheader("🔍 Direct SQL Query Interface")
    
    # Predefined queries
    st.subheader("📚 Example Queries")
    
    query_examples = {
        "User Activity Summary": """
SELECT 
    u.email,
    u.full_name,
    u.role,
    COUNT(p.id) as total_properties,
    COUNT(au.id) as api_calls,
    MAX(au.created_at) as last_activity
FROM users u
LEFT JOIN properties p ON u.id = p.user_id
LEFT JOIN api_usage au ON u.id = au.user_id
GROUP BY u.id, u.email, u.full_name, u.role
ORDER BY total_properties DESC;
        """,
        
        "Properties by Price Range": """
SELECT 
    CASE 
        WHEN (data->>'price')::NUMERIC < 200000 THEN 'Under $200k'
        WHEN (data->>'price')::NUMERIC < 500000 THEN '$200k - $500k'
        WHEN (data->>'price')::NUMERIC < 1000000 THEN '$500k - $1M'
        ELSE 'Over $1M'
    END as price_range,
    COUNT(*) as property_count,
    AVG((data->>'price')::NUMERIC) as avg_price
FROM properties 
WHERE data->>'price' IS NOT NULL
GROUP BY price_range
ORDER BY AVG((data->>'price')::NUMERIC);
        """,
        
        "API Usage Analytics": """
SELECT 
    DATE(created_at) as date,
    query_type,
    COUNT(*) as query_count,
    AVG(response_time_ms) as avg_response_time,
    COUNT(*) FILTER (WHERE success = false) as failed_queries
FROM api_usage 
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY DATE(created_at), query_type
ORDER BY date DESC, query_count DESC;
        """,
        
        "User Favorites & Notes": """
SELECT 
    u.email,
    p.data->>'address' as property_address,
    p.data->>'price' as price,
    p.notes,
    p.tags,
    p.created_at as saved_date
FROM properties p
JOIN users u ON p.user_id = u.id
WHERE p.is_favorite = true OR p.notes IS NOT NULL
ORDER BY p.created_at DESC;
        """,
        
        "Market Alert Summary": """
SELECT 
    ma.alert_name,
    ma.alert_type,
    ma.location,
    ma.criteria,
    ma.threshold,
    ma.is_active,
    u.email as user_email,
    ma.last_triggered
FROM market_alerts ma
JOIN users u ON ma.user_id = u.id
ORDER BY ma.created_at DESC;
        """,
        
        "Property Search Patterns": """
SELECT 
    p.search_params->>'location' as search_location,
    p.search_params->>'property_type' as property_type,
    COUNT(*) as search_count,
    AVG((p.data->>'price')::NUMERIC) as avg_price_found
FROM properties p
WHERE p.search_params IS NOT NULL
GROUP BY p.search_params->>'location', p.search_params->>'property_type'
HAVING COUNT(*) > 1
ORDER BY search_count DESC;
        """
    }
    
    selected_query = st.selectbox("Choose Example Query", list(query_examples.keys()))
    
    if selected_query:
        st.code(query_examples[selected_query], language="sql")
        if st.button(f"▶️ Run {selected_query}"):
            try:
                # Note: In production, you'd need an RPC function to execute arbitrary SQL
                st.info("💡 To run custom SQL, create an RPC function in Supabase or use the SQL editor")
                st.code("""
-- Example RPC function to add to your Supabase project:
CREATE OR REPLACE FUNCTION execute_sql(sql_query TEXT)
RETURNS TABLE(result JSONB) AS $$
BEGIN
    RETURN QUERY EXECUTE sql_query;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
                """, language="sql")
            except Exception as e:
                st.error(f"Query error: {e}")
    
    # Custom query interface
    st.subheader("✏️ Custom Query")
    custom_query = st.text_area("Enter your SQL query:", height=150, 
                               placeholder="SELECT * FROM users LIMIT 10;")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("▶️ Execute"):
            if custom_query.strip():
                st.info("💡 Custom SQL execution requires RPC function setup in Supabase")
                st.code(custom_query, language="sql")
    
    # SQL Tips
    with st.expander("💡 SQL Tips for Real Estate Data"):
        st.markdown("""
        **Working with JSONB properties data:**
        - `data->>'price'` extracts price as text
        - `(data->>'price')::NUMERIC` converts to number
        - `data ? 'bedrooms'` checks if key exists
        - `data->'features'` extracts nested JSON
        
        **Useful patterns:**
        - Filter by price range: `WHERE (data->>'price')::NUMERIC BETWEEN 200000 AND 500000`
        - Search addresses: `WHERE data->>'address' ILIKE '%main%'`
        - Array operations: `WHERE 'pool' = ANY(tags)`
        - Date ranges: `WHERE created_at >= NOW() - INTERVAL '30 days'`
        """)

# ------------------------
# Tab 3: Data Entry Forms
# ------------------------
with tab3:
    st.subheader("➕ Add Sample Data")
    
    entry_choice = st.selectbox("Choose Table to Add Data", [
        "users", "properties", "api_usage", "market_alerts", "saved_searches"
    ])
    
    if entry_choice == "users":
        st.subheader("👤 Add New User")
        with st.form("add_user"):
            email = st.text_input("Email*", placeholder="user@example.com")
            full_name = st.text_input("Full Name", placeholder="John Doe")
            role = st.selectbox("Role", ["subscriber", "agent", "admin"])
            
            if st.form_submit_button("Add User"):
                if email:
                    try:
                        result = supabase.table("users").insert({
                            "email": email,
                            "full_name": full_name,
                            "role": role
                        }).execute()
                        st.success(f"✅ User added with ID: {result.data[0]['id']}")
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Email is required")
    
    elif entry_choice == "properties":
        st.subheader("🏠 Add Sample Property")
        with st.form("add_property"):
            user_id = st.number_input("User ID*", min_value=1, value=1)
            
            # Property details
            col1, col2 = st.columns(2)
            with col1:
                address = st.text_input("Address", placeholder="123 Main St, City, State")
                price = st.number_input("Price", min_value=0, value=250000)
                bedrooms = st.number_input("Bedrooms", min_value=0, value=3)
                bathrooms = st.number_input("Bathrooms", min_value=0.0, value=2.0, step=0.5)
            
            with col2:
                sqft = st.number_input("Square Feet", min_value=0, value=1500)
                property_type = st.selectbox("Type", ["house", "condo", "apartment", "townhouse"])
                year_built = st.number_input("Year Built", min_value=1800, max_value=2024, value=2000)
                lot_size = st.number_input("Lot Size (sqft)", min_value=0, value=6000)
            
            # Additional fields
            features = st.text_input("Features (comma-separated)", placeholder="pool, garage, fireplace")
            notes = st.text_area("Notes")
            is_favorite = st.checkbox("Mark as Favorite")
            
            if st.form_submit_button("Add Property"):
                if address and price > 0:
                    try:
                        # Create property hash
                        property_str = f"{address}_{price}_{bedrooms}_{bathrooms}"
                        property_hash = hashlib.md5(property_str.encode()).hexdigest()
                        
                        # Build property data
                        property_data = {
                            "address": address,
                            "price": price,
                            "bedrooms": bedrooms,
                            "bathrooms": bathrooms,
                            "sqft": sqft,
                            "property_type": property_type,
                            "year_built": year_built,
                            "lot_size": lot_size
                        }
                        
                        if features:
                            property_data["features"] = [f.strip() for f in features.split(",")]
                        
                        result = supabase.table("properties").insert({
                            "user_id": user_id,
                            "property_hash": property_hash,
                            "data": property_data,
                            "notes": notes if notes else None,
                            "is_favorite": is_favorite,
                            "tags": features.split(",") if features else []
                        }).execute()
                        
                        st.success(f"✅ Property added with ID: {result.data[0]['id']}")
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.error("Address and price are required")
    
    elif entry_choice == "api_usage":
        st.subheader("📊 Log API Usage")
        with st.form("add_api_usage"):
            user_id = st.number_input("User ID*", min_value=1, value=1)
            query = st.text_input("Query", placeholder="search properties in Seattle")
            query_type = st.selectbox("Query Type", [
                "property_search", "market_analysis", "comparable_properties", 
                "neighborhood_stats", "price_prediction"
            ])
            response_time = st.number_input("Response Time (ms)", min_value=0, value=150)
            success = st.checkbox("Success", value=True)
            error_msg = st.text_input("Error Message (if failed)")
            
            if st.form_submit_button("Log API Usage"):
                try:
                    result = supabase.table("api_usage").insert({
                        "user_id": user_id,
                        "query": query,
                        "query_type": query_type,
                        "response_time_ms": response_time,
                        "success": success,
                        "error_message": error_msg if error_msg else None,
                        "metadata": {"timestamp": datetime.utcnow().isoformat()}
                    }).execute()
                    st.success(f"✅ API usage logged with ID: {result.data[0]['id']}")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # Bulk data generation
    st.subheader("🎲 Generate Sample Data")
    if st.button("Generate 10 Sample Properties"):
        sample_properties = [
            {"address": "123 Oak St", "price": 450000, "bedrooms": 3, "bathrooms": 2, "type": "house"},
            {"address": "456 Pine Ave", "price": 325000, "bedrooms": 2, "bathrooms": 1, "type": "condo"},
            {"address": "789 Elm Dr", "price": 675000, "bedrooms": 4, "bathrooms": 3, "type": "house"},
            {"address": "321 Maple Ln", "price": 275000, "bedrooms": 2, "bathrooms": 2, "type": "townhouse"},
            {"address": "654 Cedar St", "price": 825000, "bedrooms": 5, "bathrooms": 4, "type": "house"},
            {"address": "987 Birch Rd", "price": 395000, "bedrooms": 3, "bathrooms": 2, "type": "condo"},
            {"address": "147 Spruce Ave", "price": 550000, "bedrooms": 3, "bathrooms": 3, "type": "house"},
            {"address": "258 Willow Dr", "price": 425000, "bedrooms": 3, "bathrooms": 2, "type": "townhouse"},
            {"address": "369 Aspen St", "price": 750000, "bedrooms": 4, "bathrooms": 3, "type": "house"},
            {"address": "741 Cherry Ln", "price": 300000, "bedrooms": 2, "bathrooms": 1, "type": "condo"}
        ]
        
        try:
            for i, prop in enumerate(sample_properties):
                property_hash = hashlib.md5(f"{prop['address']}_{prop['price']}".encode()).hexdigest()
                supabase.table("properties").insert({
                    "user_id": 1,  # Assuming user 1 exists
                    "property_hash": property_hash,
                    "data": prop,
                    "search_params": {"location": "Sample City", "max_price": prop["price"] + 50000}
                }).execute()
            
            st.success("✅ Generated 10 sample properties!")
        except Exception as e:
            st.error(f"Error generating sample data: {e}")

# ------------------------
# Tab 4: Analytics
# ------------------------
with tab4:
    st.subheader("📈 Real Estate Portal Analytics")
    
    # Quick metrics
    try:
        users_count = supabase.table("users").select("id", count="exact").execute()
        properties_count = supabase.table("properties").select("id", count="exact").execute()
        api_calls_count = supabase.table("api_usage").select("id", count="exact").execute()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Users", users_count.count if users_count.count else 0)
        with col2:
            st.metric("Total Properties", properties_count.count if properties_count.count else 0)
        with col3:
            st.metric("API Calls", api_calls_count.count if api_calls_count.count else 0)
    except:
        st.info("Enable metrics by ensuring tables exist and have data")
    
    # Sample analytics queries to implement
    st.subheader("📊 Analytics Queries to Implement")
    analytics_examples = [
        "Properties by price range distribution",
        "User activity over time",
        "Most popular search locations",
        "API usage patterns by user role",
        "Average property prices by type",
        "User engagement metrics (favorites, notes, alerts)",
        "Market alert effectiveness",
        "Search to save conversion rates"
    ]
    
    for query in analytics_examples:
        st.write(f"• {query}")
    
    st.info("💡 Implement these analytics by creating corresponding SQL queries and visualizations using the query interface above.")

# ------------------------
# Cleanup & Delete
# ------------------------
with st.sidebar:
    st.subheader("🗑️ Data Management")
    
    if st.button("🧹 Clear All API Usage"):
        try:
            supabase.table("api_usage").delete().neq("id", 0).execute()
            st.success("API usage cleared")
        except Exception as e:
            st.error(f"Error: {e}")
    
    if st.button("🗑️ Delete Sample Properties"):
        try:
            supabase.table("properties").delete().eq("user_id", 1).execute()
            st.success("Sample properties deleted")
        except Exception as e:
            st.error(f"Error: {e}")

st.sidebar.markdown("---")
st.sidebar.caption("💡 Remember to set up RLS policies in production!")
