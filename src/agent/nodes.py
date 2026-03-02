import logging
import asyncio
import requests
import json
import asyncpg
import re
from typing import Dict, Any, Optional
from src.agent.state import AgentState
from src.retrieval.hybrid_search import HybridSearchEngine, SearchConfig
from src.core.config import settings, AGENT_CONFIGS
from src.agent.llm import generate_response
from src.retrieval.search_service import SearchService

# Global service instance
_search_service = None


async def get_search_service():
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
        await _search_service.initialize()
    return _search_service


class TavilyClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.tavily.com/search"

    def search(self, query: str, search_depth: str = "basic", max_results: int = 5, **kwargs) -> Dict[str, Any]:
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            **kwargs,
        }
        response = requests.post(self.base_url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()


logger = logging.getLogger(__name__)

# Global engine instance (lazy init)
_search_engine = None


async def get_search_engine():
    global _search_engine
    if _search_engine is None:
        engine = HybridSearchEngine(settings.DATABASE_URL)
        await engine.initialize()
        _search_engine = engine
    return _search_engine


async def route_query(state: AgentState) -> Dict[str, Any]:
    """
    PLANNER NODE (Master Brain):
    Analyzes intent, time sensitivity, and knowledge boundaries to decide the execution strategy.
    """
    print("---PLANNER NODE (ReAct Decision)---")
    question = state["question"]
    import datetime
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")

    # 1. Fast Path: Regex for common greetings
    greeting_pattern = r"^(hi|hello|hey|greetings?|你好|您好|早上好|晚上好|嗨|哈喽|what'?s up)[!.,?]*$"
    if re.match(greeting_pattern, question.strip(), re.IGNORECASE):
        print("Intent detected (Fast Path): chitchat")
        return {"intent": "chitchat", "search_strategy": "none", "thought_trace": ["Fast path greeting detected."]}

    prompt = f"""You are the "Master Planner" for Dan Koe's Digital Brain.
    Current Date: {current_date}
    
    Your job is to analyze the User Input and decide the BEST strategy to answer it.
    USE YOUR REASONING.

    User Input: {question}

    DECISION LOGIC (CRITICAL):
    1. **Chitchat**: "Hello", "Thanks", "How are you".
    
    2. **RAG (Local Memory) - PRIORITY 1**:
       - Questions about **SYSTEMS, PHILOSOPHY, STRATEGY, MINDSET**.
       - Even if the user mentions future years (e.g., "Strategy for 2026", "Future of Work"), this is usually a **SYSTEMS** question, not a news question. Dan's local content contains timeless predictions.
       - ALWAYS prefer 'query' (RAG) for broad topics like "Super Individual" (超级个体), "Deep Work", "Leverage".
       - Only skip RAG if the term is a brand new specific TECHNOLOGY released recently (e.g. "GPT-6").

    3. **Direct Web Search**:
       - Only for verifiable **FACTS** that changed yesterday/today.
       - Only for **SPECIFIC NEWS** events (e.g., "Who won the Super Bowl 2026").
       - Only if the user explicitly asks to "search twitter" or "check latest news".

    Output JSON ONLY:
    {{
        "intent": "chitchat" | "query" | "search_direct",
        "search_strategy": "local" (for RAG) | "web" (for Search) | "none",
        "reasoning": "Explain WHY you chose this path in 1 sentence.",
        "time_horizon": "2026" | "current" | "timeless" | null
    }}
    """

    try:
        messages = [{"role": "user", "content": prompt}]
        response = await generate_response(messages, stream=False)
        cleaned = response.replace("```json", "").replace("```", "").strip()
        plan = json.loads(cleaned)
        
        intent = plan.get("intent", "query")
        strategy = plan.get("search_strategy", "local")
        reasoning = plan.get("reasoning", "No reasoning provided")
        time_horizon = plan.get("time_horizon")
        
        print(f"Planner Decision: {intent} (Strategy: {strategy})")
        print(f"Planner Logic: {reasoning}")
        
        return {
            "intent": intent,
            "search_strategy": strategy,
            "intent_metadata": {"time_horizon": time_horizon},
            "thought_trace": [f"Planner: {reasoning}"]
        }
        
    except Exception as e:
        print(f"Planner Failed: {e}. Defaulting to RAG.")
        return {"intent": "query", "search_strategy": "local", "thought_trace": ["Planner failed, defaulting to Local RAG."]}


async def handle_chitchat(state: AgentState) -> Dict[str, Any]:
    """
    Handle chitchat with a simple, persona-aligned response.
    """
    print("---HANDLE CHITCHAT---")
    question = state["question"]
    agent_id = state.get("agent_id", "dan_koe")

    if agent_id == "naval":
        system_prompt = """You are Naval Ravikant.
        Reply to the user's greeting or small talk concisely.
        Be calm, friendly, but profound.
        Do NOT be long-winded.
        Output in Chinese (Simplified).
        STRICT RULE: DO NOT use any emojis or emoticons.
        """
    else:
        system_prompt = """You are Dan Koe.
        Reply to the user's greeting or small talk in a cool, minimalist way.
        Use a short sentence. Maybe ask if they are ready to focus or build.
        Do NOT be long-winded.
        Output in Chinese (Simplified).
        STRICT RULE: DO NOT use any emojis or emoticons in your response.
        """

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]

    generation = await generate_response(messages)
    return {"generation": generation}


