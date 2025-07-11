import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import time
from streamlit_autorefresh import st_autorefresh

# Import components
from components.alerts_dashboard import render_alerts_dashboard
from components.groups_view import render_groups_view
from components.rca_display import render_rca_display

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page configuration
st.set_page_config(
    page_title="Alert Monitoring MVP",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .alert-critical {
        background-color: #ffebee;
        border-left: 4px solid #f44336;
    }
    .alert-high {
        background-color: #fff3e0;
        border-left: 4px solid #ff9800;
    }
    .alert-medium {
        background-color: #f3e5f5;
        border-left: 4px solid #9c27b0;
    }
    .alert-low {
        background-color: #e8f5e8;
        border-left: 4px solid #4caf50;
    }
    .rca-content {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border: 1px solid #dee2e6;
        white-space: pre-wrap;
    }
</style>
""", unsafe_allow_html=True)

def main():
    """Main application function"""
    
    # Header
    st.markdown('<h1 class="main-header">🚨 Alert Monitoring MVP</h1>', unsafe_allow_html=True)
    
    # Auto-refresh every 30 seconds
    count = st_autorefresh(interval=30000, limit=100, key="main_refresh")
    
    # Sidebar navigation
    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox(
        "Choose a page",
        ["Dashboard", "Alerts", "Groups", "RCA Analysis", "System Health"]
    )
    
    # API status check
    check_api_status()
    
    # Route to appropriate page
    if page == "Dashboard":
        render_dashboard()
    elif page == "Alerts":
        render_alerts_dashboard()
    elif page == "Groups":
        render_groups_view()
    elif page == "RCA Analysis":
        render_rca_display()
    elif page == "System Health":
        render_system_health()


def check_api_status():
    """Check if the backend API is accessible"""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            st.sidebar.success("🟢 API Connected")
        else:
            st.sidebar.error("🔴 API Error")
    except requests.RequestException:
        st.sidebar.error("🔴 API Unavailable")
        st.sidebar.info("Make sure the FastAPI backend is running on port 8000")


def render_dashboard():
    """Render the main dashboard"""
    st.header("📊 Dashboard Overview")
    
    # Fetch data
    alerts_stats = get_alert_statistics()
    groups_stats = get_group_statistics()
    kb_stats = get_knowledge_base_stats()
    
    if alerts_stats and groups_stats:
        # Key metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(
                f'<div class="metric-card"><h3>{alerts_stats.get("total_alerts", 0)}</h3><p>Total Alerts</p></div>',
                unsafe_allow_html=True
            )
        
        with col2:
            st.markdown(
                f'<div class="metric-card"><h3>{groups_stats.get("total_groups", 0)}</h3><p>Alert Groups</p></div>',
                unsafe_allow_html=True
            )
        
        with col3:
            rca_completed = groups_stats.get("rca_status_distribution", {}).get("completed", 0)
            st.markdown(
                f'<div class="metric-card"><h3>{rca_completed}</h3><p>RCAs Generated</p></div>',
                unsafe_allow_html=True
            )
        
        with col4:
            kb_docs = kb_stats.get("total_documents", 0) if kb_stats else 0
            st.markdown(
                f'<div class="metric-card"><h3>{kb_docs}</h3><p>KB Documents</p></div>',
                unsafe_allow_html=True
            )
        
        st.markdown("---")
        
        # Charts
        col1, col2 = st.columns(2)
        
        with col1:
            # Severity distribution
            severity_data = alerts_stats.get("severity_distribution", {})
            if severity_data:
                fig = px.pie(
                    values=list(severity_data.values()),
                    names=list(severity_data.keys()),
                    title="Alert Severity Distribution",
                    color_discrete_map={
                        'critical': '#f44336',
                        'high': '#ff9800',
                        'medium': '#9c27b0',
                        'low': '#4caf50',
                        'info': '#2196f3'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Top hosts
            top_hosts = alerts_stats.get("top_hosts", {})
            if top_hosts:
                fig = px.bar(
                    x=list(top_hosts.values()),
                    y=list(top_hosts.keys()),
                    orientation='h',
                    title="Top 10 Hosts by Alert Count",
                    labels={'x': 'Alert Count', 'y': 'Host'}
                )
                fig.update_layout(yaxis={'categoryorder': 'total ascending'})
                st.plotly_chart(fig, use_container_width=True)
        
        # Recent alerts summary
        st.subheader("📈 Recent Activity")
        recent_alerts = get_recent_alerts(limit=10)
        if recent_alerts:
            df = pd.DataFrame(recent_alerts)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp', ascending=False)
            
            # Display as table
            st.dataframe(
                df[['host_name', 'service_name', 'alert_name', 'severity', 'timestamp']],
                use_container_width=True
            )
    
    else:
        st.error("Unable to fetch dashboard data. Please check the API connection.")


def render_system_health():
    """Render system health page"""
    st.header("🔧 System Health")
    
    # API Health
    st.subheader("API Health")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            st.success("✅ Backend API is healthy")
        else:
            st.error(f"❌ API returned status code: {response.status_code}")
    except Exception as e:
        st.error(f"❌ API connection failed: {str(e)}")
    
    # Knowledge Base Stats
    st.subheader("Knowledge Base")
    kb_stats = get_knowledge_base_stats()
    if kb_stats:
        if "error" in kb_stats:
            st.error(f"❌ Knowledge base error: {kb_stats['error']}")
        else:
            st.success(f"✅ Knowledge base: {kb_stats.get('total_documents', 0)} documents")
            
            # Rebuild knowledge base button
            if st.button("🔄 Rebuild Knowledge Base"):
                with st.spinner("Rebuilding knowledge base..."):
                    try:
                        response = requests.post(f"{API_BASE_URL}/api/rca/knowledge-base/rebuild", timeout=60)
                        if response.status_code == 200:
                            result = response.json()
                            st.success(f"✅ Knowledge base rebuilt: {result['total_documents']} documents")
                        else:
                            st.error("❌ Failed to rebuild knowledge base")
                    except Exception as e:
                        st.error(f"❌ Error rebuilding knowledge base: {str(e)}")
    
    # Database Health
    st.subheader("Database")
    alerts_stats = get_alert_statistics()
    groups_stats = get_group_statistics()
    
    if alerts_stats and groups_stats:
        st.success("✅ Database connection is healthy")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Alerts", alerts_stats.get("total_alerts", 0))
        with col2:
            st.metric("Total Groups", groups_stats.get("total_groups", 0))
    else:
        st.error("❌ Database connection issues")
    
    # System Actions
    st.subheader("System Actions")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Create Groups from Alerts"):
            with st.spinner("Creating groups..."):
                try:
                    response = requests.post(f"{API_BASE_URL}/api/groups/create", timeout=30)
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Created {result['total_created']} groups")
                    else:
                        st.error("❌ Failed to create groups")
                except Exception as e:
                    st.error(f"❌ Error creating groups: {str(e)}")
    
    with col2:
        if st.button("📊 Refresh Statistics"):
            st.rerun()
    
    with col3:
        if st.button("🧹 Clear Cache"):
            st.cache_data.clear()
            st.success("✅ Cache cleared")


# Utility functions
@st.cache_data(ttl=30)
def get_alert_statistics():
    """Get alert statistics from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/alerts/stats/summary", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching alert statistics: {str(e)}")
    return None


@st.cache_data(ttl=30)
def get_group_statistics():
    """Get group statistics from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/groups/stats/summary", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching group statistics: {str(e)}")
    return None


@st.cache_data(ttl=30)
def get_knowledge_base_stats():
    """Get knowledge base statistics from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/rca/knowledge-base/stats", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching knowledge base statistics: {str(e)}")
    return None


@st.cache_data(ttl=30)
def get_recent_alerts(limit=20):
    """Get recent alerts from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/alerts?limit={limit}", timeout=10)
        if response.status_code == 200:
            return response.json()["alerts"]
    except Exception as e:
        st.error(f"Error fetching recent alerts: {str(e)}")
    return None


if __name__ == "__main__":
    main()
