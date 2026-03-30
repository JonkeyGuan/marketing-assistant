"""
LangGraph Orchestrator - Multi-agent workflow for campaign creation.

Coordinates the flow between:
1. Coder Agent - Generate HTML/CSS/JS
2. K8s Agent - Deploy to OpenShift
3. Marketing Agent - Generate email content
4. Customer Agent - Retrieve customer data
"""
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import CampaignState, create_initial_state, CAMPAIGN_THEMES
from app.a2a.client import A2AClient
from app.a2a.models import Message, DataPart, TaskState
from app.settings import settings


def select_theme_node(state: CampaignState) -> CampaignState:
    """Node to handle theme selection (usually done via UI)."""
    print(f"[Orchestrator] Theme selected: {state.get('selected_theme', 'not set')}")
    
    # Validate theme
    if state.get("selected_theme") not in CAMPAIGN_THEMES:
        state["selected_theme"] = "luxury_gold"  # Default
    
    theme_data = CAMPAIGN_THEMES[state["selected_theme"]]
    state["theme_colors"] = theme_data["colors"]
    state["current_step"] = "theme_selected"
    
    return state


def human_approval_node(state: CampaignState) -> CampaignState:
    """Node that waits for human approval (handled by UI interrupt)."""
    print(f"[Orchestrator] Waiting for human approval...")
    state["awaiting_approval"] = True
    state["current_step"] = "awaiting_approval"
    return state


def route_after_approval(state: CampaignState) -> Literal["select_theme", "deploy_production"]:
    """Route based on user decision after preview."""
    decision = state.get("user_decision", "")
    print(f"[Orchestrator] User decision: {decision}")
    
    if decision == "edit":
        return "select_theme"
    else:
        return "deploy_production"


def check_for_errors(state: CampaignState) -> Literal["continue", "error"]:
    """Check if there are any errors in the state."""
    if state.get("error_message"):
        return "error"
    return "continue"


def error_handler_node(state: CampaignState) -> CampaignState:
    """Handle errors in the workflow."""
    print(f"[Orchestrator] Error: {state.get('error_message')}")
    state["current_step"] = "error"
    return state


def coder_agent_a2a(state: CampaignState) -> CampaignState:
    """Call the Coder Agent via A2A protocol."""
    print(f"[Orchestrator] Calling Coder Agent via A2A: {settings.CODER_A2A_URL}")

    theme_key = state.get("selected_theme", "luxury_gold")
    theme_data = CAMPAIGN_THEMES.get(theme_key, CAMPAIGN_THEMES["luxury_gold"])

    message = Message(
        role="user",
        parts=[DataPart(data={
            "campaign_name": state["campaign_name"],
            "campaign_description": state["campaign_description"],
            "hotel_name": state["hotel_name"],
            "theme_colors": theme_data["colors"],
            "theme_name": theme_data["name"],
            "start_date": state.get("start_date", ""),
            "end_date": state.get("end_date", ""),
        })],
    )

    try:
        client = A2AClient(settings.CODER_A2A_URL)
        task = client.send_task(message)

        if task.status.state == TaskState.FAILED:
            error_msg = ""
            if task.status.message:
                error_msg = task.status.message.parts[0].text
            state["error_message"] = f"Coder Agent error: {error_msg}"
            state["current_step"] = "error"
            return state

        # Extract HTML from artifact
        if task.artifacts:
            for artifact in task.artifacts:
                for part in artifact.parts:
                    if isinstance(part, DataPart) and "generated_html" in part.data:
                        state["generated_html"] = part.data["generated_html"]

        state["theme_colors"] = theme_data["colors"]
        state["current_step"] = "code_generated"
        state["error_message"] = ""
        state["messages"] = state.get("messages", []) + [{
            "role": "assistant",
            "agent": "coder",
            "content": f"Generated marketing page for '{state['campaign_name']}' with {theme_data['name']} theme (via A2A).",
        }]
        print(f"[Orchestrator] Coder Agent A2A call succeeded")

    except Exception as e:
        state["error_message"] = f"Coder Agent A2A error: {str(e)}"
        state["current_step"] = "error"
        print(f"[Orchestrator] Coder Agent A2A error: {e}")

    return state