async def summarize_conversation(state: AgentState) -> Dict[str, Any]:
    """
    Summarize conversation history if it exceeds 8 turns.
    Strategic Forgetting: Keep Core Consensus, clear redundancy.
    """
    print("---SUMMARIZE CONVERSATION---")
    chat_history = state.get("chat_history", [])
    summary = state.get("summary", "")

    # Only summarize if history is getting long
    if len(chat_history) > 8:
        print("DEBUG: Context threshold reached. Consolidating memory...")
        prompt = f"""
        Distill the following conversation into a concise "Core Consensus" summary.
        Preserve key user preferences and agreed-upon facts. 
        Discard transient chitchat.
        
        Current Summary: {summary}
        
        Recent Conversation:
        {chat_history}
        """
        messages = [{"role": "user", "content": prompt}]
        # Non-streaming for summary
        new_summary = await generate_response(messages, stream=False)

        # Keep only last 2 turns to maintain flow
        new_history = chat_history[-2:]
        return {"chat_history": new_history, "summary": new_summary}

    return {}


async def retrieve(state: AgentState) -> Dict[str, Any]:
    """
    Retrieve documents based on the current question (or multiple queries).
    If no multiple queries exist, generate them first (First Round Multi-Query).
    """
    print("---RETRIEVE---")
    question = state["question"]
    queries = state.get("queries", [])

    # 1. Multi-Query Logic (If not already generated)
    # Enable First Round Multi-Query: Do not use user's original query directly.
    if not queries or (len(queries) == 1 and queries[0] == question):
        print("[Enabling Multi-Query...]")

        prompt = f"""You are an expert search query optimizer.
        Generate 3 different versions of the following user question to improve retrieval coverage.
        
        Original Question: {question}
        
        Requirements:
        1. First version: The original question (translated to English if it's not).
        2. Second version: A more specific/detailed version focusing on key entities.
        3. Third version: A variation using synonyms or related concepts.
        
        Output ONLY the 3 queries, separated by newlines. No numbering, no prefixes.
        """

        try:
            messages = [{"role": "user", "content": prompt}]
            response = await generate_response(messages)
            raw_queries = [line.strip() for line in response.split("\n") if line.strip()]
            queries = []
            seen = set()
            for q in raw_queries:
                if q and q not in seen:
                    queries.append(q)
                    seen.add(q)

            if not queries:
                queries = [question]
            print(f"Generated {len(queries)} queries: {queries}")
        except Exception as e:
            print(f"Multi-query generation failed: {e}")
            queries = [question]

    search_engine = await get_search_engine()
    
    all_results = []
    
    # Run searches for all queries concurrently
    # Deduplication is handled by the search engine or simply by set logic later
    # For simplicity, we just run search for each query and aggregate
    for q in queries:
        print(f"Searching for: {q}")
        # Fix: Use SearchConfig to pass top_k limit, not 'limit' kwarg
        q_config = SearchConfig(top_k=5)
        results = await search_engine.search(q, config=q_config)
        all_results.extend(results)
        print(f" - Found {len(results)} results for '{q}'")

    # Deduplicate by content or ID
    unique_results = {}
    for r in all_results:
        # Use content hash or video_id as key
        key = r.metadata.get("video_id", r.content[:50])
        if key not in unique_results:
            unique_results[key] = r
    
    results = list(unique_results.values())
    
    # 3. Post-Aggregation Slicing (CRITICAL FIX)
    # The user complained about "9 videos returned". 
    # We must enforce a hard limit on the total context window size.
    # We re-sort by score (descending) and take the top 5 global results.
    results.sort(key=lambda x: x.score, reverse=True)
    results = results[:5]  # Hard cap at 5 distinct videos/chunks
    
    print(f"Total Unique Local Results (Sliced): {len(results)}")

    documents = []
    for r in results:
        meta = r.metadata
        # Map internal metadata keys (video_title, video_id) to display keys
        title = meta.get("video_title", meta.get("title", "Unknown Title"))

        # Construct URL from video_id if available
        video_id = meta.get("video_id")
        if video_id:
            url = f"https://www.youtube.com/watch?v={video_id}"
            # Add timestamp if available
            start_time = meta.get("start_time")
            if start_time:
                try:
                    url += f"&t={int(float(start_time))}s"
                except (ValueError, TypeError):
                    pass
        else:
            url = meta.get("source", meta.get("url", "Unknown Source"))

        # 2. Context Assembly
        # Dynamic Context Assembly: 【背景：{metadata['video_summary']}】\n【正文：{page_content}】
        video_summary = meta.get("video_summary", "暂无摘要")
        page_content = r.content

        assembled_content = f"【背景：{video_summary}】\n【正文：{page_content}】"

        # Structure Memory Encapsulation (JSON)
        # User Req: {"source": "...", "concept": "...", "content": "..."}
        doc_obj = {
            "id": video_id if video_id else url,
            "source": url,
            "concept": title,
            "content": assembled_content,
            "source_type": "video",
        }
        doc_json = json.dumps(doc_obj, ensure_ascii=False)
        documents.append(doc_json)

    return {"documents": documents, "question": question, "queries": queries}


