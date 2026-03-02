from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
from src.core.config import settings


def get_llm(model: str = None, temperature: float = 0.7, streaming: bool = True):
    """
    Get the LangChain ChatOpenAI client for DeepSeek.
    """
    if not model:
        model = settings.DEEPSEEK_MODEL

    return ChatOpenAI(
        model=model,
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL,
        temperature=temperature,
        streaming=streaming,
        timeout=60.0,  # Increase timeout
        max_retries=3, # Explicit retries
    )


async def generate_response(messages: list, model: str = None, stream: bool = True, **kwargs) -> str:
    """
    Generate a response using the LLM (LangChain wrapper).
    Compatible with existing dict-based message format.
    """
    llm = get_llm(model, streaming=stream)

    # Convert dict messages to LangChain messages if needed
    lc_messages = []
    for m in messages:
        if isinstance(m, dict):
            role = m.get("role")
            content = m.get("content", "")
            if role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                # Default to user if unknown, or ignore
                lc_messages.append(HumanMessage(content=content))
        elif isinstance(m, BaseMessage):
            lc_messages.append(m)
        else:
            # Fallback for strings?
            lc_messages.append(HumanMessage(content=str(m)))

    # Invoke
    # LangGraph's astream_events will capture the model's internal stream
    # as long as we use standard invoke/ainvoke and the model has streaming=True.
    response = await llm.ainvoke(lc_messages)
    return response.content