def k8s_agent_deploy_preview_a2a(state: CampaignState) -> CampaignState:
    """Call the K8s Agent via A2A protocol to deploy preview."""
    print(f"[Orchestrator] Calling K8s Agent via A2A: {settings.K8S_A2A_URL}")

    message = Message(
        role="user",
        parts=[DataPart(data={
            "action": "deploy_preview",
            "campaign_id": state.get("campaign_id", "campaign"),
            "generated_html": state.get("generated_html", ""),
        })],
    )

    try:
        client = A2AClient(settings.K8S_A2A_URL)
        task = client.send_task(message)

        if task.status.state == TaskState.FAILED:
            error_msg = ""
            if task.status.message:
                error_msg = task.status.message.parts[0].text
            state["error_message"] = f"K8s Agent error: {error_msg}"
            state["current_step"] = "error"
            return state

        if task.artifacts:
            for artifact in task.artifacts:
                for part in artifact.parts:
                    if isinstance(part, DataPart) and part.data:
                        data = part.data
                        state["deployment_name"] = data.get("deployment_name", "")
                        state["preview_url"] = data.get("preview_url", "")
                        state["preview_qr_code"] = data.get("preview_qr_code", "")

        state["current_step"] = "preview_ready"
        state["awaiting_approval"] = True
        state["error_message"] = ""
        preview_url = state.get("preview_url", "")
        state["messages"] = state.get("messages", []) + [{
            "role": "assistant",
            "agent": "k8s",
            "content": f"Campaign deployed to preview environment. URL: {preview_url} (via A2A).",
        }]
        print(f"[Orchestrator] K8s Agent preview deploy succeeded: {preview_url}")

    except Exception as e:
        state["error_message"] = f"K8s Agent A2A error: {str(e)}"
        state["current_step"] = "error"
        print(f"[Orchestrator] K8s Agent A2A error: {e}")

    return state


def k8s_agent_promote_production_a2a(state: CampaignState) -> CampaignState:
    """Call the K8s Agent via A2A protocol to promote to production."""
    print(f"[Orchestrator] Calling K8s Agent via A2A (promote): {settings.K8S_A2A_URL}")

    message = Message(
        role="user",
        parts=[DataPart(data={
            "action": "promote_production",
            "campaign_id": state.get("campaign_id", "campaign"),
            "generated_html": state.get("generated_html", ""),
        })],
    )

    try:
        client = A2AClient(settings.K8S_A2A_URL)
        task = client.send_task(message)

        if task.status.state == TaskState.FAILED:
            error_msg = ""
            if task.status.message:
                error_msg = task.status.message.parts[0].text
            state["error_message"] = f"K8s Agent error: {error_msg}"
            state["current_step"] = "error"
            return state

        if task.artifacts:
            for artifact in task.artifacts:
                for part in artifact.parts:
                    if isinstance(part, DataPart) and part.data:
                        data = part.data
                        state["production_url"] = data.get("production_url", "")

        state["current_step"] = "deployed_to_production"
        state["awaiting_approval"] = False
        state["error_message"] = ""
        production_url = state.get("production_url", "")
        state["messages"] = state.get("messages", []) + [{
            "role": "assistant",
            "agent": "k8s",
            "content": f"Campaign promoted to production! Live URL: {production_url} (via A2A).",
        }]
        print(f"[Orchestrator] K8s Agent production deploy succeeded: {production_url}")

    except Exception as e:
        state["error_message"] = f"K8s Agent A2A error: {str(e)}"
        state["current_step"] = "error"
        print(f"[Orchestrator] K8s Agent A2A error: {e}")

    return state


def customer_agent_a2a(state: CampaignState) -> CampaignState:
    """Call the Customer Agent via A2A protocol."""
    print(f"[Orchestrator] Calling Customer Agent via A2A: {settings.CUSTOMER_A2A_URL}")

    target_audience = state.get("target_audience", "VIP members")

    message = Message(
        role="user",
        parts=[DataPart(data={
            "target_audience": target_audience,
        })],
    )

    try:
        client = A2AClient(settings.CUSTOMER_A2A_URL)
        task = client.send_task(message)

        if task.status.state == TaskState.FAILED:
            error_msg = ""
            if task.status.message:
                error_msg = task.status.message.parts[0].text
            state["error_message"] = f"Customer Agent error: {error_msg}"
            state["current_step"] = "error"
            return state

        # Extract customer list from artifact
        if task.artifacts:
            for artifact in task.artifacts:
                for part in artifact.parts:
                    if isinstance(part, DataPart) and "customers" in part.data:
                        state["customer_list"] = part.data["customers"]

        state["current_step"] = "customers_retrieved"
        state["error_message"] = ""
        customers = state.get("customer_list", [])
        state["messages"] = state.get("messages", []) + [{
            "role": "assistant",
            "agent": "customer",
            "content": f"Retrieved {len(customers)} customers matching '{target_audience}' (via A2A).",
        }]
        print(f"[Orchestrator] Customer Agent A2A call succeeded: {len(customers)} customers")

    except Exception as e:
        state["error_message"] = f"Customer Agent A2A error: {str(e)}"
        state["current_step"] = "error"
        print(f"[Orchestrator] Customer Agent A2A error: {e}")

    return state