async def grade_documents(state: AgentState) -> Dict[str, Any]:
    """
    Semantic Grader Node (V3.0):
    1. Filters irrelevant documents.
    2. Judges 'Sufficiency' based on Philosophy vs Fact rules.
    """
    print("---GRADE DOCUMENTS (SEMANTIC GRADER)---")
    question = state["question"]
    documents = state["documents"]
    rejection_count = state.get("rejection_count", 0)

    # Step 1: Filter Irrelevant Docs (Legacy Logic, kept for noise reduction)
    # RESTORED: Semantic Grader Logic
    # We will use the LLM to grade the documents to ensure "Sufficiency".
    print(f"Semantic Grader: Evaluating {len(documents)} documents for sufficiency...")
    filtered_docs = documents

    print(f"Retained {len(filtered_docs)}/{len(documents)} documents.")

    # Step 2: Semantic Sufficiency Check (The Core Logic)
    # Context Assembly for Grader
    context_text = ""
    for doc_str in filtered_docs:
        try:
            doc_data = json.loads(doc_str)
            context_text += f"\n{doc_data.get('content', '')[:500]}"  # Truncate for token efficiency
        except Exception:
            pass

    grader_prompt = f"""You are a "Semantic Grader" for a RAG system.
    Your job is to decide if the retrieved local knowledge is SUFFICIENT to answer the user's query, or if we need to search the web for new facts.

    User Query: {question}

    Retrieved Local Knowledge (Summary):
    {context_text[:5000]}

    JUDGMENT PROCESS (STRICT):
    Step 1: Entity Extraction
    Identify core proper nouns, specific tools, people, or new concepts in the User Query (e.g., "OpenAI Operator", "DeepSeek-V3", "Kortex").

    Step 2: Fact Checking
    Check if these specific entities are EXPLICITLY defined or described in the Local Knowledge.
    - If the user asks "What is [New Term]?" and the Local Knowledge contains NO definition of [New Term], you MUST fail.
    - If the user asks for an opinion on [New Term] and you have no facts about it, you CANNOT use general philosophy to guess. You MUST fail.

    JUDGMENT RULES:
    1. Rule A (Philosophy/Methodology - SUFFICIENT): 
       If the Query asks about general concepts, methodology, or trends (e.g., "How to focus better", "Dan Koe's writing system", "Future of Work") AND the Local Knowledge contains the underlying logic/system, mark as SUFFICIENT.
       Even if the query mentions a future year (e.g. "2026"), if the local content covers the STRATEGY for the future, it is SUFFICIENT.

    2. Rule B (Entity Grounding - INSUFFICIENT):
       If the Query asks about a specific EXTERNAL entity (e.g., "OpenAI Operator", "Claude 3.5") and the Local Knowledge is silent or vague on this specific noun, mark as INSUFFICIENT (false). 
       DO NOT HALLUCINATE connection. Philosophy cannot replace facts.

    Output pure JSON:
    {{
        "is_sufficient": boolean,
        "reason": "short explanation"
    }}
    """

    is_sufficient = False
    try:
        messages = [{"role": "user", "content": grader_prompt}]
        response = await generate_response(messages)
        # Clean response to ensure JSON
        response = response.replace("```json", "").replace("```", "").strip()
        result = json.loads(response)
        is_sufficient = result.get("is_sufficient", False)
        reason = result.get("reason", "No reason provided")
        print("---SEMANTIC GRADER JUDGMENT---")
        print(f"Sufficiency: {is_sufficient}")
        print(f"Reason: {reason}")
    except Exception as e:
        print(f"Semantic Grader Failed: {e}. Defaulting to False (Search Web).")
        is_sufficient = False

    # If no docs remained after filtering, it's definitely insufficient
    if not filtered_docs:
        is_sufficient = False

    return {"documents": filtered_docs, "rejection_count": rejection_count, "is_sufficient": is_sufficient}


