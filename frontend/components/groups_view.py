import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import json

API_BASE_URL = "http://localhost:8000"


def render_groups_view():
    """Render the alert groups management page"""
    
    st.header("👥 Alert Groups")
    
    # Tabs for different group operations
    tab1, tab2, tab3, tab4 = st.tabs(["📋 View Groups", "🔄 Create Groups", "📊 Group Analytics", "⚙️ Group Management"])
    
    with tab1:
        render_groups_list()
    
    with tab2:
        render_create_groups()
    
    with tab3:
        render_group_analytics()
    
    with tab4:
        render_group_management()


def render_groups_list():
    """Render the list of alert groups"""
    
    st.subheader("Current Alert Groups")
    
    # Filters and controls
    col1, col2, col3 = st.columns(3)
    
    with col1:
        status_filter = st.selectbox("Filter by Status", ["All", "active", "resolved", "deleted"])
    
    with col2:
        include_alerts = st.checkbox("Include Alert Details", value=False)
    
    with col3:
        limit = st.number_input("Limit Results", min_value=10, max_value=500, value=50)
    
    # Build query parameters
    params = {"limit": limit, "include_alerts": include_alerts}
    if status_filter != "All":
        params["status"] = status_filter
    
    # Fetch groups
    groups = get_groups(params)
    
    if groups:
        # Display summary metrics
        total_groups = len(groups)
        rca_completed = len([g for g in groups if g.get('rca_generated') == 'completed'])
        rca_pending = len([g for g in groups if g.get('rca_generated') == 'pending'])
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Groups", total_groups)
        with col2:
            st.metric("RCA Completed", rca_completed)
        with col3:
            st.metric("RCA Pending", rca_pending)
        with col4:
            avg_alerts = sum(g.get('alert_count', 0) for g in groups) / len(groups) if groups else 0
            st.metric("Avg Alerts/Group", f"{avg_alerts:.1f}")
        
        # Create DataFrame for display
        df = create_groups_dataframe(groups)
        
        # Color coding for RCA status
        def color_rca_status(val):
            colors = {
                'completed': 'background-color: #e8f5e8',
                'pending': 'background-color: #fff3e0',
                'generating': 'background-color: #e3f2fd',
                'failed': 'background-color: #ffebee'
            }
            return colors.get(val, '')
        
        # Display table with styling
        display_columns = ['name', 'host_name', 'service_name', 'alert_count', 'rca_generated', 'created_at']
        styled_df = df[display_columns].style.applymap(color_rca_status, subset=['rca_generated'])
        
        st.dataframe(styled_df, use_container_width=True, height=400)
        
        # Group details
        if st.checkbox("Show detailed group view"):
            selected_group_id = st.selectbox("Select Group for Details",
                                           options=df['id'].tolist(),
                                           format_func=lambda x: f"{df[df['id']==x]['name'].iloc[0]}")
            
            if selected_group_id:
                group_details = next(g for g in groups if g['id'] == selected_group_id)
                render_group_details(group_details)
    
    else:
        st.info("No alert groups found.")
    
    # Refresh button
    if st.button("🔄 Refresh Groups"):
        st.cache_data.clear()
        st.rerun()


