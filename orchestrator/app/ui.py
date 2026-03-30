"""
Streamlit UI for Macau Casino Marketing Assistant.

A conversational chatbot interface for creating marketing campaigns.
"""
import streamlit as st

from app.state import CAMPAIGN_THEMES, create_initial_state
from app.orchestrator import get_app, run_campaign_workflow, resume_after_approval
from app.settings import settings

# Page configuration
st.set_page_config(
    page_title="Grand Luxe Marketing Assistant",
    page_icon="🎰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for luxury feel
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #D4AF37;
        text-align: center;
        padding: 1rem 0;
        border-bottom: 2px solid #D4AF37;
        margin-bottom: 2rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #888;
        text-align: center;
        margin-bottom: 2rem;
    }
    .theme-card {
        border: 2px solid #333;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .theme-card:hover {
        border-color: #D4AF37;
        transform: translateY(-2px);
    }
    .theme-card.selected {
        border-color: #D4AF37;
        background-color: rgba(212, 175, 55, 0.1);
    }
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .status-generating { background-color: #FFA500; color: white; }
    .status-preview { background-color: #4CAF50; color: white; }
    .status-live { background-color: #2196F3; color: white; }
    .status-error { background-color: #f44336; color: white; }
    .preview-frame {
        border: 2px solid #D4AF37;
        border-radius: 10px;
        overflow: hidden;
        margin: 1rem 0;
    }
    .email-preview {
        background-color: #f5f5f5;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
    }
    .qr-code {
        text-align: center;
        padding: 1rem;
    }
</style>
""", unsafe_allow_html=True)


def initialize_session_state():
    """Initialize session state variables."""
    if "step" not in st.session_state:
        st.session_state.step = "welcome"
    if "campaign_data" not in st.session_state:
        st.session_state.campaign_data = {}
    if "workflow_state" not in st.session_state:
        st.session_state.workflow_state = None
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = None
    if "messages" not in st.session_state:
        st.session_state.messages = []


def add_message(role: str, content: str):
    """Add a message to the chat history."""
    st.session_state.messages.append({"role": role, "content": content})


def render_sidebar():
    """Render the sidebar with status and settings."""
    with st.sidebar:
        st.markdown("""
        <div style="text-align: center; padding: 1rem 0;">
            <h2 style="color: #D4AF37; margin: 0;">🎰 Grand Luxe</h2>
            <p style="color: #888; font-size: 0.8rem; margin: 0;">Marketing Assistant</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("---")
        
        # Current status
        st.markdown("### 📊 Campaign Status")
        
        step = st.session_state.step
        if step == "welcome":
            st.info("Ready to create a new campaign")
        elif step == "gathering":
            st.warning("Gathering campaign details...")
        elif step == "generating":
            st.warning("🔄 Generating campaign...")
        elif step == "preview":
            st.success("✅ Preview ready for review")
        elif step == "live":
            st.success("🚀 Campaign is LIVE!")
        elif step == "error":
            st.error("❌ Error occurred")
        
        st.markdown("---")
        
        # Quick actions
        st.markdown("### ⚡ Quick Actions")
        if st.button("🔄 Start New Campaign", use_container_width=True):
            st.session_state.step = "welcome"
            st.session_state.campaign_data = {}
            st.session_state.workflow_state = None
            st.session_state.thread_id = None
            st.session_state.messages = []
            st.rerun()
        
        st.markdown("---")
        
        # Debug info (collapsible)
        with st.expander("🔧 Debug Info"):
            st.write(f"Step: {st.session_state.step}")
            st.write(f"Thread ID: {st.session_state.thread_id}")
            if st.session_state.workflow_state:
                st.write(f"Current Step: {st.session_state.workflow_state.get('current_step', 'N/A')}")


def render_welcome():
    """Render the welcome screen."""
    st.markdown('<h1 class="main-header">🎰 Grand Luxe Marketing Assistant</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Create stunning marketing campaigns for your VIP customers in minutes</p>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        ### What would you like to do today?
        
        I can help you:
        - 📝 Create a new marketing campaign
        - 🎨 Design beautiful landing pages
        - 📧 Generate personalized emails
        - 🚀 Deploy campaigns instantly
        """)
        
        if st.button("✨ Create New Campaign", type="primary", use_container_width=True):
            st.session_state.step = "campaign_details"
            add_message("assistant", "Great! Let's create a new marketing campaign. Please provide the campaign details.")
            st.rerun()


def render_campaign_details():
    """Render the campaign details form."""
    from datetime import datetime, timedelta
    
    st.markdown("## 📝 Campaign Details")
    
    with st.form("campaign_form"):
        campaign_name = st.text_input(
            "Campaign Name",
            placeholder="e.g., Chinese New Year VIP Bonus",
            help="A catchy name for your campaign"
        )
        
        campaign_description = st.text_area(
            "Campaign Description",
            placeholder="Describe your campaign offer, benefits, and any special conditions...",
            height=100,
            help="Detailed description of what you're offering"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            hotel_name = st.text_input(
                "Hotel/Casino Name",
                value="Grand Luxe Hotel & Casino",
                help="Your property name"
            )
        with col2:
            target_audience = st.selectbox(
                "Target Audience",
                ["VIP platinum members", "VIP gold members", "VIP diamond members", "All VIP members", "New members"],
                help="Who should receive this campaign?"
            )
        
        st.markdown("### 📅 Campaign Dates")
        date_col1, date_col2 = st.columns(2)
        with date_col1:
            start_date = st.date_input(
                "Start Date",
                value=datetime.now().date(),
                min_value=datetime.now().date(),
                help="When does the campaign start?"
            )
        with date_col2:
            end_date = st.date_input(
                "End Date",
                value=(datetime.now() + timedelta(days=30)).date(),
                min_value=datetime.now().date(),
                help="When does the campaign end?"
            )
        
        submitted = st.form_submit_button("Continue to Theme Selection →", type="primary", use_container_width=True)
        
        if submitted:
            if not campaign_name or not campaign_description:
                st.error("Please fill in all required fields")
            elif end_date < start_date:
                st.error("End date must be after start date")
            else:
                st.session_state.campaign_data = {
                    "campaign_name": campaign_name,
                    "campaign_description": campaign_description,
                    "hotel_name": hotel_name,
                    "target_audience": target_audience,
                    "start_date": start_date.strftime("%B %d, %Y"),
                    "end_date": end_date.strftime("%B %d, %Y")
                }
                st.session_state.step = "theme_selection"
                add_message("user", f"Create a campaign called '{campaign_name}' for {target_audience}")
                add_message("assistant", "Great details! Now let's choose a theme for your campaign.")
                st.rerun()


def render_theme_selection():
    """Render the theme selection screen."""
    st.markdown("## 🎨 Select Campaign Theme")
    
    cols = st.columns(2)
    
    for i, (theme_key, theme_data) in enumerate(CAMPAIGN_THEMES.items()):
        with cols[i % 2]:
            colors = theme_data["colors"]
            
            # Create a color preview
            color_preview = f"""
            <div style="display: flex; gap: 5px; margin-bottom: 10px;">
                <div style="width: 30px; height: 30px; background-color: {colors['primary']}; border-radius: 5px;"></div>
                <div style="width: 30px; height: 30px; background-color: {colors['secondary']}; border-radius: 5px;"></div>
                <div style="width: 30px; height: 30px; background-color: {colors['accent']}; border-radius: 5px; border: 1px solid #ccc;"></div>
            </div>
            """
            
            with st.container():
                st.markdown(f"### {theme_data['name']}")
                st.markdown(color_preview, unsafe_allow_html=True)
                st.caption(theme_data["description"])
                
                if st.button(f"Select {theme_data['name']}", key=f"theme_{theme_key}", use_container_width=True):
                    st.session_state.campaign_data["selected_theme"] = theme_key
                    st.session_state.step = "generating"
                    add_message("user", f"I'll use the {theme_data['name']} theme")
                    add_message("assistant", "Excellent choice! I'm now generating your campaign. This may take a moment...")
                    st.rerun()


def render_generating():
    """Render the generating screen and run the workflow."""
    st.markdown("## 🔄 Generating Your Campaign")
    
    with st.spinner("Creating your marketing masterpiece..."):
        progress = st.progress(0)
        status = st.empty()
        
        try:
            # Run the workflow
            status.text("Step 1/4: Generating campaign page...")
            progress.progress(25)
            
            result, thread_id = run_campaign_workflow(
                campaign_name=st.session_state.campaign_data["campaign_name"],
                campaign_description=st.session_state.campaign_data["campaign_description"],
                hotel_name=st.session_state.campaign_data["hotel_name"],
                target_audience=st.session_state.campaign_data["target_audience"],
                selected_theme=st.session_state.campaign_data["selected_theme"],
                start_date=st.session_state.campaign_data.get("start_date", ""),
                end_date=st.session_state.campaign_data.get("end_date", "")
            )
            
            progress.progress(100)
            
            st.session_state.workflow_state = result
            st.session_state.thread_id = thread_id
            
            if result.get("error_message"):
                st.session_state.step = "error"
                add_message("assistant", f"I encountered an error: {result['error_message']}")
            elif result.get("awaiting_approval"):
                st.session_state.step = "preview"
                add_message("assistant", f"Your campaign preview is ready! Check it out at: {result.get('preview_url', 'N/A')}")
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.session_state.step = "error"
            add_message("assistant", f"Sorry, I encountered an error: {str(e)}")


def render_preview():
    """Render the preview screen with approval options."""
    st.markdown("## 👀 Campaign Preview")
    
    state = st.session_state.workflow_state
    
    if not state:
        st.error("No preview available")
        return
    
    # Preview URL and QR code
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🔗 Preview Link")
        preview_url = state.get("preview_url", "")
        if preview_url:
            st.code(preview_url)
            st.link_button("🔗 Open Preview in New Tab", preview_url, use_container_width=True)
            
            st.markdown("### 📱 Preview")
            st.info("Click the button above to view the generated campaign page in a new tab.")
    
    with col2:
        st.markdown("### 📱 QR Code")
        qr_code = state.get("preview_qr_code", "")
        if qr_code:
            st.image(qr_code, width=200)
            st.caption("Scan to view on mobile")
    
    st.markdown("---")
    
    # Approval buttons
    st.markdown("### What would you like to do?")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🎨 Change Theme", use_container_width=True):
            st.session_state.step = "theme_selection"
            add_message("user", "I want to change the theme")
            add_message("assistant", "No problem! Let's pick a different theme.")
            st.rerun()
    
    with col2:
        if st.button("✏️ Edit Details", use_container_width=True):
            st.session_state.step = "campaign_details"
            add_message("user", "I want to edit the campaign details")
            add_message("assistant", "Sure! Let's update the campaign details.")
            st.rerun()
    
    with col3:
        if st.button("🚀 Go Live!", type="primary", use_container_width=True):
            st.session_state.step = "deploying"
            add_message("user", "Let's go live!")
            add_message("assistant", "Deploying to production and preparing emails...")
            st.rerun()


def render_deploying():
    """Deploy to production and generate emails."""
    st.markdown("## 🚀 Going Live!")
    
    with st.spinner("Deploying to production..."):
        progress = st.progress(0)
        status = st.empty()
        
        try:
            status.text("Step 1/3: Deploying to production...")
            progress.progress(33)
            
            # Resume workflow with approval
            result = resume_after_approval(
                thread_id=st.session_state.thread_id,
                user_decision="approve"
            )
            
            progress.progress(100)
            
            st.session_state.workflow_state = result
            
            if result.get("error_message"):
                st.session_state.step = "error"
                add_message("assistant", f"Error during deployment: {result['error_message']}")
            else:
                st.session_state.step = "live"
                add_message("assistant", f"🎉 Your campaign is now LIVE at: {result.get('production_url', 'N/A')}")
            
            st.rerun()
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.session_state.step = "error"


def render_live():
    """Render the live campaign summary."""
    st.markdown("## 🎉 Campaign is LIVE!")
    
    state = st.session_state.workflow_state
    
    if not state:
        st.error("No campaign data available")
        return
    
    # Success banner
    st.success(f"Your campaign '{state.get('campaign_name', '')}' is now live!")
    
    # URLs
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🌐 Production URL")
        prod_url = state.get("production_url", "")
        if prod_url:
            st.code(prod_url)
            st.markdown(f"[Open Live Campaign]({prod_url})")
    
    with col2:
        st.markdown("### 📱 QR Code")
        qr_code = state.get("preview_qr_code", "")
        if qr_code:
            st.image(qr_code, width=150)
    
    st.markdown("---")
    
    # Email preview
    st.markdown("### 📧 Email Content")
    
    tab1, tab2 = st.tabs(["English", "中文"])
    
    def clean_email_html(html_content: str) -> str:
        """Extract just the body content from email HTML, removing DOCTYPE and html/head tags."""
        import re
        if not html_content:
            return html_content
        # Remove DOCTYPE
        html_content = re.sub(r'<!DOCTYPE[^>]*>', '', html_content, flags=re.IGNORECASE)
        # Extract body content if present
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, flags=re.IGNORECASE | re.DOTALL)
        if body_match:
            return body_match.group(1).strip()
        # Remove html and head tags if no body found
        html_content = re.sub(r'<html[^>]*>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'</html>', '', html_content, flags=re.IGNORECASE)
        html_content = re.sub(r'<head>.*?</head>', '', html_content, flags=re.IGNORECASE | re.DOTALL)
        return html_content.strip()
    
    with tab1:
        st.markdown(f"**Subject:** {state.get('email_subject_en', 'N/A')}")
        st.markdown("**Body:**")
        email_body_en = clean_email_html(state.get("email_body_en", "N/A"))
        st.markdown(f"""
<div style="background-color: #ffffff; color: #333333; padding: 20px; border-radius: 8px; font-size: 16px; line-height: 1.6;">
{email_body_en}
</div>
""", unsafe_allow_html=True)
    
    with tab2:
        st.markdown(f"**主题:** {state.get('email_subject_zh', 'N/A')}")
        st.markdown("**内容:**")
        email_body_zh = clean_email_html(state.get("email_body_zh", "N/A"))
        st.markdown(f"""
<div style="background-color: #ffffff; color: #333333; padding: 20px; border-radius: 8px; font-size: 16px; line-height: 1.6;">
{email_body_zh}
</div>
""", unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Customer summary
    st.markdown("### 👥 Email Recipients")
    customers = state.get("customer_list", [])
    st.info(f"Emails sent to {len(customers)} VIP customers")
    
    if customers:
        with st.expander("View recipient list"):
            for c in customers[:10]:
                st.write(f"- {c.get('name_en', c.get('name', 'Unknown'))} ({c.get('tier', 'VIP')})")
            if len(customers) > 10:
                st.write(f"... and {len(customers) - 10} more")


def render_error():
    """Render the error screen."""
    st.markdown("## ❌ Error")
    
    state = st.session_state.workflow_state
    error_msg = state.get("error_message", "Unknown error") if state else "Unknown error"
    
    st.error(error_msg)
    
    if st.button("🔄 Try Again", type="primary"):
        st.session_state.step = "welcome"
        st.session_state.workflow_state = None
        st.rerun()


def main():
    """Main application entry point."""
    initialize_session_state()
    render_sidebar()
    
    # Route to appropriate screen based on step
    step = st.session_state.step
    
    if step == "welcome":
        render_welcome()
    elif step == "campaign_details":
        render_campaign_details()
    elif step == "theme_selection":
        render_theme_selection()
    elif step == "generating":
        render_generating()
    elif step == "preview":
        render_preview()
    elif step == "deploying":
        render_deploying()
    elif step == "live":
        render_live()
    elif step == "error":
        render_error()
    else:
        render_welcome()


if __name__ == "__main__":
    main()
