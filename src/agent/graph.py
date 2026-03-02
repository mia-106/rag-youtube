from langgraph.graph import END, StateGraph
from src.agent.state import AgentState
from src.agent.nodes import (
    grade_documents,
    generate,
    summarize_conversation,
    self_correct,
    route_query,
    handle_chitchat,
    update_profile,
    retrieve,
    web_search,
)


def decide_route(state: AgentState):
    """
    Route based on intent.
    - chitchat -> handle_chitchat
    - query -> summarize_conversation (RAG)
    - search_direct -> web_search (Skip RAG)
    """
    print("---DECIDE ROUTE---")
    intent = state.get("intent", "query")
    if intent == "chitchat":
        print("---DECISION: CHITCHAT---")
        return "handle_chitchat"
    elif intent == "search_direct":
        print("---DECISION: DIRECT SEARCH (Skip RAG)---")
        return "web_search"
    else:
        print("---DECISION: QUERY (RAG)---")
        return "summarize_conversation"


def decide_sufficiency(state: AgentState):
    """
    Route based on Grader's Sufficiency Check.
    - If Sufficient: Go directly to Generate.
    - If Insufficient: Go to Web Search.
    """
    print("---DECIDE SUFFICIENCY---")
    is_sufficient = state.get("is_sufficient", False)

    if is_sufficient:
        print("---DECISION: SUFFICIENT (GENERATE)---")
        return "generate"
    else:
        print("---DECISION: INSUFFICIENT (WEB SEARCH)---")
        return "web_search"


# Define the graph
workflow = StateGraph(AgentState)

# Define the nodes
workflow.add_node("route_query", route_query)
workflow.add_node("handle_chitchat", handle_chitchat)
workflow.add_node("summarize_conversation", summarize_conversation)
workflow.add_node("retrieve", retrieve)
workflow.add_node("grade_documents", grade_documents)
workflow.add_node("web_search", web_search)
workflow.add_node("generate", generate)
workflow.add_node("self_correct", self_correct)
workflow.add_node("update_profile", update_profile)

# Build graph
workflow.set_entry_point("route_query")

workflow.add_conditional_edges(
    "route_query",
    decide_route,
    {
        "handle_chitchat": "handle_chitchat",
        "web_search": "web_search",
        "summarize_conversation": "summarize_conversation",
    },
)

workflow.add_edge("handle_chitchat", END)
workflow.add_edge("summarize_conversation", "retrieve")
workflow.add_edge("retrieve", "grade_documents")

# New Conditional Edge for Semantic CRAG
workflow.add_conditional_edges(
    "grade_documents",
    decide_sufficiency,
    {
        "generate": "generate",
        "web_search": "web_search",
    },
)

workflow.add_edge("web_search", "generate")
workflow.add_edge("generate", "self_correct")
workflow.add_edge("self_correct", "update_profile")
workflow.add_edge("update_profile", END)

# Compile
app = workflow.compile()