def render_group_details(group):
    """Render detailed view of a single group"""
    
    with st.expander("Group Details", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Group Information:**")
            st.write(f"**ID:** {group['id']}")
            st.write(f"**Name:** {group['name']}")
            st.write(f"**Host:** {group['host_name']}")
            st.write(f"**Service:** {group['service_name']}")
            st.write(f"**Group Key:** {group['group_key']}")
            st.write(f"**Alert Count:** {group['alert_count']}")
            st.write(f"**Status:** {group['status']}")
        
        with col2:
            st.write("**RCA Information:**")
            st.write(f"**RCA Status:** {group['rca_generated']}")
            st.write(f"**Created:** {group['created_at']}")
            st.write(f"**Updated:** {group['updated_at']}")
        
        # Severity summary
        if group.get('severity_summary'):
            st.write("**Severity Distribution:**")
            severity_data = group['severity_summary']
            
            # Create pie chart for severity
            fig = px.pie(
                values=list(severity_data.values()),
                names=list(severity_data.keys()),
                title="Severity Distribution in Group",
                color_discrete_map={
                    'critical': '#f44336',
                    'high': '#ff9800',
                    'medium': '#9c27b0',
                    'low': '#4caf50',
                    'info': '#2196f3'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # Show alerts in group if available
        if group.get('alerts'):
            st.write(f"**Alerts in Group ({len(group['alerts'])}):**")
            alerts_df = pd.DataFrame(group['alerts'])
            alerts_df['timestamp'] = pd.to_datetime(alerts_df['timestamp'])
            alerts_df = alerts_df.sort_values('timestamp', ascending=False)
            
            st.dataframe(
                alerts_df[['alert_name', 'severity', 'message', 'timestamp']],
                use_container_width=True
            )
        
        # RCA Actions
        st.write("**Actions:**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button(f"🔍 View RCA", key=f"view_rca_{group['id']}"):
                # Switch to RCA tab with this group
                st.session_state.selected_group_for_rca = group['id']
                st.switch_page("RCA Analysis")
        
        with col2:
            if st.button(f"🔄 Generate RCA", key=f"gen_rca_{group['id']}"):
                generate_rca_for_group(group['id'])
        
        with col3:
            if st.button(f"🗑️ Delete Group", key=f"del_group_{group['id']}", type="secondary"):
                delete_group(group['id'])


def render_create_groups():
    """Render interface for creating groups from alerts"""
    
    st.subheader("🔄 Create Groups from Alerts")
    
    # Check ungrouped alerts
    ungrouped_alerts = get_ungrouped_alerts()
    
    if ungrouped_alerts:
        st.info(f"Found {len(ungrouped_alerts)} ungrouped alerts")
        
        # Preview of what groups would be created
        preview_groups = preview_group_creation(ungrouped_alerts)
        
        if preview_groups:
            st.write("**Groups that will be created:**")
            preview_df = pd.DataFrame([
                {
                    'host_name': host,
                    'service_name': service,
                    'alert_count': len(alerts),
                    'severities': ', '.join(set(alert['severity'] for alert in alerts))
                }
                for (host, service), alerts in preview_groups.items()
            ])
            
            st.dataframe(preview_df, use_container_width=True)
            
            # Create groups button
            if st.button("✅ Create Alert Groups", type="primary"):
                with st.spinner("Creating groups..."):
                    result = create_groups_from_alerts()
                    
                    if result:
                        st.success(f"✅ Successfully created {result.get('total_created', 0)} groups")
                        st.cache_data.clear()
                        st.rerun()
                    else:
                        st.error("❌ Failed to create groups")
        else:
            st.warning("No groups can be created from current ungrouped alerts")
    
    else:
        st.success("🎉 All alerts are already grouped!")
    
    # Manual group creation
    st.markdown("---")
    st.write("**Manual Group Creation**")
    
    with st.form("manual_group_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            group_name = st.text_input("Group Name *")
            host_name = st.text_input("Host Name *")
        
        with col2:
            service_name = st.text_input("Service Name *")
            
        submit_button = st.form_submit_button("➕ Create Manual Group")
        
        if submit_button:
            if not all([group_name, host_name, service_name]):
                st.error("Please fill in all required fields")
            else:
                # This would require implementing manual group creation in the API
                st.info("Manual group creation not yet implemented in API")


def render_group_analytics():
    """Render group analytics"""
    
    st.subheader("📊 Group Analytics")
    
    # Get groups for analysis
    groups = get_groups({"limit": 1000})
    
    if not groups:
        st.info("No groups available for analysis")
        return
    
    df = create_groups_dataframe(groups)
    
    # Analytics tabs
    analytics_tab1, analytics_tab2, analytics_tab3 = st.tabs(["📈 Distribution", "🔍 RCA Analysis", "⏱️ Timeline"])
    
    with analytics_tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            # Alert count distribution
            fig = px.histogram(df, x='alert_count', nbins=20,
                              title="Distribution of Alerts per Group",
                              labels={'x': 'Alert Count', 'y': 'Number of Groups'})
            st.plotly_chart(fig, use_container_width=True)
            
            # Host distribution
            host_counts = df['host_name'].value_counts().head(15)
            fig = px.bar(x=host_counts.values, y=host_counts.index, orientation='h',
                        title="Groups by Host (Top 15)",
                        labels={'x': 'Group Count', 'y': 'Host'})
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Service distribution
            service_counts = df['service_name'].value_counts().head(10)
            fig = px.pie(values=service_counts.values, names=service_counts.index,
                        title="Groups by Service (Top 10)")
            st.plotly_chart(fig, use_container_width=True)
            
            # RCA status distribution
            rca_counts = df['rca_generated'].value_counts()
            fig = px.bar(x=rca_counts.index, y=rca_counts.values,
                        title="RCA Status Distribution",
                        labels={'x': 'RCA Status', 'y': 'Group Count'},
                        color=rca_counts.index,
                        color_discrete_map={
                            'completed': '#4caf50',
                            'pending': '#ff9800',
                            'generating': '#2196f3',
                            'failed': '#f44336'
                        })
            st.plotly_chart(fig, use_container_width=True)
    
    with analytics_tab2:
        # RCA Analysis
        rca_completed_groups = df[df['rca_generated'] == 'completed']
        
        if len(rca_completed_groups) > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric("Groups with RCA", len(rca_completed_groups))
                st.metric("RCA Completion Rate", f"{len(rca_completed_groups)/len(df)*100:.1f}%")
            
            with col2:
                # Average time to RCA completion (if timestamps available)
                st.write("**RCA Completion by Service:**")
                rca_by_service = rca_completed_groups['service_name'].value_counts()
                fig = px.bar(x=rca_by_service.index, y=rca_by_service.values,
                           title="RCA Completions by Service")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No completed RCAs available for analysis")
    
    with analytics_tab3:
        # Timeline analysis
        df['created_date'] = pd.to_datetime(df['created_at']).dt.date
        timeline_data = df.groupby('created_date').size().reset_index(name='groups_created')
        
        if len(timeline_data) > 1:
            fig = px.line(timeline_data, x='created_date', y='groups_created',
                         title="Group Creation Timeline",
                         labels={'created_date': 'Date', 'groups_created': 'Groups Created'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Insufficient data for timeline analysis")


def render_group_management():
    """Render group management operations"""
    
    st.subheader("⚙️ Group Management")
    
    # Bulk operations
    st.write("**Bulk Operations**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Generate All RCAs"):
            groups = get_groups({"limit": 1000})
            pending_groups = [g for g in groups if g.get('rca_generated') == 'pending']
            
            if pending_groups:
                with st.spinner(f"Generating RCAs for {len(pending_groups)} groups..."):
                    success_count = 0
                    for group in pending_groups[:5]:  # Limit to 5 at a time
                        if generate_rca_for_group(group['id'], show_message=False):
                            success_count += 1
                    
                    st.success(f"✅ Started RCA generation for {success_count} groups")
            else:
                st.info("No groups with pending RCA status")
    
    with col2:
        if st.button("📊 Update Statistics"):
            st.cache_data.clear()
            st.success("✅ Statistics refreshed")
            st.rerun()
    
    with col3:
        if st.button("🧹 Cleanup Deleted"):
            # This would clean up groups marked as deleted
            st.info("Cleanup functionality not yet implemented")
    
    # Group health check
    st.markdown("---")
    st.write("**Group Health Check**")
    
    groups = get_groups({"limit": 1000})
    if groups:
        health_stats = analyze_group_health(groups)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Empty Groups", health_stats.get('empty_groups', 0))
        
        with col2:
            st.metric("Failed RCAs", health_stats.get('failed_rcas', 0))
        
        with col3:
            st.metric("Large Groups", health_stats.get('large_groups', 0))
        
        with col4:
            st.metric("Old Groups", health_stats.get('old_groups', 0))
        
        # Show problematic groups
        if health_stats.get('problem_groups'):
            st.write("**Groups Needing Attention:**")
            problem_df = pd.DataFrame(health_stats['problem_groups'])
            st.dataframe(problem_df, use_container_width=True)


# Utility functions
def create_groups_dataframe(groups):
    """Create pandas DataFrame from groups data"""
    df_data = []
    for group in groups:
        df_data.append({
            'id': group['id'],
            'name': group['name'],
            'host_name': group['host_name'],
            'service_name': group['service_name'],
            'group_key': group['group_key'],
            'alert_count': group['alert_count'],
            'rca_generated': group['rca_generated'],
            'created_at': group['created_at'],
            'updated_at': group['updated_at'],
            'status': group['status']
        })
    return pd.DataFrame(df_data)


def preview_group_creation(ungrouped_alerts):
    """Preview what groups would be created from ungrouped alerts"""
    from collections import defaultdict
    
    grouped = defaultdict(list)
    for alert in ungrouped_alerts:
        key = (alert['host_name'], alert['service_name'])
        grouped[key].append(alert)
    
    return dict(grouped)


def analyze_group_health(groups):
    """Analyze group health and identify issues"""
    health_stats = {
        'empty_groups': 0,
        'failed_rcas': 0,
        'large_groups': 0,
        'old_groups': 0,
        'problem_groups': []
    }
    
    for group in groups:
        issues = []
        
        # Check for empty groups
        if group.get('alert_count', 0) == 0:
            health_stats['empty_groups'] += 1
            issues.append('Empty group')
        
        # Check for failed RCAs
        if group.get('rca_generated') == 'failed':
            health_stats['failed_rcas'] += 1
            issues.append('Failed RCA')
        
        # Check for large groups (>50 alerts)
        if group.get('alert_count', 0) > 50:
            health_stats['large_groups'] += 1
            issues.append('Large group')
        
        # Check for old groups (>7 days)
        try:
            created_date = pd.to_datetime(group['created_at'])
            days_old = (pd.Timestamp.now() - created_date).days
            if days_old > 7:
                health_stats['old_groups'] += 1
                issues.append('Old group')
        except:
            pass
        
        if issues:
            health_stats['problem_groups'].append({
                'group_name': group['name'],
                'host_name': group['host_name'],
                'service_name': group['service_name'],
                'issues': ', '.join(issues)
            })
    
    return health_stats


# API interaction functions
@st.cache_data(ttl=30)
def get_groups(params=None):
    """Fetch groups from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/groups", params=params or {}, timeout=10)
        if response.status_code == 200:
            return response.json()["groups"]
    except Exception as e:
        st.error(f"Error fetching groups: {str(e)}")
    return None


@st.cache_data(ttl=60)
def get_ungrouped_alerts():
    """Fetch ungrouped alerts from API"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/alerts/ungrouped/list", timeout=10)
        if response.status_code == 200:
            return response.json()["ungrouped_alerts"]
    except Exception as e:
        st.error(f"Error fetching ungrouped alerts: {str(e)}")
    return None


def create_groups_from_alerts():
    """Create groups from alerts via API"""
    try:
        response = requests.post(f"{API_BASE_URL}/api/groups/create", timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"Error creating groups: {str(e)}")
    return None


def generate_rca_for_group(group_id, show_message=True):
    """Generate RCA for a specific group"""
    try:
        response = requests.post(f"{API_BASE_URL}/api/groups/{group_id}/generate-rca", timeout=30)
        if response.status_code == 200:
            if show_message:
                st.success("✅ RCA generation started")
            return True
        else:
            if show_message:
                st.error("❌ Failed to start RCA generation")
            return False
    except Exception as e:
        if show_message:
            st.error(f"Error generating RCA: {str(e)}")
        return False


def delete_group(group_id):
    """Delete a group via API"""
    try:
        response = requests.delete(f"{API_BASE_URL}/api/groups/{group_id}", timeout=10)
        if response.status_code == 200:
            st.success("✅ Group deleted successfully")
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("❌ Failed to delete group")
    except Exception as e:
        st.error(f"Error deleting group: {str(e)}")