def marketing_agent_a2a(state: CampaignState) -> CampaignState:
    """Call the Marketing Agent via A2A protocol."""
    print(f"[Orchestrator] Calling Marketing Agent via A2A: {settings.MARKETING_A2A_URL}")

    campaign_url = state.get("production_url") or state.get("preview_url") or ""

    message = Message(
        role="user",
        parts=[DataPart(data={
            "campaign_name": state["campaign_name"],
            "campaign_description": state["campaign_description"],
            "hotel_name": state["hotel_name"],
            "campaign_url": campaign_url,
            "target_audience": state.get("target_audience", ""),
            "start_date": state.get("start_date", ""),
            "end_date": state.get("end_date", ""),
        })],
    )

    try:
        client = A2AClient(settings.MARKETING_A2A_URL)
        task = client.send_task(message)

        if task.status.state == TaskState.FAILED:
            error_msg = ""
            if task.status.message:
                error_msg = task.status.message.parts[0].text
            state["error_message"] = f"Marketing Agent error: {error_msg}"
            state["current_step"] = "error"
            return state

        # Extract email content from artifact
        if task.artifacts:
            for artifact in task.artifacts:
                for part in artifact.parts:
                    if isinstance(part, DataPart) and part.data:
                        data = part.data
                        state["email_subject_en"] = data.get("subject_en", "")
                        state["email_body_en"] = data.get("body_en", "")
                        state["email_subject_zh"] = data.get("subject_zh", "")
                        state["email_body_zh"] = data.get("body_zh", "")

        state["current_step"] = "email_generated"
        state["error_message"] = ""
        state["messages"] = state.get("messages", []) + [{
            "role": "assistant",
            "agent": "marketing",
            "content": f"Generated email content in English and Chinese for '{state['campaign_name']}' (via A2A).",
        }]
        print(f"[Orchestrator] Marketing Agent A2A call succeeded")

    except Exception as e:
        state["error_message"] = f"Marketing Agent A2A error: {str(e)}"
        state["current_step"] = "error"
        print(f"[Orchestrator] Marketing Agent A2A error: {e}")

    return state


def simulate_email_send(state: CampaignState) -> CampaignState:
    """Simulate sending emails to customers."""
    print(f"[Orchestrator] Simulating email send...")

    customer_list = state.get("customer_list", [])

    if not customer_list:
        customer_list = [
            {"name": "张伟", "name_en": "Wei Zhang", "email": "wei.zhang@example.com", "preferred_language": "zh-CN"},
            {"name": "李明", "name_en": "Ming Li", "email": "ming.li@example.com", "preferred_language": "zh-CN"},
            {"name": "John Smith", "name_en": "John Smith", "email": "john.smith@example.com", "preferred_language": "en"},
        ]

    sent_count = 0
    for customer in customer_list:
        lang = customer.get("preferred_language", "en")
        name = customer.get("name") if lang == "zh-CN" else customer.get("name_en", customer.get("name"))
        email = customer.get("email")

        if lang == "zh-CN":
            subject = state.get("email_subject_zh", "")
        else:
            subject = state.get("email_subject_en", "")

        print(f"  [SIMULATED] Sending to {name} <{email}> - Subject: {subject[:50]}...")
        sent_count += 1

    state["messages"] = state.get("messages", []) + [{
        "role": "assistant",
        "agent": "marketing",
        "content": f"[SIMULATED] Sent {sent_count} emails to customers.",
    }]

    state["current_step"] = "emails_sent"

    return state


def build_campaign_graph() -> StateGraph:
    """Build the LangGraph workflow for campaign creation."""
    
    # Create the graph
    workflow = StateGraph(CampaignState)
    
    # Add nodes
    workflow.add_node("select_theme", select_theme_node)
    workflow.add_node("generate_code", coder_agent_a2a)
    workflow.add_node("deploy_preview", k8s_agent_deploy_preview_a2a)
    workflow.add_node("human_approval", human_approval_node)
    workflow.add_node("deploy_production", k8s_agent_promote_production_a2a)
    workflow.add_node("get_customers", customer_agent_a2a)
    workflow.add_node("generate_email", marketing_agent_a2a)
    workflow.add_node("send_emails", simulate_email_send)
    workflow.add_node("error_handler", error_handler_node)
    
    # Define edges - Main flow
    workflow.add_edge(START, "select_theme")
    workflow.add_edge("select_theme", "generate_code")
    
    # After code generation, check for errors
    workflow.add_conditional_edges(
        "generate_code",
        check_for_errors,
        {
            "continue": "deploy_preview",
            "error": "error_handler"
        }
    )
    
    # After preview deployment, check for errors
    workflow.add_conditional_edges(
        "deploy_preview",
        check_for_errors,
        {
            "continue": "human_approval",
            "error": "error_handler"
        }
    )
    
    # Human approval routes to either edit or production
    workflow.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "select_theme": "select_theme",
            "deploy_production": "deploy_production"
        }
    )
    
    # After production deployment
    workflow.add_conditional_edges(
        "deploy_production",
        check_for_errors,
        {
            "continue": "get_customers",
            "error": "error_handler"
        }
    )
    
    # After customer retrieval, check for errors
    workflow.add_conditional_edges(
        "get_customers",
        check_for_errors,
        {
            "continue": "generate_email",
            "error": "error_handler"
        }
    )
    
    # After email generation
    workflow.add_conditional_edges(
        "generate_email",
        check_for_errors,
        {
            "continue": "send_emails",
            "error": "error_handler"
        }
    )
    
    # End after sending emails
    workflow.add_edge("send_emails", END)
    
    # Error handler ends the workflow
    workflow.add_edge("error_handler", END)
    
    return workflow


