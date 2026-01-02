from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from .state import TravelState
import json
import os

def get_llm():
    provider = os.environ.get("LLM_PROVIDER", "OpenAI")
    if provider == "Groq":
        return ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    else:
        return ChatOpenAI(model="gpt-4o-mini", temperature=0)

def get_tool():
    return TavilySearchResults(max_results=3)

def planner_node(state: TravelState):
    """Generates a plan of search queries based on the user request."""
    print("--- PLANNER NODE ---")
    llm = get_llm()
    messages = [
        SystemMessage(content="You are a travel planning assistant. Analyze the user's request and generate a list of 3-5 specific search queries to gather necessary information (flights, hotels, weather, attractions). Return ONLY a JSON list of strings."),
        HumanMessage(content=f"Origin: {state['origin']}\nDestination: {state['destination']}\nDates: {state['dates']}\nBudget: {state['budget']}\nInterests: {state['interests']}")
    ]
    response = llm.invoke(messages)
    try:
        queries = json.loads(response.content)
    except:
        # Fallback if JSON parsing fails - simple heuristic or retry
        queries = [f"flights from {state['origin']} to {state['destination']} {state['dates']}", f"cheap hotels in {state['destination']}", f"top things to do in {state['destination']}"]
    
    return {"plan": queries, "revision_number": state.get("revision_number", 0) + 1}

def researcher_node(state: TravelState):
    """Executes the search queries."""
    print("--- RESEARCHER NODE ---")
    tool = get_tool()
    queries = state["plan"]
    results = []
    
    for q in queries:
        try:
            res = tool.invoke(q)
            # Tavily returns a list of dictionaries. We'll stringify them for simplicity.
            results.append(f"Query: {q}\nResults: {str(res)}\n")
        except Exception as e:
             results.append(f"Query: {q}\nError: {str(e)}\n")
             
    return {"search_results": results}

def drafter_node(state: TravelState):
    """Synthesizes research into an itinerary."""
    print("--- DRAFTER NODE ---")
    llm = get_llm()
    research_text = "\n\n".join(state["search_results"])
    
    prompt = f"""
    You are a travel agent. Create a detailed day-by-day itinerary for a trip from {state['origin']} to {state['destination']}.
    
    Constraints:
    - Dates: {state['dates']}
    - Budget: {state['budget']}
    - Interests: {', '.join(state['interests'])}
    
    Here is the research data you found:
    {research_text}
    
    Specific Feedback (if any) from previous validation:
    {state.get('critique', 'None')}
    
    Produce a professional Markdown formatted itinerary. Include estimated costs where found.
    """
    
    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    return {"draft": response.content}

def validator_node(state: TravelState):
    """Checks if the itinerary meets the budget and requirements."""
    print("--- VALIDATOR NODE ---")
    llm = get_llm()
    
    prompt = f"""
    Review this itinerary for {state['destination']}:
    
    {state['draft']}
    
    User Budget: {state['budget']}
    User Interests: {state['interests']}
    
    1. Calculate the rough total cost of the itinerary based on the mentioned prices.
    2. Compare it to the User Budget.
    
    Is this itinerary feasible within the budget?
    If YES, return "VALID".
    If NO, return "INFEASIBLE: <Estimate Total Cost> - <Reason>". 
    Example: "INFEASIBLE: $2500 - Flight costs alone are $2000, leaving too little for hotels."
    """
    
    messages = [HumanMessage(content=prompt)]
    response = llm.invoke(messages)
    
    content = response.content
    if "VALID" in content:
        return {"final_itinerary": state['draft'], "critique": None}
    elif "INFEASIBLE" in content:
        # We return the critique. The graph decision logic might need to handle this "Fatal" error or just report it.
        # For this agent, we will let the UI display the error.
        return {"critique": content, "final_itinerary": f"### ⚠️ Budget Issue\n\n{content}\n\n**Please increase your budget and try again.**"}
    else:
        return {"critique": content}
