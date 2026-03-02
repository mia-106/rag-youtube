import sys
import io

# 强制设置标准输出为 UTF-8解决 Windows GBK 导致的问题
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import importlib
import logging
import os
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

# Runtime Check: Ensure Python 3.10+
if sys.version_info < (3, 10):
    print(f" 错误: 检测到 Python {sys.version}. 本系统要求 3.10+请使用 'uv run' 启动")
    sys.exit(1)

print("DEBUG: Server script starting...", file=sys.stderr)

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Lazy load the graph app to avoid startup errors
# app will be loaded on first request
_app = None

def get_app():
    global _app
    if _app is None:
        _app = importlib.import_module("src.agent.graph").app
    return _app

print("DEBUG: Imported graph app.", file=sys.stderr)
SuperabaseClient = importlib.import_module("src.vector_storage.superabase_client").SuperabaseClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
print("DEBUG: Initializing FastAPI...", file=sys.stderr)
app_server = FastAPI(title="Dan Koe RAG Agent API")

# Initialize Database Client
print("DEBUG: Initializing Supabase Client...", file=sys.stderr)
supabase_client = SuperabaseClient()
print("DEBUG: Supabase Client initialized.", file=sys.stderr)

# Startup success log
print("后端服务已就绪API 运行在 http://localhost:8000", flush=True)


@app_server.on_event("startup")
async def startup_event():
    try:
        await supabase_client.connect()
    except Exception as e:
        logger.error(f"Failed to connect to database on startup: {e}")
        # Server will start, but DB operations will fail


@app_server.on_event("shutdown")
async def shutdown_event():
    await supabase_client.disconnect()


# Add CORS middleware to allow requests from Next.js (Vercel)
# Get allowed origins from environment variable, default to localhost for dev
allowed_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
app_server.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Allow Vercel frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    images: Optional[List[str]] = None  # Base64 encoded images
    agent_id: str = "dan_koe"  # "dan_koe" or "naval"
    session_id: str


class FeedbackRequest(BaseModel):
    message_id: str
    is_positive: bool
    comment: Optional[str] = None


# --- Endpoints ---


@app_server.get("/health")
async def health_check():
    return {"status": "ok"}


@app_server.get("/api/history/{session_id}")
async def get_history(session_id: str):
    """
    Get chat history for a session.
    """
    try:
        history = await supabase_client.get_chat_history(session_id)
        return history
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        return []


