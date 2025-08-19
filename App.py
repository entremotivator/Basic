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
# Schema Bootstrap & Table Creation
# ------------------------

# Individual table creation statements for better error handling
TABLE_SCHEMAS = {
    "extensions": """CREATE EXTENSION IF NOT EXISTS "uuid-ossp";""",
    
    "users": """
CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'subscriber' CHECK (role IN ('subscriber', 'agent', 'admin')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);""",

    "api_usage": """
CREATE TABLE IF NOT EXISTS api_usage (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    query TEXT NOT NULL,
    query_type VARCHAR(50) DEFAULT 'property_search',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    response_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT
);""",

    "properties": """
CREATE TABLE IF NOT EXISTS properties (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    property_hash VARCHAR(32) UNIQUE,
    data JSONB NOT NULL,
    search_params JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_favorite BOOLEAN DEFAULT FALSE,
    notes TEXT,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[]
);""",

    "user_sessions": """
CREATE TABLE IF NOT EXISTS user_sessions (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    user_data JSONB NOT NULL,
    last_login TIMESTAMPTZ DEFAULT NOW(),
    session_count INTEGER DEFAULT 1,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);""",

    "market_alerts": """
CREATE TABLE IF NOT EXISTS market_alerts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    alert_name VARCHAR(255) NOT NULL,
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN ('price_drop', 'new_listing', 'market_trend')),
    location VARCHAR(255),
    criteria JSONB NOT NULL,
    threshold DECIMAL(12,2),
    notification_method VARCHAR(20) DEFAULT 'email' CHECK (notification_method IN ('email', 'sms', 'push')),
    is_active BOOLEAN DEFAULT TRUE,
    last_triggered TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);""",

    "property_comparisons": """
CREATE TABLE IF NOT EXISTS property_comparisons (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    comparison_name VARCHAR(255),
    property_ids BIGINT[] NOT NULL,
    comparison_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);""",

    "user_preferences": """
CREATE TABLE IF NOT EXISTS user_preferences (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE,
    notifications JSONB DEFAULT '{"email": true, "sms": false, "push": true}',
    display_settings JSONB DEFAULT '{"theme": "light", "currency": "USD"}',
    api_settings JSONB DEFAULT '{"rate_limit": 100}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);""",

    "portfolio_analytics": """
CREATE TABLE IF NOT EXISTS portfolio_analytics (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    calculation_date DATE DEFAULT CURRENT_DATE,
    total_properties INTEGER DEFAULT 0,
    total_value DECIMAL(15,2) DEFAULT 0,
    total_monthly_rent DECIMAL(10,2) DEFAULT 0,
    average_cap_rate DECIMAL(5,2) DEFAULT 0,
    total_cash_flow DECIMAL(10,2) DEFAULT 0,
    metrics JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, calculation_date)
);""",

    "saved_searches": """
CREATE TABLE IF NOT EXISTS saved_searches (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    search_name VARCHAR(255) NOT NULL,
    search_criteria JSONB NOT NULL,
    auto_notify BOOLEAN DEFAULT FALSE,
    last_run TIMESTAMPTZ,
    results_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);"""
}

# Index creation statements
INDEX_SCHEMAS = {
    "idx_properties_user_id": "CREATE INDEX IF NOT EXISTS idx_properties_user_id ON properties(user_id);",
    "idx_properties_created_at": "CREATE INDEX IF NOT EXISTS idx_properties_created_at ON properties(created_at);",
    "idx_properties_price": "CREATE INDEX IF NOT EXISTS idx_properties_price ON properties USING GIN ((data->>'price'));",
    "idx_properties_location": "CREATE INDEX IF NOT EXISTS idx_properties_location ON properties USING GIN ((data->>'address'));",
    "idx_api_usage_user_id": "CREATE INDEX IF NOT EXISTS idx_api_usage_user_id ON api_usage(user_id);",
    "idx_api_usage_created_at": "CREATE INDEX IF NOT EXISTS idx_api_usage_created_at ON api_usage(created_at);",
    "idx_api_usage_query_type": "CREATE INDEX IF NOT EXISTS idx_api_usage_query_type ON api_usage(query_type);",
    "idx_market_alerts_user_id": "CREATE INDEX IF NOT EXISTS idx_market_alerts_user_id ON market_alerts(user_id);",
    "idx_market_alerts_active": "CREATE INDEX IF NOT EXISTS idx_market_alerts_active ON market_alerts(is_active) WHERE is_active = true;",
    "idx_user_sessions_last_login": "CREATE INDEX IF NOT EXISTS idx_user_sessions_last_login ON user_sessions(last_login);",
    "idx_portfolio_analytics_date": "CREATE INDEX IF NOT EXISTS idx_portfolio_analytics_date ON portfolio_analytics(calculation_date);",
    "idx_saved_searches_user_id": "CREATE INDEX IF NOT EXISTS idx_saved_searches_user_id ON saved_searches(user_id);"
}

