import streamlit as st
import os
from agent.graph import app
from agent.nodes import get_llm
from agent.chat import get_chat_response
from langchain_core.messages import HumanMessage
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta

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

# --- API HELPERS ---
@st.cache_data(ttl=3600*24) # Cache for 24h
def get_all_countries():
    try:
        url = "https://countriesnow.space/api/v0.1/countries/positions"
        response = requests.get(url)
        data = response.json()
        if not data.get("error"):
            return sorted([item["name"] for item in data["data"]])
        return []
    except:
        return []

@st.cache_data(ttl=3600*24)
def get_cities_for_country(country):
    try:
        url = "https://countriesnow.space/api/v0.1/countries/cities"
        response = requests.post(url, json={"country": country})
        data = response.json()
        if not data.get("error"):
            return sorted(data["data"])
        return []
    except:
        return []

# Sidebar Settings
with st.sidebar:
    st.title("🔑 API Keys")
    st.markdown("""
    To use this app, you need to provide your own API keys.
    The keys are not stored and are only used for this session.
    """)
    
    # Provider Selection
    provider = st.radio("Select LLM Provider", ["OpenAI", "Groq"], horizontal=True)
    
    if provider == "Groq":
        os.environ["LLM_PROVIDER"] = "Groq"
        if os.environ.get("GROQ_API_KEY"):
            st.success("✅ Groq Key loaded from env")
        else:
            groq_key = st.text_input("Groq API Key", type="password", help="Get a free key: https://console.groq.com/keys")
            if groq_key:
                os.environ["GROQ_API_KEY"] = groq_key
            else:
                st.warning("⚠️ Groq Key missing")
        
        # Groq Models
        groq_model = st.selectbox("Select Model", ["llama-3.3-70b-versatile", "llama3-70b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"])
        os.environ["LLM_MODEL"] = groq_model
    else:
        os.environ["LLM_PROVIDER"] = "OpenAI"
        if os.environ.get("OPENAI_API_KEY"):
            st.success("✅ OpenAI Key loaded from env")
        else:
            openai_key = st.text_input("OpenAI API Key", type="password", help="Get key: https://platform.openai.com/api-keys")
            if openai_key:
                os.environ["OPENAI_API_KEY"] = openai_key
            else:
                st.warning("⚠️ OpenAI Key missing")
        
        # OpenAI Models
        openai_model = st.selectbox("Select Model", ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"])
        os.environ["LLM_MODEL"] = openai_model

    st.markdown("---")
    st.markdown("### Search Provider")
    if os.environ.get("TAVILY_API_KEY"):
        st.success("✅ Tavily Key loaded from env")
    else:
        tavily_key = st.text_input("Tavily API Key", type="password", help="Get free key: https://tavily.com/")
        if tavily_key:
            os.environ["TAVILY_API_KEY"] = tavily_key
        else:
            st.warning("⚠️ Tavily Key missing (Required for research)")
            
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
    # Manual / Classic Mode (Dynamic)
    col1, col2 = st.columns(2)
    
    # --- Origin Selection ---
    with col1:
        st.markdown("### From (Origin)")
        countries = get_all_countries()
        if not countries:
            # Fallback if API fails
            origin = st.text_input("Enter Origin City")
        else:
            o_country = st.selectbox("Select Country", countries, key="o_country")
            o_cities = get_cities_for_country(o_country)
            
            if o_cities:
                o_city = st.selectbox("Select City", o_cities + ["Other"], key="o_city")
                if o_city == "Other":
                    origin = st.text_input("Enter Origin City", key="o_custom")
                else:
                    origin = f"{o_city}, {o_country}"
            else:
                 origin = st.text_input("Enter Origin City", key="o_fallback")

    # --- Destination Selection ---
    with col2:
        st.markdown("### To (Destination)")
        # Re-use cached countries
        if not countries:
             final_destination = st.text_input("Enter Destination City")
        else:
            d_country = st.selectbox("Select Country", countries, key="d_country", index=min(10, len(countries)-1)) # Default to mixed
            d_cities = get_cities_for_country(d_country)
            
            if d_cities:
                d_city = st.selectbox("Select City", d_cities + ["Other"], key="d_city")
                if d_city == "Other":
                     final_destination = st.text_input("Enter Destination City", key="d_custom")
                else:
                    final_destination = f"{d_city}, {d_country}"
            else:
                final_destination = st.text_input("Enter Destination City", key="d_fallback")

# --- STEP 2: DETAILS ---
st.subheader("2. Trip Details")
d1, d2 = st.columns(2)

with d1:
    today = datetime.today()
    next_week = today + timedelta(days=7)
    date_range = st.date_input("Dates", value=(today, next_week), min_value=today)
    
    # helper to format dates for the agent
    if isinstance(date_range, tuple) and len(date_range) == 2:
        dates = f"{date_range[0].strftime('%b %d')} - {date_range[1].strftime('%b %d')}"
    elif isinstance(date_range, tuple) and len(date_range) == 1:
         dates = f"{date_range[0].strftime('%b %d')}"
    else:
        dates = str(date_range)
        
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


