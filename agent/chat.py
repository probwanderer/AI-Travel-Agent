from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_community.tools.tavily_search import TavilySearchResults
import os

def get_chat_llm():
    """Returns the LLM instance based on environment configuration."""
    provider = os.environ.get("LLM_PROVIDER", "OpenAI")
    model = os.environ.get("LLM_MODEL")
    
    if provider == "Groq":
        # Using a versatile model for chat
        return ChatGroq(model=model or "llama-3.3-70b-versatile", temperature=0.7)
    else:
        return ChatOpenAI(model=model or "gpt-4o-mini", temperature=0.7)

def get_chat_response(messages, itinerary_context):
    """
    Generates a response to the user's follow-up question.
    
    Args:
        messages: List of message dicts (from streamlit session_state).
        itinerary_context: The string content of the generated itinerary.
    """
    llm = get_chat_llm()
    tool = TavilySearchResults(max_results=3)
    
    # Enable the LLM to use the search tool
    llm_with_tools = llm.bind_tools([tool])
    
    # Construct history for LangChain
    lc_messages = []
    
    # 1. System Prompt with Context
    system_text = f"""You are a helpful travel assistant. 
    The user has just generated a travel itinerary (below).
    Your goal is to answer follow-up questions about this trip, search for extra details (weather, specific restaurants, events), 
    and provide helpful advice.
    
    --- ITINERARY CONTEXT ---
    {itinerary_context}
    -------------------------
    
    If the user asks for something not in the itinerary, use your search tool to find real-time info.
    Be concise and friendly.
    """
    lc_messages.append(SystemMessage(content=system_text))
    
    # 2. Add History
    for msg in messages:
        if msg["role"] == "user":
            lc_messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            lc_messages.append(AIMessage(content=msg["content"]))
            
    # 3. Invoke
    # We use a simple invoke. For a real agent loop, we'd use LangGraph prebuilt agent, 
    # but strictly binding tools and letting the model decide to call them is often enough for simple Q&A.
    # However, to actually EXECUTE the tool call, we need a small loop or use LangChain's existing agent features.
    # To keep dependencies minimal and consistent with the "Scratch" nature, we'll do a simple "call -> if tool -> exec -> call again" loop.
    
    response = llm_with_tools.invoke(lc_messages)
    
    if response.tool_calls:
        # If the model wants to use a tool
        tool_call = response.tool_calls[0] # Handle single tool for simplicity
        if tool_call["name"] == "tavily_search_results_json":
            # Execute tool
            tool_msg = f"Searching for: {tool_call['args']}"
            print(tool_msg) 
            try:
                search_res = tool.invoke(tool_call['args'])
                # Feed result back
                lc_messages.append(response) # The tool call request
                from langchain_core.messages import ToolMessage
                lc_messages.append(ToolMessage(tool_call_id=tool_call['id'], content=str(search_res)))
                
                # Final answer
                final_response = llm_with_tools.invoke(lc_messages)
                return final_response.content
            except Exception as e:
                return f"I tried to search but encountered an error: {e}"
    
    return response.content