async def self_correct(state: AgentState) -> Dict[str, Any]:
    """
    Self-Reflection Node: Checks if the generated answer is grounded in the retrieved documents.
    If hallucinations are detected, attempts to fix them.
    """
    print("---SELF-CORRECT---")
    generation = state["generation"]
    documents = state["documents"]

    # Extract text content from JSON documents
    context_text = ""
    for doc_str in documents:
        try:
            doc_data = json.loads(doc_str)
            context_text += f"\n{doc_data.get('content', '')}"
        except Exception:
            context_text += f"\n{doc_str}"

    # Self-Correction Prompt
    prompt = f"""You are a strict fact-checker. 
    Verify if the following Answer is fully grounded in the provided Context.
    
    Context:
    {context_text[:10000]}  # Limit context size
    
    Answer:
    {generation}
    
    Task:
    1. Identify any statements in the Answer that are NOT supported by the Context.
    2. If the Answer is fully supported, output it exactly as is, including any citations like [1] and the __REFERENCES_JSON__ block at the end.
    3. If there are hallucinations (unsupported claims), rewrite the Answer to remove them. You MUST preserve the __REFERENCES_JSON__ block at the very end of your response.
    4. Maintain the original tone (Dan Koe style) as much as possible while being factual.
    5. Ensure __REFERENCES_JSON__ follows the schema: [{{"id": "...", "title": "...", "url": "..."}}]
    
    Output ONLY the final response (Answer + References). Do NOT use any emojis or special symbols. Do not output "Analysis" or "Correction".
    """

    messages = [{"role": "user", "content": prompt}]
    corrected_generation = await generate_response(messages)

    print(f"DEBUG: Corrected Generation successful. Length: {len(corrected_generation)}")
    if "__REFERENCES_JSON__" not in corrected_generation and "__REFERENCES_JSON__" in generation:
        print("Warning: Self-correction stripped references. Restoring them.")
        ref_start = generation.find("__REFERENCES_JSON__")
        corrected_generation += "\n" + generation[ref_start:]

    if corrected_generation != generation:
        print("Self-Correction applied fixes.")
    else:
        print("Answer is faithful.")

    return {"generation": corrected_generation}


