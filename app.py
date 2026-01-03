import streamlit as st
import os
from agent.graph import app
from agent.nodes import get_llm
from agent.chat import get_chat_response
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Page Config
st.set_page_config(page_title="AI Travel Planner", page_icon="✈️", layout="wide")

# Custom CSS
st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #fafafa; }
    .stButton>button { background-color: #ff4b4b; color: white; border-radius: 20px; padding: 10px 24px; border: none; }
    .success-box { padding: 1rem; border-radius: 0.5rem; background-color: #1c2e2e; border: 1px solid #4caf50; }
</style>
""", unsafe_allow_html=True)

# Helper for Dynamic City Search
def suggest_cities(query):
    llm = get_llm()
    msg = HumanMessage(content=f"Suggest 5 specific travel destinations (City, Country) based on this theme/query: '{query}'. Return ONLY a comma-separated list of strings.")
    res = llm.invoke([msg])
    return [c.strip() for c in res.content.split(',')]

# Sidebar Settings
with st.sidebar:
    st.title("Settings")
    if os.environ.get("LLM_PROVIDER") == "Groq":
        st.success(f"Using Groq (Llama 3)")
    else:
        if os.environ.get("OPENAI_API_KEY"):
            st.success("OpenAI Key loaded")
        else:
            openai_key = st.text_input("OpenAI API Key", type="password")
            if openai_key:
                os.environ["OPENAI_API_KEY"] = openai_key

    if os.environ.get("TAVILY_API_KEY"):
        st.success("Tavily Key loaded")
    else:
        tavily_key = st.text_input("Tavily API Key", type="password")
        if tavily_key:
            os.environ["TAVILY_API_KEY"] = tavily_key
            
    st.markdown("---")
    st.info("💡 **Tip**: Be specific with your budget for better validation.")

# Session State for Cities
if "suggested_cities" not in st.session_state:
    st.session_state.suggested_cities = ["Tokyo, Japan", "Paris, France", "New York, USA", "London, UK", "Rome, Italy"]

# Session State for Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

if "final_itinerary" not in st.session_state:
    st.session_state.final_itinerary = None

# Main Layout
st.title("✈️ AI Travel Agent")
st.markdown("I plan your perfect trip, iteratively refining it until it matches your budget.")

# --- STEP 1: DESTINATION DISCOVERY ---
st.subheader("1. Where to?")
search_mode = st.radio("Destination Mode", ["Select from List", "Let AI Suggest Locations"], horizontal=True)

final_destination = "Tokyo, Japan" # Default

if search_mode == "Let AI Suggest Locations":
    col_search, col_btn = st.columns([3, 1])
    with col_search:
        query = st.text_input("Describe your ideal trip", placeholder="e.g. Cheap beach vacation in Asia with great food")
    with col_btn:
        st.write("") # spacer
        st.write("") 
        if st.button("🔍 Find Cities"):
            with st.spinner("Searching for perfect spots..."):
                try:
                    found = suggest_cities(query)
                    st.session_state.suggested_cities = found
                    st.success(f"Found {len(found)} destinations!")
                except Exception as e:
                    st.error(f"Error fetching suggestions: {e}")

    final_destination = st.selectbox("Select Suggested Destination", st.session_state.suggested_cities)

else:
    # Manual / Classic Mode
    DEPARTURE_CITIES = ["New York, USA", "London, UK", "Los Angeles, USA", "San Francisco, USA", "Singapore", "Mumbai, India", "Delhi, India", "Sydney, Australia", "Berlin, Germany", "Toronto, Canada", "Other"]
    
    c1, c2 = st.columns(2)
    with c1:
        origin_select = st.selectbox("From (Origin)", DEPARTURE_CITIES)
        origin = st.text_input("Enter Departure City") if origin_select == "Other" else origin_select
    with c2:
        # We use a combined list or simple text
        dest_input = st.selectbox("To (Destination)", st.session_state.suggested_cities + ["Other"])
        final_destination = st.text_input("Enter Destination") if dest_input == "Other" else dest_input

# --- STEP 2: DETAILS ---
st.subheader("2. Trip Details")
d1, d2 = st.columns(2)

with d1:
    dates = st.text_input("Dates", "Oct 1 - Oct 7")
    interests = st.multiselect("Interests", ["Food", "History", "Nature", "Shopping", "Adventure", "Relaxation"], ["Food", "History"])

with d2:
    # Enhanced Budget Input
    b_col1, b_col2 = st.columns([2, 1])
    with b_col1:
        budget_amount = st.number_input("Budget Amount", min_value=100, value=2000, step=100)
    with b_col2:
        currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "INR", "JPY"])
    
    final_budget = f"{budget_amount} {currency}"

# --- EXECUTION ---

# --- EXECUTION ---
if st.button("🚀 Plan My Trip"):
    # Reset Chat History on new plan
    st.session_state.messages = []
    st.session_state.final_itinerary = None
    
    # Check Logic
    has_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY")
    orig = origin if search_mode == "Select from List" else "Your Location" 
    
    if not has_key or not os.environ.get("TAVILY_API_KEY"):
        st.error("Please provide API Keys in the sidebar or .env!")
    else:
        status_container = st.empty()
        result_container = st.container()
        
        initial_state = {
            "request": f"Trip to {final_destination} from {orig} on {dates}. Budget: {final_budget}.",
            "origin": orig,
            "destination": final_destination,
            "dates": dates,
            "budget": final_budget,
            "interests": interests,
            "revision_number": 0
        }
        
        status_container.info("Initializing Agent...")
        
        try:
            events = app.stream(initial_state)
            for event in events:
                for key, value in event.items():
                    if key == "planner":
                        status_container.write("📅 **Planning**: Generating search queries...")
                    elif key == "researcher":
                        status_container.write("🔎 **Researching**: Checking real-time availability...")
                    elif key == "drafter":
                        status_container.write("✍️ **Drafting**: Writing itinerary...")
                    elif key == "validator":
                        critique = value.get("critique")
                        if critique:
                            if "INFEASIBLE" in critique:
                                status_container.error("❌ **Budget Check Failed**")
                                result_container.markdown(value.get("final_itinerary"))
                            else:
                                status_container.warning(f"🤔 **Refining**: {critique}")
                        else:
                             status_container.success("✅ **Validated**: Itinerary approved!")
                             st.session_state.final_itinerary = value.get("final_itinerary")
                             result_container.markdown(st.session_state.final_itinerary)
                             
        except Exception as e:
            st.error(f"An error occurred: {e}")

# --- DISPLAY ITINERARY ---
if st.session_state.final_itinerary:
    st.markdown(st.session_state.final_itinerary)

# --- CHAT INTERFACE ---
if st.session_state.final_itinerary:
    st.markdown("---")
    st.subheader("💬 Ask about your trip")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("Ask a follow-up question (e.g., 'What's the weather?', 'Find veg food nearby')"):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate Agent Response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = get_chat_response(st.session_state.messages, st.session_state.final_itinerary)
                st.markdown(response)
        
        # Add assistant response to history
        st.session_state.messages.append({"role": "assistant", "content": response})


