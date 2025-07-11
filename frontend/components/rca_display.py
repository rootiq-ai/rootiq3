import streamlit as st
import requests
import pandas as pd
import json
from datetime import datetime
import re

API_BASE_URL = "http://localhost:8000"


def render_rca_display():
    """Render the RCA analysis page"""
    
    st.header("🔍 Root Cause Analysis")
    
    # Tabs for different RCA operations
    tab1, tab2, tab3, tab4 = st.tabs(["📋 View RCAs", "🔍 Generate RCA", "🔎 Search Incidents", "⚙️ Custom Analysis"])
    
    with tab1:
        render_existing_rcas()
    
    with tab2:
        render_generate_rca()
    
    with tab3:
        render_search_incidents()
    
    with tab4:
        render_custom_analysis()


def render_existing_rcas():
    """Render list of existing RCAs"""
    
    st.subheader("📋 Existing RCA Reports")
    
    # Get groups with completed RCAs
    groups = get_groups_with_rca()
    
    if groups:
        # Create selection interface
        col1, col2 = st.columns([2, 1])
        
        with col1:
            selected_group = st.selectbox(
                "Select Group for RCA",
                options=groups,
                format_func=lambda x: f"{x['name']} - {x['host_name']} ({x['created_at'][:10]})"
            )
        
        with col2:
            if st.button("🔄 Refresh RCA List"):
                st.cache_data.clear()
                st.rerun()
        
        if selected_group:
            render_rca_report(selected_group['id'])
    
    else:
        st.info("No RCA reports available. Generate some RCAs from the Groups page first.")
        
        # Quick link to create groups
        if st.button("🔄 Go to Groups Page"):
            st.switch_page("Groups")


def render_generate_rca():
    """Render RCA generation interface"""
    
    st.subheader("🔍 Generate New RCA")
    
    # Get available groups
    available_groups = get_available_groups_for_rca()
    
    if available_groups:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            selected_group = st.selectbox(
                "Select Group for RCA Generation",
                options=available_groups,
                format_func=lambda x: f"{x['name']} - {x['alert_count']} alerts ({x['rca_generated']})"
            )
        
        with col2:
            force_regenerate = st.checkbox("Force Regenerate", help="Regenerate even if RCA already exists")
        
        if selected_group:
            # Show group preview
            with st.expander("Group Preview", expanded=True):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.write(f"**Host:** {selected_group['host_name']}")
                    st.write(f"**Service:** {selected_group['service_name']}")
                
                with col2:
                    st.write(f"**Alert Count:** {selected_group['alert_count']}")
                    st.write(f"**RCA Status:** {selected_group['rca_generated']}")
                
                with col3:
                    if selected_group.get('severity_summary'):
                        st.write("**Severities:**")
                        for sev, count in selected_group['severity_summary'].items():
                            st.write(f"• {sev}: {count}")
            
            # Generation options
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Generate Full RCA", type="primary"):
                    generate_full_rca(selected_group['id'], force_regenerate)
            
            with col2:
                if st.button("⚡ Quick Analysis"):
                    generate_quick_analysis(selected_group['id'])
    
    else:
        st.info("No groups available for RCA generation.")


def render_search_incidents():
    """Render incident search interface"""
    
    st.subheader("🔎 Search Similar Incidents")
    
    # Search interface
    col1, col2 = st.columns([3, 1])
    
    with col1:
        search_query = st.text_input(
            "Search Query",
            placeholder="e.g., high cpu usage web server nginx",
            help="Enter keywords to search for similar incidents"
        )
    
    with col2:
        search_limit = st.number_input("Max Results", min_value=1, max_value=50, value=10)
    
    if st.button("🔍 Search Incidents") and search_query:
        search_similar_incidents(search_query, search_limit)
    
    # Predefined searches
    st.markdown("---")
    st.write("**Quick Searches:**")
    
    quick_searches = [
        "high cpu usage",
        "memory leak",
        "disk space low",
        "service down",
        "database connection",
        "network timeout"
    ]
    
    cols = st.columns(3)
    for i, query in enumerate(quick_searches):
        with cols[i % 3]:
            if st.button(f"🔍 {query}", key=f"quick_search_{i}"):
                search_similar_incidents(query, 5)