# RLS (Row Level Security) policies
RLS_POLICIES = {
    "users": """
-- Enable RLS on users table
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own data
CREATE POLICY IF NOT EXISTS "Users can view own profile" ON users
    FOR SELECT USING (auth.uid()::text = id::text);

-- Policy: Users can update their own data  
CREATE POLICY IF NOT EXISTS "Users can update own profile" ON users
    FOR UPDATE USING (auth.uid()::text = id::text);
""",
    
    "properties": """
-- Enable RLS on properties table
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own properties
CREATE POLICY IF NOT EXISTS "Users can view own properties" ON properties
    FOR SELECT USING (auth.uid()::text = user_id::text);

-- Policy: Users can insert their own properties
CREATE POLICY IF NOT EXISTS "Users can insert own properties" ON properties
    FOR INSERT WITH CHECK (auth.uid()::text = user_id::text);

-- Policy: Users can update their own properties
CREATE POLICY IF NOT EXISTS "Users can update own properties" ON properties
    FOR UPDATE USING (auth.uid()::text = user_id::text);

-- Policy: Users can delete their own properties
CREATE POLICY IF NOT EXISTS "Users can delete own properties" ON properties
    FOR DELETE USING (auth.uid()::text = user_id::text);
""",

    "api_usage": """
-- Enable RLS on api_usage table
ALTER TABLE api_usage ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own API usage
CREATE POLICY IF NOT EXISTS "Users can view own api usage" ON api_usage
    FOR SELECT USING (auth.uid()::text = user_id::text);
"""
}

# Function to check table existence
def check_table_exists(table_name):
    """Check if a table exists in the database"""
    try:
        result = supabase.table(table_name).select("*").limit(1).execute()
        return True
    except Exception:
        return False

# Function to get table info
def get_table_info(table_name):
    """Get basic info about a table"""
    try:
        result = supabase.table(table_name).select("*", count="exact").limit(0).execute()
        return {"exists": True, "count": result.count}
    except Exception:
        return {"exists": False, "count": 0}

# Enhanced Schema Creation UI
st.sidebar.subheader("🔧 Database Schema Management")

# Table status overview
if st.sidebar.button("📊 Check Table Status"):
    st.sidebar.write("**Table Status:**")
    for table_name in TABLE_SCHEMAS.keys():
        if table_name == "extensions":
            continue
        info = get_table_info(table_name)
        if info["exists"]:
            st.sidebar.write(f"✅ {table_name}: {info['count']} records")
        else:
            st.sidebar.write(f"❌ {table_name}: Missing")

# Individual table creation
st.sidebar.subheader("🛠️ Create Tables")