@app_server.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that streams the agent's response.
    Uses LangGraph's astream_events to capture tokens from the 'generate' node.
    """
    # 1. Validate Input
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    last_message = request.messages[-1]
    if last_message.role != "user":
        raise HTTPException(status_code=400, detail="Last message must be from user")

    question = last_message.content

    # Prepare chat history (convert Pydantic to list of BaseMessage)
    from langchain_core.messages import HumanMessage, AIMessage

    chat_history = []
    for msg in request.messages[:-1]:
        if msg.role == "user":
            chat_history.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            chat_history.append(AIMessage(content=msg.content))

    inputs = {
        "question": question,
        "chat_history": chat_history,
        "retry_count": 0,
        "agent_id": request.agent_id,
        "images": request.images or []
    }

    # Save user message
    try:
        await supabase_client.save_chat_message(request.session_id, "user", question, request.agent_id)
    except Exception as e:
        logger.error(f"Failed to save user message: {e}")

    # 2. Agent Routing
    logger.info(f"Routing to {request.agent_id} agent")

    # 3. Stream Generator
    async def event_generator():
        full_response = ""
        try:
            logger.info("Starting event stream...")
            # Use astream_events to get granular events
            async for event in get_app().astream_events(inputs, version="v1"):
                kind = event["event"]
                logger.debug(f"Event received: {kind}")

                # We only want to stream tokens from the 'generate' node
                # to avoid streaming internal thoughts (like query generation or summarization)
                meta = event.get("metadata", {})
                node_name = meta.get("langgraph_node", "")

                # 1. Stream "Thinking" logs (Step-by-step reasoning)
                if event["event"] == "on_chain_start" and node_name:
                    step_msg = f"__STEP__: {node_name}"
                    yield step_msg

                    # --- PRE-EMPTIVE SOURCES INJECTION ---
                    # If we're starting the 'generate' node, the sources are already in the state
                    # We can extract them and send them immediately so the UI has them even if the stream cuts off
                    if node_name == "generate":
                        try:
                            input_state = event["data"].get("input", {})
                            docs = input_state.get("documents", [])
                            if docs:
                                pre_refs = []
                                video_count = 0
                                web_count = 0
                                assigned_ids = {}
                                
                                import json
                                for doc_str in docs:
                                    try:
                                        d = json.loads(doc_str)
                                        s_id = d.get("id", d.get("source", ""))
                                        if s_id not in assigned_ids:
                                            s_type = d.get("source_type", "video")
                                            if s_type == "web":
                                                web_count += 1
                                                d_id = f"W{web_count}"
                                            else:
                                                video_count += 1
                                                d_id = str(video_count)
                                            assigned_ids[s_id] = d_id
                                            pre_refs.append({
                                                "id": d_id,
                                                "title": d.get("concept", "Unknown"),
                                                "url": d.get("source", ""),
                                                "type": s_type
                                            })
                                    except: continue
                                
                                if pre_refs:
                                    marker = "[[[FINAL_SOURCES_START]]]"
                                    json_payload = f"{marker}{json.dumps(pre_refs, ensure_ascii=False)}"
                                    logger.info(f"Pre-injecting {len(pre_refs)} sources at start of generation.")
                                    yield json_payload
                                    # We don't append to full_response yet to avoid duplicating in displayText clean
                        except Exception as e:
                            logger.error(f"Failed to pre-inject sources: {e}")
                
                # 2. Stream actual content
                if event["event"] == "on_chat_model_stream" and node_name in ["generate", "handle_chitchat"]:
                    chunk = event["data"]["chunk"]
                    if chunk and chunk.content:
                        full_response += chunk.content
                        yield chunk.content
                elif event["event"] == "on_tool_start":
                    tool_name = event["name"]
                    yield f"__STEP__: Using tool {tool_name}..."
                
                # 3. Capture the FINAL appended output from 'generate' node
                # This contains the JSON block which was appended AFTER the LLM stream finished
                elif event["event"] == "on_chain_end" and node_name == "generate":
                    output_data = event["data"].get("output", {})
                    # If output is a dict (expected), get 'generation' key
                    if isinstance(output_data, dict):
                        final_text = output_data.get("generation", "")
                    # If output is just string
                    elif isinstance(output_data, str):
                        final_text = output_data
                    else:
                        final_text = ""
                    
                    # Check if we missed the JSON part
                    marker = "[[[FINAL_SOURCES_START]]]"
                    if marker in final_text and marker not in full_response:
                        # Extract the missing part (JSON) and stream it
                        parts = final_text.split(marker)
                        if len(parts) > 1:
                            missing_part = parts[1]
                            json_payload = f"{marker}{missing_part}"
                            logger.info("Injecting missing JSON sources to stream at end...")
                            yield json_payload
                            full_response += json_payload


            # Save assistant message
            if full_response:
                try:
                    # Append references if available
                    # We need to extract them from the state, but astream_events yields events, not state updates directly.
                    # However, the graph state 'documents' contains the references.
                    # We can't easily access the final state here inside the stream unless we capture it.
                    # For now, let's just save the text. The references are usually embedded in the text by the LLM 
                    # OR we should append the JSON metadata.
                    
                    # Hack: The frontend expects __REFERENCES_JSON__ at the end of the stream
                    # We can try to fetch the final state after the loop, but astream_events finishes when the graph finishes.
                    # Actually, we can't easily get the state here. 
                    # BUT, 'generate' node puts citations in the text. 
                    
                    # Wait! The user says "Stream finished" log appears but frontend is still loading? 
                    # No, user says "answer generated, then continues loading, but no web search logs".
                    # Actually, user says "logs show stream finished".
                    
                    await supabase_client.save_chat_message(
                        request.session_id, "assistant", full_response, request.agent_id
                    )
                except Exception as e:
                    logger.error(f"Failed to save assistant message: {e}")

            logger.info(f"Stream finished for session {request.session_id}")
            # Explicitly yield a final newline or marker to ensure client sees end
            yield "" 

        except Exception as e:
            logger.error(f"Error during streaming: {e}")
            yield f"Error: {str(e)}"

    return StreamingResponse(event_generator(), media_type="text/plain")


@app_server.post("/api/feedback")
async def feedback_endpoint(request: FeedbackRequest):
    """
    Endpoint to receive user feedback and save to Supabase.
    """
    try:
        success = await supabase_client.save_feedback(
            request.message_id, 
            request.is_positive, 
            request.comment
        )
        if success:
            return {"status": "success", "message": "Feedback recorded"}
        else:
            raise HTTPException(status_code=500, detail="Failed to save feedback")
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app_server.get("/api/history")
async def get_sessions():
    """
    Get all chat sessions.
    """
    try:
        sessions = await supabase_client.get_sessions()
        # Convert datetime objects to ISO strings
        for session in sessions:
            if session.get("last_message_at"):
                session["last_message_at"] = session["last_message_at"].isoformat()
        return {"sessions": sessions}
    except Exception as e:
        logger.error(f"Failed to get sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app_server.get("/api/history/{session_id}")
async def get_session_history(session_id: str):
    """
    Get chat history for a specific session.
    """
    try:
        history = await supabase_client.get_chat_history(session_id)
        # Convert datetime objects to ISO strings
        for msg in history:
            if msg.get("created_at"):
                msg["created_at"] = msg["created_at"].isoformat()
        return {"history": history}
    except Exception as e:
        logger.error(f"Failed to get history for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app_server.delete("/api/history/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a specific chat session.
    """
    try:
        success = await supabase_client.delete_session(session_id)
        if success:
            return {"status": "success", "message": f"Session {session_id} deleted"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete session")
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app_server, host="127.0.0.1", port=8000)