def compile_workflow(checkpointer=None):
    """Compile the workflow with optional checkpointer."""
    workflow = build_campaign_graph()
    
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    return workflow.compile(checkpointer=checkpointer)


# Global app instance
_app = None
_checkpointer = None


def get_app():
    """Get or create the compiled workflow app."""
    global _app, _checkpointer
    
    if _app is None:
        _checkpointer = MemorySaver()
        _app = compile_workflow(_checkpointer)
    
    return _app


def run_campaign_workflow(
    campaign_name: str,
    campaign_description: str,
    hotel_name: str = "Grand Luxe Hotel & Casino",
    target_audience: str = "VIP members",
    selected_theme: str = "luxury_gold",
    start_date: str = "",
    end_date: str = "",
    thread_id: str = None
) -> CampaignState:
    """
    Run the campaign creation workflow.
    
    This runs until it hits the human_approval node, then returns.
    Call resume_after_approval() to continue.
    """
    import uuid
    
    app = get_app()
    
    # Create initial state
    initial_state = create_initial_state(
        campaign_name=campaign_name,
        campaign_description=campaign_description,
        hotel_name=hotel_name,
        target_audience=target_audience,
        start_date=start_date,
        end_date=end_date
    )
    initial_state["selected_theme"] = selected_theme
    
    # Generate thread ID if not provided
    if thread_id is None:
        thread_id = f"thread-{uuid.uuid4().hex[:8]}"
    
    config = {"configurable": {"thread_id": thread_id}}
    
    print(f"\n{'='*60}")
    print(f"Starting Campaign Workflow: {campaign_name}")
    print(f"Thread ID: {thread_id}")
    print(f"{'='*60}\n")
    
    # Run until interrupt (human_approval)
    result = None
    for event in app.stream(initial_state, config):
        # Get the latest state
        for node_name, node_state in event.items():
            result = node_state
            print(f"[{node_name}] Step: {node_state.get('current_step', 'unknown')}")
        
        # Check if we're waiting for approval
        if result and result.get("awaiting_approval"):
            print("\n[Orchestrator] Workflow paused - awaiting human approval")
            break
    
    return result, thread_id


def resume_after_approval(
    thread_id: str,
    user_decision: str  # "edit" or "approve"
) -> CampaignState:
    """
    Resume the workflow after human approval.
    
    Args:
        thread_id: The thread ID from run_campaign_workflow
        user_decision: Either "edit" (go back to theme selection) or "approve" (go live)
    """
    app = get_app()
    config = {"configurable": {"thread_id": thread_id}}
    
    # Get current state
    current_state = app.get_state(config)
    
    if current_state is None:
        raise ValueError(f"No state found for thread: {thread_id}")
    
    # Update state with user decision
    updated_state = dict(current_state.values)
    updated_state["user_decision"] = user_decision
    updated_state["awaiting_approval"] = False
    
    print(f"\n{'='*60}")
    print(f"Resuming Workflow - Decision: {user_decision}")
    print(f"{'='*60}\n")
    
    # Update the state
    app.update_state(config, updated_state)
    
    # Continue execution
    result = None
    for event in app.stream(None, config):
        for node_name, node_state in event.items():
            result = node_state
            print(f"[{node_name}] Step: {node_state.get('current_step', 'unknown')}")
    
    return result


# For testing
if __name__ == "__main__":
    print("Testing Campaign Workflow (without actual model calls)...")
    print("Note: This will fail without model endpoints. Use the Streamlit UI for full testing.")
    
    # Show workflow structure
    workflow = build_campaign_graph()
    print("\nWorkflow nodes:")
    for node in workflow.nodes:
        print(f"  - {node}")
