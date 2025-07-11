import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
import json

API_BASE_URL = "http://localhost:8000"


def render_alerts_dashboard():
    """Render the alerts dashboard page"""
    
    st.header("🚨 Alerts Management")
    
    # Tabs for different alert operations
    tab1, tab2, tab3, tab4 = st.tabs(["📋 View Alerts", "➕ Add Alert", "📊 Analytics", "⚙️ Bulk Operations"])
    
    with tab1:
        render_alerts_view()
    
    with tab2:
        render_add_alert_form()
    
    with tab3:
        render_alerts_analytics()
    
    with tab4:
        render_bulk_operations()


def render_alerts_view():
    """Render alerts viewing interface"""
    
    st.subheader("Current Alerts")
    
    # Filters
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        host_filter = st.text_input("Filter by Host", placeholder="e.g., web-server-01")
    
    with col2:
        service_filter = st.text_input("Filter by Service", placeholder="e.g., nginx")
    
    with col3:
        status_filter = st.selectbox("Status", ["All", "active", "resolved", "acknowledged"])
    
    with col4:
        limit = st.number_input("Limit Results", min_value=10, max_value=1000, value=100)
    
    # Build query parameters
    params = {"limit": limit}
    if host_filter:
        params["host_name"] = host_filter.lower()
    if service_filter:
        params["service_name"] = service_filter.lower()
    if status_filter != "All":
        params["status"] = status_filter
    
    # Fetch alerts
    alerts = get_alerts(params)
    
    if alerts:
        # Display summary
        total_alerts = len(alerts)
        critical_count = len([a for a in alerts if a['severity'] == 'critical'])
        high_count = len([a for a in alerts if a['severity'] == 'high'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Alerts", total_alerts)
        with col2:
            st.metric("Critical", critical_count, delta=f"{critical_count} critical")
        with col3:
            st.metric("High", high_count, delta=f"{high_count} high priority")
        
        # Create DataFrame
        df = pd.DataFrame(alerts)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp', ascending=False)
        
        # Color coding for severity
        def color_severity(val):
            colors = {
                'critical': 'background-color: #ffebee',
                'high': 'background-color: #fff3e0',
                'medium': 'background-color: #f3e5f5',
                'low': 'background-color: #e8f5e8',
                'info': 'background-color: #e3f2fd'
            }
            return colors.get(val, '')
        
        # Display table with styling
        styled_df = df[['host_name', 'service_name', 'alert_name', 'severity', 'status', 'message', 'timestamp']].style.applymap(
            color_severity, subset=['severity']
        )
        
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Alert details expander
        if st.checkbox("Show detailed view"):
            selected_alert_id = st.selectbox("Select Alert for Details", 
                                           options=df['id'].tolist(),
                                           format_func=lambda x: f"{df[df['id']==x]['alert_name'].iloc[0]} - {df[df['id']==x]['host_name'].iloc[0]}")
            
            if selected_alert_id:
                alert_details = df[df['id'] == selected_alert_id].iloc[0]
                render_alert_details(alert_details)
    
    else:
        st.info("No alerts found matching the criteria.")
    
    # Refresh button
    if st.button("🔄 Refresh Alerts"):
        st.cache_data.clear()
        st.rerun()


def render_alert_details(alert):
    """Render detailed view of a single alert"""
    
    with st.expander("Alert Details", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Alert Information:**")
            st.write(f"**ID:** {alert['id']}")
            st.write(f"**Name:** {alert['alert_name']}")
            st.write(f"**Host:** {alert['host_name']}")
            st.write(f"**Service:** {alert['service_name']}")
            st.write(f"**Severity:** {alert['severity']}")
            st.write(f"**Status:** {alert['status']}")
            st.write(f"**Monitoring System:** {alert['monitoring_system']}")
        
        with col2:
            st.write("**Timestamps:**")
            st.write(f"**Alert Time:** {alert['timestamp']}")
            st.write(f"**Created:** {alert['created_at']}")
            st.write(f"**Updated:** {alert['updated_at']}")
            if alert['group_id']:
                st.write(f"**Group ID:** {alert['group_id']}")
        
        st.write("**Message:**")
        st.code(alert['message'])
        
        if alert['details'] and alert['details'] != '{}':
            st.write("**Additional Details:**")
            try:
                if isinstance(alert['details'], str):
                    details = json.loads(alert['details'])
                else:
                    details = alert['details']
                st.json(details)
            except:
                st.code(str(alert['details']))


def render_add_alert_form():
    """Render form to add new alerts"""
    
    st.subheader("Add New Alert")
    
    with st.form("add_alert_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            monitoring_system = st.text_input("Monitoring System *", value="manual", help="Name of the monitoring system")
            host_name = st.text_input("Host Name *", help="Hostname where the alert originated")
            service_name = st.text_input("Service Name *", help="Service associated with the alert")
            alert_name = st.text_input("Alert Name *", help="Name/type of the alert")
        
        with col2:
            severity = st.selectbox("Severity *", ["critical", "high", "medium", "low", "info"])
            message = st.text_area("Alert Message *", help="Detailed alert message")
            
            # Optional timestamp
            use_current_time = st.checkbox("Use current timestamp", value=True)
            if not use_current_time:
                alert_timestamp = st.datetime_input("Alert Timestamp")
                alert_time = st.time_input("Alert Time")
        
        # Additional details
        st.write("**Additional Details (Optional):**")
        details_json = st.text_area("Details (JSON format)", placeholder='{"key": "value", "metric": 95.2}')
        
        submit_button = st.form_submit_button("➕ Add Alert")
        
        if submit_button:
            # Validate required fields
            if not all([monitoring_system, host_name, service_name, alert_name, message]):
                st.error("Please fill in all required fields marked with *")
                return
            
            # Prepare alert data
            alert_data = {
                "monitoring_system": monitoring_system,
                "host_name": host_name,
                "service_name": service_name,
                "alert_name": alert_name,
                "severity": severity,
                "message": message
            }
            
            # Add timestamp if not using current time
            if not use_current_time:
                alert_datetime = datetime.combine(alert_timestamp, alert_time)
                alert_data["timestamp"] = alert_datetime.isoformat()
            
            # Add details if provided
            if details_json.strip():
                try:
                    details = json.loads(details_json)
                    alert_data["details"] = details
                except json.JSONDecodeError:
                    st.error("Invalid JSON format in details field")
                    return
            
            # Submit alert
            success = create_alert(alert_data)
            if success:
                st.success("✅ Alert created successfully!")
                st.cache_data.clear()  # Clear cache to refresh data
                st.rerun()


def render_alerts_analytics():
    """Render alerts analytics"""
    
    st.subheader("📊 Alert Analytics")
    
    # Get alerts for analysis
    alerts = get_alerts({"limit": 1000})
    
    if not alerts:
        st.info("No alerts available for analysis")
        return
    
    df = pd.DataFrame(alerts)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.day_name()
    
    # Analytics tabs
    analytics_tab1, analytics_tab2, analytics_tab3 = st.tabs(["📈 Time Patterns", "🏠 Host Analysis", "⚙️ Service Analysis"])
    
    with analytics_tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Hourly distribution
            hourly_counts = df['hour'].value_counts().sort_index()
            fig = px.bar(x=hourly_counts.index, y=hourly_counts.values,
                        title="Alerts by Hour of Day",
                        labels={'x': 'Hour', 'y': 'Alert Count'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Day of week distribution
            day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            day_counts = df['day_of_week'].value_counts().reindex(day_order, fill_value=0)
            fig = px.bar(x=day_counts.index, y=day_counts.values,
                        title="Alerts by Day of Week",
                        labels={'x': 'Day', 'y': 'Alert Count'})
            st.plotly_chart(fig, use_container_width=True)
    
    with analytics_tab2:
        # Host analysis
        host_counts = df['host_name'].value_counts().head(20)
        host_severity = df.groupby(['host_name', 'severity']).size().unstack(fill_value=0)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(x=host_counts.values, y=host_counts.index, orientation='h',
                        title="Top 20 Hosts by Alert Count",
                        labels={'x': 'Alert Count', 'y': 'Host'})
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if len(host_severity) > 0:
                fig = px.bar(host_severity.head(10), 
                           title="Alert Severity by Host (Top 10)",
                           labels={'value': 'Alert Count', 'index': 'Host'})
                st.plotly_chart(fig, use_container_width=True)
    
    with analytics_tab3:
        # Service analysis
        service_counts = df['service_name'].value_counts().head(15)
        service_severity = df.groupby(['service_name', 'severity']).size().unstack(fill_value=0)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.pie(values=service_counts.values, names=service_counts.index,
                        title="Alert Distribution by Service")
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            if len(service_severity) > 0:
                fig = px.bar(service_severity.head(10),
                           title="Alert Severity by Service (Top 10)",
                           labels={'value': 'Alert Count', 'index': 'Service'})
                st.plotly_chart(fig, use_container_width=True)


def render_bulk_operations():
    """Render bulk operations interface"""
    
    st.subheader("⚙️ Bulk Operations")
    
    # Bulk alert creation
    st.write("**Bulk Alert Creation**")
    
    with st.expander("Upload CSV File"):
        uploaded_file = st.file_uploader("Choose CSV file", type="csv", 
                                       help="CSV should have columns: monitoring_system, host_name, service_name, alert_name, severity, message")
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("Preview of uploaded data:")
                st.dataframe(df.head())
                
                if st.button("🔄 Process Bulk Upload"):
                    with st.spinner("Processing alerts..."):
                        alerts_data = df.to_dict('records')
                        result = create_bulk_alerts(alerts_data)
                        
                        if result:
                            st.success(f"✅ Successfully created {result.get('successful_count', 0)} alerts")
                            if result.get('error_count', 0) > 0:
                                st.warning(f"⚠️ {result['error_count']} alerts failed to create")
                                with st.expander("View Errors"):
                                    st.json(result.get('errors', []))
                        else:
                            st.error("❌ Failed to process bulk upload")
            
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")
    
    # Sample data generation
    st.write("**Generate Sample Data**")
    col1, col2 = st.columns(2)
    
    with col1:
        sample_count = st.number_input("Number of sample alerts", min_value=1, max_value=100, value=10)
    
    with col2:
        if st.button("🎲 Generate Sample Alerts"):
            sample_alerts = generate_sample_alerts(sample_count)
            result = create_bulk_alerts(sample_alerts)
            
            if result:
                st.success(f"✅ Generated {result.get('successful_count', 0)} sample alerts")
            else:
                st.error("❌ Failed to generate sample alerts")


# API interaction functions
@st.cache_data(ttl=30)
def get_alerts(params=None):
    """Fetch alerts from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/alerts", params=params or {}, timeout=10)
        if response.status_code == 200:
            return response.json()["alerts"]
    except Exception as e:
        st.error(f"Error fetching alerts: {str(e)}")
    return None


def create_alert(alert_data):
    """Create a new alert via API"""
    try:
        response = requests.post(f"{API_BASE_URL}/api/alerts/ingest", json=alert_data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        st.error(f"Error creating alert: {str(e)}")
        return False


def create_bulk_alerts(alerts_data):
    """Create multiple alerts via API"""
    try:
        response = requests.post(f"{API_BASE_URL}/api/alerts/batch-ingest", json=alerts_data, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error creating bulk alerts: {str(e)}")
    return None


def generate_sample_alerts(count):
    """Generate sample alert data"""
    import random
    from datetime import datetime, timedelta
    
    hosts = ["web-server-01", "web-server-02", "db-server-01", "cache-server-01", "api-gateway-01"]
    services = ["nginx", "apache", "mysql", "redis", "nodejs", "python", "java"]
    alert_types = ["HighCPUUsage", "HighMemoryUsage", "DiskSpaceLow", "ServiceDown", "HighLatency", "ErrorRate"]
    severities = ["critical", "high", "medium", "low"]
    
    sample_alerts = []
    
    for i in range(count):
        alert = {
            "monitoring_system": "sample_generator",
            "host_name": random.choice(hosts),
            "service_name": random.choice(services),
            "alert_name": random.choice(alert_types),
            "severity": random.choice(severities),
            "message": f"Sample alert {i+1}: {random.choice(alert_types)} detected",
            "details": {
                "sample_id": i+1,
                "generated_at": datetime.utcnow().isoformat(),
                "metric_value": round(random.uniform(80, 99), 2)
            },
            "timestamp": (datetime.utcnow() - timedelta(minutes=random.randint(0, 1440))).isoformat()
        }
        sample_alerts.append(alert)
    
    return sample_alerts