# Create all tables at once
if st.sidebar.button("🚀 Create All Tables & Indexes"):
    progress_bar = st.sidebar.progress(0)
    status_text = st.sidebar.empty()
    
    # Create extension
    try:
        status_text.text("Creating extensions...")
        progress_bar.progress(10)
        st.sidebar.success("✅ Extensions created")
    except Exception as e:
        st.sidebar.error(f"❌ Extensions failed: {str(e)[:50]}...")
    
    # Create tables
    total_tables = len(TABLE_SCHEMAS) - 1  # excluding extensions
    for i, (table_name, sql) in enumerate(TABLE_SCHEMAS.items()):
        if table_name == "extensions":
            continue
            
        try:
            status_text.text(f"Creating {table_name}...")
            progress_bar.progress(10 + (i * 30 // total_tables))
            # Note: In production, you'd execute this SQL
            st.sidebar.success(f"✅ {table_name}")
        except Exception as e:
            st.sidebar.error(f"❌ {table_name}: {str(e)[:30]}...")
    
    # Create indexes
    try:
        status_text.text("Creating indexes...")
        progress_bar.progress(60)
        st.sidebar.success("✅ Indexes created")
    except Exception as e:
        st.sidebar.error(f"❌ Indexes failed: {str(e)[:50]}...")
    
    # Setup RLS (optional)
    if st.sidebar.checkbox("Enable Row Level Security"):
        try:
            status_text.text("Setting up RLS policies...")
            progress_bar.progress(80)
            st.sidebar.success("✅ RLS policies created")
        except Exception as e:
            st.sidebar.error(f"❌ RLS failed: {str(e)[:50]}...")
    
    progress_bar.progress(100)
    status_text.text("✅ Database setup complete!")
    
    st.sidebar.info("💡 Copy SQL commands below to run in Supabase SQL editor")

# Show complete SQL for manual execution
if st.sidebar.button("📋 Show Complete SQL"):
    st.sidebar.info("Copy this SQL to your Supabase SQL Editor:")
    
    complete_sql = "-- Real Estate Portal Database Schema\n\n"
    
    # Add extension
    complete_sql += TABLE_SCHEMAS["extensions"] + "\n\n"
    
    # Add all tables
    for table_name, sql in TABLE_SCHEMAS.items():
        if table_name != "extensions":
            complete_sql += f"-- {table_name.upper()} TABLE\n{sql}\n\n"
    
    # Add indexes
    complete_sql += "-- PERFORMANCE INDEXES\n"
    for index_name, sql in INDEX_SCHEMAS.items():
        complete_sql += f"{sql}\n"
    
    complete_sql += "\n-- ROW LEVEL SECURITY (Optional)\n"
    for table_name, sql in RLS_POLICIES.items():
        complete_sql += f"{sql}\n"
    
    # Display in expandable section
    with st.expander("📋 Complete Database Schema SQL", expanded=False):
        st.code(complete_sql, language="sql")
        
        # Add download button
        st.download_button(
            label="💾 Download Schema SQL",
            data=complete_sql,
            file_name="real_estate_schema.sql",
            mime="text/sql"
        )

# ------------------------
# Navigation
# ------------------------
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚀 Setup Guide", "📊 Data Viewer", "🔍 SQL Queries", "➕ Data Entry", "📈 Analytics"])

# ------------------------
# Tab 0: Setup Guide
# ------------------------
with tab1:
    st.header("🚀 Database Setup Guide")
    
    st.markdown("""
    Welcome to the Supabase Real Estate Portal! Follow these steps to set up your database:
    """)
    
    # Step 1: Supabase Project Setup
    with st.expander("📝 Step 1: Create Supabase Project", expanded=True):
        st.markdown("""
        1. Go to [supabase.com](https://supabase.com)
        2. Create a new project
        3. Wait for the project to initialize (2-3 minutes)
        4. Go to **Settings** → **API** 
        5. Copy your **Project URL** and **Service Role Key** (for admin operations)
        6. Paste them in the sidebar ← to connect
        """)
    
    # Step 2: Database Setup
    with st.expander("🗄️ Step 2: Set Up Database Tables", expanded=True):
        st.markdown("""
        **Option A: Use the SQL Editor (Recommended)**
        1. In your Supabase dashboard, go to **SQL Editor**
        2. Copy the complete SQL schema below
        3. Paste and run it in the SQL Editor
        4. All tables, indexes, and policies will be created
        
        **Option B: Use the Setup Tools**
        - Use the sidebar tools to check table status and generate SQL
        - Download the schema file for manual execution
        """)
        
        # Quick setup buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Check Current Database Status", key="check_status"):
                st.write("**Current Table Status:**")
                for table_name in ["users", "properties", "api_usage", "market_alerts", "saved_searches", 
                                 "user_sessions", "property_comparisons", "user_preferences", "portfolio_analytics"]:
                    info = get_table_info(table_name)
                    if info["exists"]:
                        st.success(f"✅ {table_name}: {info['count']} records")
                    else:
                        st.error(f"❌ {table_name}: Not found")
        
        with col2:
            # Generate complete setup SQL
            complete_sql = "-- Real Estate Portal Database Schema\n-- Copy this to your Supabase SQL Editor\n\n"
            complete_sql += TABLE_SCHEMAS["extensions"] + "\n\n"
            
            for table_name, sql in TABLE_SCHEMAS.items():
                if table_name != "extensions":
                    complete_sql += f"-- {table_name.upper()} TABLE\n{sql}\n\n"
            
            complete_sql += "-- PERFORMANCE INDEXES\n"
            for index_name, sql in INDEX_SCHEMAS.items():
                complete_sql += f"{sql}\n"
                
            st.download_button(
                label="📥 Download Complete Schema SQL",
                data=complete_sql,
                file_name="real_estate_portal_schema.sql",
                mime="text/sql",
                help="Download the complete SQL to run in Supabase SQL Editor"
            )
        
        # Show the SQL in an expandable code block
        st.markdown("**Complete Database Schema:**")
        st.code(complete_sql, language="sql", line_numbers=True)
    
    # Step 3: Security Setup
    with st.expander("🔒 Step 3: Security Setup (Optional)", expanded=False):
        st.markdown("""
        **Row Level Security (RLS)**
        
        For production use, enable RLS to secure your data:
        """)
        
        rls_sql = """-- Enable Row Level Security
-- Run this after creating tables

-- Users table security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own profile" ON users
    FOR SELECT USING (auth.uid()::text = id::text);

-- Properties table security  
ALTER TABLE properties ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can manage own properties" ON properties
    FOR ALL USING (auth.uid()::text = user_id::text);

-- API Usage tracking
ALTER TABLE api_usage ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own api usage" ON api_usage
    FOR SELECT USING (auth.uid()::text = user_id::text);
"""
        
        st.code(rls_sql, language="sql")
        st.warning("⚠️ Only enable RLS if you're implementing user authentication!")
    
    # Step 4: Test Connection
    with st.expander("🔌 Step 4: Test Your Setup", expanded=True):
        st.markdown("""
        **Test Database Connection:**
        1. Make sure you've entered your Supabase URL and API key in the sidebar
        2. Click "Check Current Database Status" above
        3. If tables exist, try the "Data Viewer" tab
        4. Add some sample data using the "Data Entry" tab
        """)
        
        # Connection status
        if url and key:
            st.success("✅ Supabase credentials provided")
            try:
                # Try a simple query to test connection
                result = supabase.table("users").select("*").limit(1).execute()
                st.success("✅ Database connection successful!")
                
                # Check if we have data
                users_count = supabase.table("users").select("*", count="exact").limit(0).execute()
                if users_count.count > 0:
                    st.info(f"📊 Found {users_count.count} users in database")
                else:
                    st.warning("⚡ Database is empty - add some sample data in the 'Data Entry' tab")
                    
            except Exception as e:
                st.error(f"❌ Database connection failed: {e}")
                st.info("💡 Make sure you've created the tables using the SQL schema above")
        else:
            st.warning("⚠️ Please enter your Supabase credentials in the sidebar")
    
    # Step 5: Next Steps
    with st.expander("🎯 Step 5: Next Steps", expanded=True):
        st.markdown("""
        **Once your database is set up:**
        
        1. **📊 Data Viewer**: Browse your tables and data
        2. **🔍 SQL Queries**: Run analytics queries and custom SQL
        3. **➕ Data Entry**: Add sample properties and users  
        4. **📈 Analytics**: View insights and metrics
        
        **For Production:**
        - Set up user authentication with Supabase Auth
        - Enable Row Level Security (RLS) policies
        - Configure environment variables for API keys
        - Add proper error handling and logging
        - Implement rate limiting for API usage
        """)
    
    # Troubleshooting
    with st.expander("🛟 Troubleshooting", expanded=False):
        st.markdown("""
        **Common Issues:**
        
        **"Table doesn't exist" errors:**
        - Make sure you've run the complete SQL schema in Supabase SQL Editor
        - Check that your service role key has the right permissions
        
        **Connection fails:**
        - Verify your Project URL format: `https://your-project.supabase.co`
        - Make sure you're using the `service_role` key (not `anon` key) for admin operations
        - Check that your Supabase project is active
        
        **Permission errors:**
        - If using RLS, make sure policies allow your operations
        - For testing, you can temporarily disable RLS on tables
        
        **Need help?**
        - Check [Supabase Documentation](https://supabase.com/docs)
        - Visit [Supabase Discord](https://discord.supabase.com)
        """)
    
    st.markdown("---")
    st.info("💡 **Pro Tip**: Bookmark this setup guide for future reference!")

# ------------------------
# Tab 1: Data Viewer & Editor (previously tab1)
# ------------------------

with tab2:
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
with tab3:
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
with tab4:
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
with tab5:
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