def render_custom_analysis():
    """Render custom analysis interface"""
    
    st.subheader("⚙️ Custom RCA Analysis")
    
    st.write("Generate RCA for custom alert data without saving to database.")
    
    # Input method selection
    input_method = st.radio(
        "Choose input method:",
        ["Manual Entry", "JSON Input", "CSV Upload"]
    )
    
    if input_method == "Manual Entry":
        render_manual_alert_entry()
    elif input_method == "JSON Input":
        render_json_alert_entry()
    elif input_method == "CSV Upload":
        render_csv_alert_upload()


def render_manual_alert_entry():
    """Render manual alert entry form"""
    
    st.write("**Add Custom Alerts:**")
    
    # Initialize session state for alerts
    if 'custom_alerts' not in st.session_state:
        st.session_state.custom_alerts = []
    
    # Add alert form
    with st.form("add_custom_alert"):
        col1, col2 = st.columns(2)
        
        with col1:
            host_name = st.text_input("Host Name *")
            service_name = st.text_input("Service Name *")
            alert_name = st.text_input("Alert Name *")
        
        with col2:
            severity = st.selectbox("Severity", ["critical", "high", "medium", "low", "info"])
            message = st.text_area("Alert Message *")
        
        if st.form_submit_button("➕ Add Alert"):
            if all([host_name, service_name, alert_name, message]):
                alert = {
                    "host_name": host_name,
                    "service_name": service_name,
                    "alert_name": alert_name,
                    "severity": severity,
                    "message": message,
                    "id": f"custom_{len(st.session_state.custom_alerts) + 1}"
                }
                st.session_state.custom_alerts.append(alert)
                st.success("✅ Alert added")
                st.rerun()
            else:
                st.error("Please fill in all required fields")
    
    # Show current alerts
    if st.session_state.custom_alerts:
        st.write(f"**Current Alerts ({len(st.session_state.custom_alerts)}):**")
        alerts_df = pd.DataFrame(st.session_state.custom_alerts)
        st.dataframe(alerts_df[['host_name', 'service_name', 'alert_name', 'severity']], use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔍 Generate Custom RCA"):
                generate_custom_rca(st.session_state.custom_alerts)
        
        with col2:
            if st.button("🗑️ Clear Alerts"):
                st.session_state.custom_alerts = []
                st.rerun()


def render_json_alert_entry():
    """Render JSON alert entry"""
    
    st.write("**Enter Alert Data as JSON:**")
    
    json_example = [
        {
            "host_name": "web-server-01",
            "service_name": "nginx",
            "alert_name": "HighCPUUsage",
            "severity": "high",
            "message": "CPU usage above 90%",
            "details": {"cpu_percent": 95.2}
        }
    ]
    
    json_input = st.text_area(
        "Alert JSON Data",
        value=json.dumps(json_example, indent=2),
        height=300,
        help="Enter a JSON array of alert objects"
    )
    
    if st.button("🔍 Generate RCA from JSON"):
        try:
            alerts_data = json.loads(json_input)
            if isinstance(alerts_data, list) and alerts_data:
                generate_custom_rca(alerts_data)
            else:
                st.error("Please provide a valid JSON array of alerts")
        except json.JSONDecodeError as e:
            st.error(f"Invalid JSON format: {str(e)}")


def render_csv_alert_upload():
    """Render CSV alert upload"""
    
    st.write("**Upload Alert Data from CSV:**")
    
    uploaded_file = st.file_uploader(
        "Choose CSV file",
        type="csv",
        help="CSV should have columns: host_name, service_name, alert_name, severity, message"
    )
    
    if uploaded_file:
        try:
            df = pd.read_csv(uploaded_file)
            st.write("**Preview of uploaded data:**")
            st.dataframe(df.head(), use_container_width=True)
            
            if st.button("🔍 Generate RCA from CSV"):
                alerts_data = df.to_dict('records')
                generate_custom_rca(alerts_data)
        
        except Exception as e:
            st.error(f"Error processing CSV file: {str(e)}")


def render_rca_report(group_id):
    """Render a specific RCA report"""
    
    with st.spinner("Loading RCA report..."):
        rca_data = get_rca_report(group_id)
    
    if rca_data:
        # Header with group info
        st.subheader(f"RCA Report - {rca_data.get('incident_summary', {}).get('host', 'Unknown')} / {rca_data.get('incident_summary', {}).get('service', 'Unknown')}")
        
        # Report metadata
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Alerts Analyzed", len(rca_data.get('alerts_analyzed', [])))
        
        with col2:
            st.metric("Similar Incidents", rca_data.get('similar_incidents_found', 0))
        
        with col3:
            generated_at = rca_data.get('generated_at', '')
            if generated_at:
                formatted_date = datetime.fromisoformat(generated_at.replace('Z', '+00:00')).strftime('%Y-%m-%d %H:%M')
                st.write(f"**Generated:** {formatted_date}")
        
        # Incident summary
        if rca_data.get('incident_summary'):
            summary = rca_data['incident_summary']
            
            with st.expander("📊 Incident Summary", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Host:** {summary.get('host', 'N/A')}")
                    st.write(f"**Service:** {summary.get('service', 'N/A')}")
                    st.write(f"**Alert Count:** {summary.get('alert_count', 0)}")
                
                with col2:
                    if summary.get('time_span'):
                        time_span = summary['time_span']
                        st.write(f"**Start Time:** {time_span.get('start', 'N/A')[:19]}")
                        st.write(f"**End Time:** {time_span.get('end', 'N/A')[:19]}")
                    
                    # Severity distribution
                    if summary.get('severity_distribution'):
                        st.write("**Severity Distribution:**")
                        for sev, count in summary['severity_distribution'].items():
                            st.write(f"• {sev}: {count}")
        
        # Similar incidents
        if rca_data.get('similar_incidents'):
            with st.expander("🔍 Similar Past Incidents"):
                for i, incident in enumerate(rca_data['similar_incidents']):
                    st.write(f"**Similar Incident {i+1}** (Similarity: {incident.get('similarity_score', 0):.2f})")
                    metadata = incident.get('metadata', {})
                    st.write(f"• Host: {metadata.get('host_name', 'N/A')}")
                    st.write(f"• Service: {metadata.get('service_name', 'N/A')}")
                    st.write(f"• Type: {metadata.get('type', 'N/A')}")
                    st.markdown("---")
        
        # Main RCA analysis
        rca_analysis = rca_data.get('rca_analysis', '')
        if rca_analysis:
            st.markdown("### 📝 Root Cause Analysis")
            
            # Format and display the RCA content
            formatted_rca = format_rca_content(rca_analysis)
            st.markdown(formatted_rca, unsafe_allow_html=True)
        
        # Analyzed alerts
        if rca_data.get('alerts_analyzed'):
            with st.expander("📋 Analyzed Alerts"):
                alerts_df = pd.DataFrame(rca_data['alerts_analyzed'])
                alerts_df['timestamp'] = pd.to_datetime(alerts_df['timestamp'])
                alerts_df = alerts_df.sort_values('timestamp')
                st.dataframe(alerts_df, use_container_width=True)
        
        # Actions
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("🔄 Regenerate RCA"):
                with st.spinner("Regenerating RCA..."):
                    regenerate_rca(group_id)
        
        with col2:
            if st.button("📥 Export Report"):
                export_rca_report(rca_data)
        
        with col3:
            if st.button("🔍 Find Similar"):
                # Search for similar incidents based on this group
                summary = rca_data.get('incident_summary', {})
                query = f"{summary.get('host', '')} {summary.get('service', '')}"
                search_similar_incidents(query, 10)
    
    else:
        st.error("Failed to load RCA report")


def format_rca_content(content):
    """Format RCA content for better display"""
    
    # Convert markdown-like formatting to HTML
    content = content.replace('**', '<strong>').replace('**', '</strong>')
    content = content.replace('*', '<em>').replace('*', '</em>')
    
    # Convert numbered lists
    content = re.sub(r'^(\d+)\.\s+(.+)$', r'<div style="margin: 10px 0;"><strong>\1.</strong> \2</div>', content, flags=re.MULTILINE)
    
    # Convert bullet points
    content = re.sub(r'^[-•]\s+(.+)$', r'<div style="margin: 5px 0 5px 20px;">• \1</div>', content, flags=re.MULTILINE)
    
    # Add line breaks for paragraphs
    content = content.replace('\n\n', '<br><br>')
    content = content.replace('\n', '<br>')
    
    return f'<div style="background-color: #f8f9fa; padding: 20px; border-radius: 5px; border-left: 4px solid #007bff; white-space: pre-wrap; line-height: 1.6;">{content}</div>'


# Action functions
def generate_full_rca(group_id, force_regenerate=False):
    """Generate full RCA for a group"""
    
    params = {"force_regenerate": force_regenerate} if force_regenerate else {}
    
    with st.spinner("Generating RCA... This may take a few minutes."):
        try:
            response = requests.get(f"{API_BASE_URL}/api/rca/{group_id}", params=params, timeout=120)
            
            if response.status_code == 200:
                st.success("✅ RCA generated successfully!")
                rca_data = response.json()
                render_rca_report(group_id)
            else:
                st.error(f"❌ Failed to generate RCA: {response.text}")
        
        except requests.Timeout:
            st.error("⏰ RCA generation timed out. It may still be processing in the background.")
        except Exception as e:
            st.error(f"❌ Error generating RCA: {str(e)}")


def generate_quick_analysis(group_id):
    """Generate quick analysis for a group"""
    
    with st.spinner("Generating quick analysis..."):
        try:
            response = requests.get(f"{API_BASE_URL}/api/rca/{group_id}/quick-analysis", timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                st.success("✅ Quick analysis generated!")
                
                with st.expander("⚡ Quick Analysis", expanded=True):
                    st.markdown(format_rca_content(result['analysis']))
            else:
                st.error(f"❌ Failed to generate quick analysis: {response.text}")
        
        except Exception as e:
            st.error(f"❌ Error generating quick analysis: {str(e)}")


def search_similar_incidents(query, limit):
    """Search for similar incidents"""
    
    with st.spinner(f"Searching for incidents similar to '{query}'..."):
        try:
            response = requests.post(
                f"{API_BASE_URL}/api/rca/search-incidents",
                params={"query": query, "limit": limit},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                incidents = result.get('incidents', [])
                
                st.success(f"✅ Found {len(incidents)} similar incidents")
                
                if incidents:
                    with st.expander("🔍 Search Results", expanded=True):
                        for i, incident in enumerate(incidents):
                            st.write(f"**Incident {i+1}** (Similarity: {incident.get('similarity_score', 0):.2f})")
                            
                            metadata = incident.get('metadata', {})
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.write(f"• **Type:** {metadata.get('type', 'N/A')}")
                                st.write(f"• **Host:** {metadata.get('host_name', 'N/A')}")
                                st.write(f"• **Service:** {metadata.get('service_name', 'N/A')}")
                            
                            with col2:
                                st.write(f"• **Severity:** {metadata.get('severity', 'N/A')}")
                                if metadata.get('timestamp'):
                                    st.write(f"• **Time:** {metadata['timestamp'][:19]}")
                            
                            st.write(f"**Content:** {incident.get('document', 'N/A')[:200]}...")
                            st.markdown("---")
                else:
                    st.info("No similar incidents found")
            
            else:
                st.error(f"❌ Search failed: {response.text}")
        
        except Exception as e:
            st.error(f"❌ Error searching incidents: {str(e)}")


def generate_custom_rca(alerts_data):
    """Generate RCA for custom alert data"""
    
    with st.spinner("Generating custom RCA..."):
        try:
            payload = {
                "alerts": alerts_data,
                "context": "Custom analysis requested via Streamlit interface"
            }
            
            response = requests.post(
                f"{API_BASE_URL}/api/rca/generate-custom",
                json=payload,
                timeout=120
            )
            
            if response.status_code == 200:
                st.success("✅ Custom RCA generated successfully!")
                rca_data = response.json()
                
                # Display the custom RCA
                st.markdown("### 📝 Custom RCA Analysis")
                
                # Show incident summary
                if rca_data.get('incident_summary'):
                    summary = rca_data['incident_summary']
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Alerts Analyzed", summary.get('alert_count', 0))
                    with col2:
                        st.metric("Unique Hosts", len(set(alert.get('host_name', '') for alert in alerts_data)))
                    with col3:
                        st.metric("Unique Services", len(set(alert.get('service_name', '') for alert in alerts_data)))
                
                # Show RCA content
                rca_analysis = rca_data.get('rca_analysis', '')
                if rca_analysis:
                    st.markdown(format_rca_content(rca_analysis))
                
                # Show analyzed alerts
                if rca_data.get('alerts_analyzed'):
                    with st.expander("📋 Analyzed Alerts"):
                        alerts_df = pd.DataFrame(rca_data['alerts_analyzed'])
                        st.dataframe(alerts_df, use_container_width=True)
            
            else:
                st.error(f"❌ Failed to generate custom RCA: {response.text}")
        
        except Exception as e:
            st.error(f"❌ Error generating custom RCA: {str(e)}")


def regenerate_rca(group_id):
    """Regenerate RCA for a group"""
    generate_full_rca(group_id, force_regenerate=True)


def export_rca_report(rca_data):
    """Export RCA report"""
    
    # Create text version of the report
    report_text = f"""
RCA REPORT
==========

Group ID: {rca_data.get('group_id', 'N/A')}
Generated: {rca_data.get('generated_at', 'N/A')}

INCIDENT SUMMARY
================
{json.dumps(rca_data.get('incident_summary', {}), indent=2)}

SIMILAR INCIDENTS FOUND: {rca_data.get('similar_incidents_found', 0)}

RCA ANALYSIS
============
{rca_data.get('rca_analysis', 'No analysis available')}

ALERTS ANALYZED
===============
{json.dumps(rca_data.get('alerts_analyzed', []), indent=2)}
"""
    
    st.download_button(
        label="📥 Download Report",
        data=report_text,
        file_name=f"rca_report_{rca_data.get('group_id', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        mime="text/plain"
    )


# API interaction functions
@st.cache_data(ttl=60)
def get_groups_with_rca():
    """Get groups that have completed RCAs"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/groups?limit=1000", timeout=10)
        if response.status_code == 200:
            groups = response.json()["groups"]
            return [g for g in groups if g.get('rca_generated') == 'completed']
    except Exception as e:
        st.error(f"Error fetching groups with RCA: {str(e)}")
    return []


@st.cache_data(ttl=30)
def get_available_groups_for_rca():
    """Get groups available for RCA generation"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/groups?limit=1000", timeout=10)
        if response.status_code == 200:
            groups = response.json()["groups"]
            return [g for g in groups if g.get('alert_count', 0) > 0]
    except Exception as e:
        st.error(f"Error fetching available groups: {str(e)}")
    return []


def get_rca_report(group_id):
    """Get RCA report for a specific group"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/rca/{group_id}", timeout=60)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error fetching RCA report: {str(e)}")
    return None
