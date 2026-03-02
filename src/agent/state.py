from typing import List, TypedDict, Optional, Dict, Any
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """
    Agent State to track the workflow execution.
    """

    question: str
    generation: Optional[str]
    documents: List[str]  # List of retrieved document contents (JSON formatted)
    queries: List[str]  # List of queries for multi-query retrieval
    retry_count: int
    rejection_count: int  # Track how many times documents were rejected by grader
    chat_history: List[BaseMessage]  # Conversation history
    summary: Optional[str]  # Long-term memory summary
    user_profile: Optional[str]  # User profile (interests, career, pain points)
    evolving_insights: Optional[str]  # Dynamic insights about user/system interaction
    agent_id: Optional[str]  # "dan_koe" or "naval"
    intent: Optional[str]  # "chitchat" or "query"
    intent_metadata: Optional[Dict[str, Any]]  # Metadata from Intent Analysis
    is_sufficient: bool  # Whether local documents are sufficient to answer the query
    
    # --- ReAct & Planning ---
    thought_trace: List[str]  # Agent's internal reasoning steps (for UI "Thinking...")
    search_strategy: Optional[str]  # "local", "web", "hybrid"
    knowledge_gap: bool  # Whether a knowledge gap was detected
    
    # --- Protocol Lock ---
    final_references: List[Dict[str, Any]]  # Strictly typed references for UI (ID, title, url, type)
    
    # --- Multimodal Vision ---
    images: Optional[List[str]]  # List of base64 strings for the current turn