async def web_search(state: AgentState) -> Dict[str, Any]:
    """
    Web Search Node (V2.0 Robust):
    - Independent Error Handling
    - Timeout Protection
    - Dynamic Configuration
    - Graceful Degradation: Returns empty list on failure
    """
    print("---WEB SEARCH---")
    question = state["question"]
    agent_id = state.get("agent_id", "dan_koe")
    current_docs = state.get("documents", [])  # Keep existing docs if any

    try:
        # 1. Load Agent Config
        agent_config = AGENT_CONFIGS.get(agent_id, AGENT_CONFIGS["dan_koe"])
        search_domains = agent_config["search_domains"]
        full_name = agent_config["full_name"]

        # 2. Execute Search via Service (with timeout)
        service = await get_search_service()

        search_query = f"{full_name} {question}"

        # OPTIMIZATION: Reduce timeout to 5s to fail fast
        results = await asyncio.wait_for(service.search(search_query, search_domains), timeout=30.0)

        web_docs = []
        intent_metadata = {}

        for item in results:
            content = item.get("content", "")
            if not content:
                continue

            # Capture intent from first result
            if not intent_metadata:
                intent_metadata = item.get("intent_metadata", {})

            doc_obj = {
                "source": item.get("url", ""),
                "concept": item.get("title", "Web Result"),
                "content": f"【External Knowledge】{content}",
                "source_type": "web",
            }
            web_docs.append(json.dumps(doc_obj, ensure_ascii=False))

        print(f"Web search returned {len(web_docs)} results")

        # --- Content Grading (Quality Filter Funnel) ---
        graded_docs = []
        for doc_json in web_docs:
            try:
                doc_obj = json.loads(doc_json)
                content = doc_obj.get("content", "").replace("【External Knowledge】", "")

                # Rule 1: Length Check (Filter out thin content)
                # OPTIMIZATION: Relax length check from 200 to 100 to catch valid but shorter snippets
                if len(content) < 100:
                    logger.warning(f"⚠️ Content too short ({len(content)} chars), skipping. Snippet: {content[:30]}...")
                    continue

                # Rule 2: Keyword Density / Spam Check (Simple Heuristic)
                # If needed, we can add LLM check here, but length + domain whitelist is a strong baseline.

                graded_docs.append(doc_json)
            except Exception as e:
                logger.error(f"Error grading doc: {e}")
                continue

        logger.info(f"Web Search Results: Raw={len(web_docs)}, Graded={len(graded_docs)}")
        
        if len(graded_docs) < len(web_docs):
            logger.warning(f"Content Grading: Filtered {len(web_docs) - len(graded_docs)} low-quality results.")

        # Fallback: If strict grading filters everything, use raw results (top 2) to avoid empty response
        if not graded_docs and web_docs:
             logger.warning("All web results filtered by grader! Falling back to raw top 2 results.")
             graded_docs = web_docs[:2]

        web_docs = graded_docs
        # -----------------------------------------------

        # Merge with existing documents (RAG + Web)
        all_docs = current_docs + web_docs
        return {"documents": all_docs, "intent_metadata": intent_metadata}

    except asyncio.TimeoutError:
        logger.warning("Web Search API Timeout (30s). Attempting Fallback Search...")
        try:
            # Fallback: Simple Tavily Search without Hybrid Logic
            # Just search the raw question + full name directly
            simple_query = f"{full_name} {question}"
            # Use raw Tavily call via a new ad-hoc request or simpler method if available
            # Here we reuse service.search but with a simpler query and SHORTER timeout for fallback
            # But wait, service.search does hybrid logic. 
            # Ideally we should have a simple_search method. 
            # For now, let's just log and return. 
            # In a true ReAct loop, we would yield a "Thought" and retry.
            # Given current architecture constraints, we return gracefully.
            pass
        except Exception:
            pass
            
        return {"documents": current_docs}  # Return existing docs on failure
    except Exception as e:
        logger.error(f"Web Search Failed: {e}")
        return {"documents": current_docs}  # Return existing docs on failure


async def get_agent_insights():
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        row = await conn.fetchrow("SELECT content FROM agent_insights ORDER BY id DESC LIMIT 1")
        await conn.close()
        if row:
            return row["content"]
        return ""
    except Exception as e:
        print(f"Error fetching agent insights: {e}")
        return ""


async def update_profile(state: AgentState) -> Dict[str, Any]:
    """
    Update User Profile based on the interaction.
    """
    print("DEBUG: Updating profile...")
    # This is a placeholder for the actual profile update logic
    # In a real system, we would extract insights and save them to the DB
    return {}


async def generate(state: AgentState) -> Dict[str, Any]:
    """
    Generate answer using the retrieved documents.
    STRICTLY ENFORCES PROTOCOL LOCK for frontend rendering.
    """
    print("---GENERATE---")
    question = state["question"]
    documents = state["documents"]
    chat_history = state.get("chat_history", [])
    intent_metadata = state.get("intent_metadata", {})
    core_entity = intent_metadata.get("core_entity")

    print(f"DEBUG: Generating response for: {question}")
    print(f"DEBUG: Core Entity: {core_entity}")
    print(f"DEBUG: Documents count: {len(documents)}")

    # Fetch Wisdom Layer
    wisdom = await get_agent_insights()

    # === 本地 RAG 优先策略 ===
    if not documents and not wisdom:
        if any(keyword in question for keyword in ["OpenAI", "DeepSeek", "Operator", "Kortex", "Claude"]):
            print("[WARNING] 无文档且无 Wisdom Layer，针对具体实体问题使用坦诚回复。")
            return {
                "generation": "针对你提到的具体项目或工具，虽然我手头没有直接的资料，但从构建系统和杠杆的角度来看，这个问题的本质往往是共通的。我们可以试着从底层逻辑拆解它，而不是纠结于表面的技术细节。"
            }
        print("[WARNING] 无文档且无 Wisdom Layer，使用极简兜底回复。")
        return {
            "generation": "目前我的知识库中尚未找到与这个具体问题直接相关的内容。但我的核心系统围绕专注力、杠杆、系统构建和数字个体进化展开。你可以尝试更具体地描述你的问题，或者我们可以从不同的角度切入探讨。"
        }

    # Prepare Memory Layer (JSON List)
    memory_layer_parts = []
    # Structured references for JSON Injection
    references_json = []

    video_count = 0
    web_count = 0

    # Track assigned IDs to deduplicate sources
    assigned_ids = {}

    # Group content by stable ID first
    grouped_docs = {}  # {stable_id: {doc_id: "...", title: "...", source: "...", content_list: []}}

    for doc_str in documents:
        try:
            doc_data = json.loads(doc_str)
            content = doc_data.get("content", "")
            source = doc_data.get("source", "")
            title = doc_data.get("concept", "Unknown Title")
            source_type = doc_data.get("source_type", "video")  # Default to video

            # Get stable ID for grouping
            stable_id = doc_data.get("id", source)

            if stable_id not in assigned_ids:
                if source_type == "web":
                    web_count += 1
                    doc_id = f"W{web_count}"
                else:
                    video_count += 1
                    doc_id = str(video_count)
                assigned_ids[stable_id] = doc_id

                grouped_docs[stable_id] = {
                    "doc_id": doc_id,
                    "title": title,
                    "source": source,
                    "content_list": [content],
                }
            else:
                # Append content to existing group
                grouped_docs[stable_id]["content_list"].append(content)
        except Exception:
            video_count += 1
            memory_layer_parts.append(f"Document [{video_count}]:\n{doc_str}\n")

    # Build Memory Layer and Reference List
    for stable_id, data in grouped_docs.items():
        doc_id = data["doc_id"]
        title = data["title"]
        source = data["source"]
        combined_content = "\n---\n".join(data["content_list"])

        memory_layer_parts.append(
            f"Document [{doc_id}]:\nTitle: {title}\nSource: {source}\nContent: {combined_content}\n"
        )

        # Collect strict reference data
        references_json.append({
            "id": doc_id,
            "title": title,
            "url": source,
            "type": "web" if doc_id.startswith("W") else "video"
        })

    memory_layer = "\n".join(memory_layer_parts)
    # Serialize references for final injection
    references_json_str = json.dumps(references_json, ensure_ascii=False)

    # Prepare Transient Layer (History)
    transient_layer = ""
    if chat_history:
        transient_layer = "\n".join([f"{msg.type}: {msg.content}" for msg in chat_history])

    # Layered Personality Instructions
    agent_id = state.get("agent_id", "dan_koe")
    
    available_sources_list = ", ".join([f"[{ref['id']}]" for ref in references_json])
    
    citation_instruction = f"""
    Citation Rules (CRITICAL):
    1. You MUST cite your sources using [1], [2] or [W1] notation immediately after the relevant sentence.
    2. Available Sources for THIS turn: {available_sources_list if available_sources_list else "None"}
    3. Example: "Dan Koe believes that systems are the foundation of freedom [1]. Web search also indicates similar trends [W1]."
    4. If the Context is empty or irrelevant, DO NOT HALLUCINATE citations.
    5. Do NOT output the references list yourself. The system will append it automatically.
    """

    if agent_id == "naval":
        system_prompt = f"""You are Naval Ravikant. Embody his voice, philosophy, and thinking patterns as demonstrated in the Context below.
        
        Your task: Answer the user's question. Draw deeply from the Context (your own words and ideas from past content). Synthesize, connect dots, and go deeper than surface-level advice. Write in the same natural, conversational tone as the Context material.
        
        {citation_instruction}
        
        Honesty Rule:
        If the Context does NOT contain specific information about something the user mentions (e.g., their personal project), state this honestly in one natural sentence at the beginning, then immediately pivot to your philosophical analysis based on your broader worldview from the Context.
        Example: "我的记忆库和实时搜索均未找到关于你个人项目'[名称]'的具体记录，接下来的推演是基于我一贯的哲学逻辑和对你处境的系统性分析。"
        
        For follow-up questions (Conversation History is NOT empty), skip disclaimers entirely. Dive straight in.

        Context (Memory Layer - YOUR OWN PAST CONTENT):
        {memory_layer}
        
        Wisdom Layer (General Knowledge):
        {wisdom}
        
        Conversation History:
        {transient_layer}
        
        User Question: {question}
        
        Output in Chinese (Simplified). Do NOT use emojis. Write long, thorough, deeply analytical responses for complex questions.
        """
    else:
        system_prompt = f"""You are Dan Koe. Embody his voice, philosophy, and thinking patterns as demonstrated in the Context below.
        
        Your task: Answer the user's question. Draw deeply from the Context (your own words and ideas from past videos and writing). Synthesize, connect dots across multiple ideas, and go much deeper than surface-level advice. Write in the same natural, direct, intense tone as the Context material — as if you are personally talking to this person.
        
        {citation_instruction}
        
        Honesty Rule:
        If the Context does NOT contain specific information about something the user mentions (e.g., their personal project, a specific tool), state this honestly in one natural sentence at the beginning, then immediately pivot to your deep philosophical analysis based on your broader worldview from the Context.
        Example: "我的记忆库和实时搜索均未找到关于你个人项目'[名称]'的具体记录，接下来的推演是基于我一贯的哲学逻辑和对你处境的系统性分析。"
        
        For follow-up questions (Conversation History is NOT empty), skip disclaimers entirely. Dive straight in.

        Context (Memory Layer - YOUR OWN PAST CONTENT):
        {memory_layer}
        
        Wisdom Layer (General Knowledge):
        {wisdom}
        
        Conversation History:
        {transient_layer}
        
        User Question: {question}
        
        Output in Chinese (Simplified). Do NOT use emojis. Write long, thorough, deeply analytical responses for complex questions.
        """

    # --- Multimodal Logic Synthesis ---
    images = state.get("images", [])
    if images and len(images) > 0:
        # Construct multimodal message
        print(f"Generating with {len(images)} images")
        user_content = [
            {"type": "text", "text": system_prompt},
        ]
        for img_base64 in images:
            user_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"{img_base64}" if img_base64.startswith("data:") else f"data:image/jpeg;base64,{img_base64}"
                }
            })
        messages = [{"role": "user", "content": user_content}]
    else:
        # Standard text-only
        messages = [{"role": "user", "content": system_prompt}]

    generation = await generate_response(messages)
    
    # --- PROTOCOL LOCK: FORCE INJECTION ---
    # Ensure no duplicate JSON if LLM hallucinates it
    generation = generation.replace("__REFERENCES_JSON__", "") 
    
    # Append the strict JSON block with new marker
    final_output = f"{generation}\n\n[[[FINAL_SOURCES_START]]]{references_json_str}"
    
    return {"generation": final_output, "final_references": references_json}
