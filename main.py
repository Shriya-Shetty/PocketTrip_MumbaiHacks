import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import json
from datetime import datetime
import os
import hashlib
import string
import random
import time

# Page config
st.set_page_config(
    page_title="PocketTrip",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS (unchanged)
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        padding: 1rem 0;
    }
    .room-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    .plan-card {
        background: #f8f9fa;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 1rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        color: #333;
    }
    .vote-badge {
        background: #ffd700;
        color: #333;
        padding: 0.3rem 0.8rem;
        border-radius: 15px;
        font-weight: bold;
        display: inline-block;
    }
    .member-badge {
        background: #e7f3ff;
        padding: 0.4rem 0.8rem;
        border-radius: 8px;
        margin: 0.2rem;
        display: inline-block;
        color: #333;
    }
    .chat-user {
        background: #e3f2fd;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        color: #1565c0;
        border-left: 4px solid #1976d2;
    }
    .chat-assistant {
        background: #f3e5f5;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        color: #4a148c;
        border-left: 4px solid #7b1fa2;
    }
    .split-summary {
        background: #fff3e0;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        color: #e65100;
        border: 2px solid #ff9800;
    }
    .stButton>button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.75rem 2rem;
        border-radius: 25px;
        font-weight: bold;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Initialize Supabase
# ---------------------------
@st.cache_resource
def init_supabase():
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            st.error("⚠️ Supabase credentials not found. Please configure SUPABASE_URL and SUPABASE_KEY environment variables.")
            st.stop()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {e}")
        st.stop()

# ---------------------------
# Initialize Gemini with fallback + model selection
# ---------------------------
@st.cache_resource
def init_gemini():
    """
    Reads GEMINI_API_KEY and optional GEMINI_MODEL env var.
    If the requested model fails (quota or other), auto-fallback to gemini-1.5-flash.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    requested_model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")  # default to free-tier compatible
    if not api_key:
        st.error("⚠️ Gemini API key not found. Please configure GEMINI_API_KEY environment variable.")
        st.stop()

    # configure global
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"Error configuring Gemini client: {e}")
        st.stop()

    # try to instantiate the requested model; if it fails, fallback
    try_models = [requested_model]
    if requested_model != "gemini-1.5-flash":
        try_models.append("gemini-1.5-flash")

    last_error = None
    for m in try_models:
        try:
            model_obj = genai.GenerativeModel(m)
            st.sidebar.info(f"Using Gemini model: {m}")
            return model_obj
        except Exception as e:
            last_error = e
            # show short warning and try next
            st.sidebar.warning(f"Could not initialize model {m}: {str(e)}. Trying fallback...")
            time.sleep(0.5)

    # if none succeeded, show error and stop
    st.error(f"Failed to initialize Gemini model. Last error: {last_error}")
    st.stop()


# Retry helper for generate_content
def call_generate_with_retries(model_obj, prompt, max_retries=3, initial_delay=2):
    """
    Calls model.generate_content(prompt) with simple exponential backoff for transient errors (429, rate limits).
    Returns the response object or raises the last exception.
    """
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            response = model_obj.generate_content(prompt)
            return response
        except Exception as e:
            # If it's a quota/429 like error, retry with backoff, otherwise bubble up after last try
            msg = str(e).lower()
            if attempt < max_retries and ("quota" in msg or "429" in msg or "rate" in msg):
                st.sidebar.info(f"Rate/Quota error detected, retrying in {delay}s... (attempt {attempt}/{max_retries})")
                time.sleep(delay)
                delay *= 2
                continue
            # last attempt or non-retriable error
            raise

# Initialize clients
supabase: Client = init_supabase()
model = init_gemini()

# ---------------------------
# Helper Functions (unchanged logic, small tweaks)
# ---------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def authenticate_user(username, password):
    try:
        response = supabase.table('users').select('*').eq('username', username).execute()
        if response.data and len(response.data) > 0:
            user = response.data[0]
            if user['password'] == hash_password(password):
                return user
        return None
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None

def create_user(username, password, email):
    try:
        data = {
            'username': username,
            'password': hash_password(password),
            'email': email,
            'created_at': datetime.now().isoformat()
        }
        response = supabase.table('users').insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"User creation error: {e}")
        return None

def create_room(creator_id, room_name, current_location):
    try:
        room_code = generate_room_code()
        data = {
            'room_code': room_code,
            'room_name': room_name,
            'creator_id': creator_id,
            'current_location': current_location,
            'members': json.dumps([creator_id]),
            'status': 'active',
            'created_at': datetime.now().isoformat()
        }
        response = supabase.table('rooms').insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Room creation error: {e}")
        return None

def join_room(room_code, user_id):
    try:
        response = supabase.table('rooms').select('*').eq('room_code', room_code).execute()
        if response.data:
            room = response.data[0]
            members = json.loads(room['members'])
            if user_id not in members:
                members.append(user_id)
                supabase.table('rooms').update({'members': json.dumps(members)}).eq('id', room['id']).execute()
            return room
        return None
    except Exception as e:
        st.error(f"Error joining room: {e}")
        return None

def get_user_rooms(user_id):
    try:
        response = supabase.table('rooms').select('*').order('created_at', desc=True).execute()
        if response.data:
            user_rooms = [room for room in response.data if user_id in json.loads(room['members'])]
            return user_rooms
        return []
    except Exception as e:
        st.error(f"Error fetching rooms: {e}")
        return []

def get_room_members(room_id):
    try:
        room = supabase.table('rooms').select('members').eq('id', room_id).execute()
        if room.data:
            member_ids = json.loads(room.data[0]['members'])
            members = []
            for mid in member_ids:
                user = supabase.table('users').select('id, username').eq('id', mid).execute()
                if user.data:
                    members.append(user.data[0])
            return members
        return []
    except Exception as e:
        return []

def save_day_plan(user_id, room_id, plan_data):
    try:
        data = {
            'user_id': user_id,
            'room_id': room_id,
            'plan_data': json.dumps(plan_data),
            'votes': 0,
            'created_at': datetime.now().isoformat()
        }
        response = supabase.table('day_plans').insert(data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        st.error(f"Error saving plan: {e}")
        return None

def get_room_plans(room_id):
    try:
        response = supabase.table('day_plans').select('*').eq('room_id', room_id).order('created_at', desc=True).execute()
        if response.data:
            for plan in response.data:
                user = supabase.table('users').select('username').eq('id', plan['user_id']).execute()
                plan['username'] = user.data[0]['username'] if user.data else 'Unknown'
        return response.data
    except Exception as e:
        st.error(f"Error fetching plans: {e}")
        return []

def vote_plan(plan_id, user_id):
    try:
        vote_check = supabase.table('plan_votes').select('*').eq('plan_id', plan_id).eq('user_id', user_id).execute()
        if vote_check.data:
            st.warning("You already voted for this plan!")
            return False
        
        supabase.table('plan_votes').insert({'plan_id': plan_id, 'user_id': user_id}).execute()
        
        plan = supabase.table('day_plans').select('votes').eq('id', plan_id).execute()
        current_votes = plan.data[0]['votes'] if plan.data else 0
        supabase.table('day_plans').update({'votes': current_votes + 1}).eq('id', plan_id).execute()
        return True
    except Exception as e:
        st.error(f"Error voting: {e}")
        return False

def save_expense_message(room_id, user_id, message, response):
    try:
        data = {
            'room_id': room_id,
            'user_id': user_id,
            'message': message,
            'response': response,
            'created_at': datetime.now().isoformat()
        }
        supabase.table('split_expenses').insert(data).execute()
    except Exception as e:
        st.error(f"Error saving expense: {e}")

def get_room_expenses(room_id):
    try:
        response = supabase.table('split_expenses').select('*').eq('room_id', room_id).order('created_at', desc=False).execute()
        if response.data:
            for exp in response.data:
                user = supabase.table('users').select('username').eq('id', exp['user_id']).execute()
                exp['username'] = user.data[0]['username'] if user.data else 'Unknown'
        return response.data
    except Exception as e:
        return []

# ---------------------------
# AI-driven functions with retries and safe fallbacks
# ---------------------------
def generate_day_plan(current_location, radius, budget, interests, additional_info):
    # Ensure interests is a list
    if not isinstance(interests, list):
        interests = [interests]

    prompt = f"""
    Create a detailed ONE-DAY trip plan with these parameters:
    Current Location: {current_location}
    Search Radius: {radius} km
    Budget: ₹{budget}
    Interests: {', '.join(interests)}
    Additional Info: {additional_info}
    
    Provide a JSON response with realistic costs in Indian Rupees (₹):
    1. Exact destinations within the radius with addresses
    2. Time-based itinerary (morning, afternoon, evening)
    3. Detailed budget breakdown including TRAVEL COSTS (cab/auto/metro fares between locations)
    4. Precise cost estimates for each destination
    5. Travel time and transport costs between locations
    6. Practical tips
    
    Format as valid JSON:
    {{
        "destinations": [
            {{
                "name": "Place Name",
                "address": "Full address",
                "distance_km": 15,
                "category": "nature/food/culture",
                "time_slot": "morning/afternoon/evening",
                "duration": "2 hours",
                "activities": ["Activity 1", "Activity 2"],
                "costs": {{
                    "entry": 200,
                    "food": 300,
                    "transport": 150,
                    "misc": 100
                }},
                "total_cost": 750,
                "transport_from_previous": {{
                    "mode": "Metro/Cab/Auto",
                    "cost": 150,
                    "time": "30 mins"
                }}
            }}
        ],
        "itinerary": {{
            "morning": ["9:00 AM - Activity 1", "11:00 AM - Activity 2"],
            "afternoon": ["1:00 PM - Lunch", "3:00 PM - Activity 3"],
            "evening": ["6:00 PM - Activity 4", "8:00 PM - Dinner"]
        }},
        "total_budget": {{
            "transport": 500,
            "food": 800,
            "activities": 600,
            "miscellaneous": 200,
            "total": 2100
        }},
        "tips": ["Tip 1", "Tip 2"]
    }}
    
    Make sure to include realistic Indian prices and transport costs between each location.
    """

    try:
        resp = call_generate_with_retries(model, prompt)
        text = getattr(resp, "text", "") or str(resp)
        # strip triple-backtick JSON fences if present
        if "```json" in text:
            text = text.split("```json",1)[1].split("```",1)[0]
        elif "```" in text:
            text = text.split("```",1)[1].split("```",1)[0]

        return json.loads(text.strip())
    except json.JSONDecodeError:
        # return a safe fallback structured response (keeps app functional)
        return {
            "destinations": [{
                "name": f"Exploring {current_location}",
                "address": "Various locations",
                "distance_km": int(radius // 2),
                "category": "general",
                "time_slot": "all-day",
                "duration": "8 hours",
                "activities": ["Sightseeing", "Local experiences"],
                "costs": {"entry": int(budget * 0.25), "food": int(budget * 0.35), "transport": int(budget * 0.25), "misc": int(budget * 0.15)},
                "total_cost": int(budget),
                "transport_from_previous": {"mode": "Metro/Cab", "cost": int(budget * 0.1), "time": "30 mins"}
            }],
            "itinerary": {
                "morning": ["9:00 AM - Start exploration"],
                "afternoon": ["1:00 PM - Lunch & activities"],
                "evening": ["6:00 PM - Evening activities"]
            },
            "total_budget": {
                "transport": int(budget * 0.25),
                "food": int(budget * 0.35),
                "activities": int(budget * 0.25),
                "miscellaneous": int(budget * 0.15),
                "total": int(budget)
            },
            "tips": ["Book in advance", "Check weather", "Carry cash"]
        }
    except Exception as e:
        st.error(f"Error generating plan: {e}")
        return None

def combine_plans(plans_data):
    prompt = f"""
    Combine these {len(plans_data)} day trip plans into one optimal merged plan:
    
    {json.dumps(plans_data, indent=2)}
    
    Create a balanced plan that:
    1. Takes best destinations from each plan
    2. Optimizes route and timing
    3. Averages budgets intelligently
    4. Removes duplicates
    5. Ensures feasibility for one day
    
    Return JSON in the same format as individual plans.
    """
    try:
        resp = call_generate_with_retries(model, prompt)
        text = getattr(resp, "text", "") or str(resp)
        if "```json" in text:
            text = text.split("```json",1)[1].split("```",1)[0]
        elif "```" in text:
            text = text.split("```",1)[1].split("```",1)[0]
        return json.loads(text.strip())
    except Exception as e:
        st.error(f"Error combining plans: {e}")
        return None

def process_expense_split(message, room_expenses_context):
    prompt = f"""
    You are SplitSense AI for group expense splitting. Use Indian Rupees (₹) for all amounts.
    
    Previous expenses in this room:
    {json.dumps(room_expenses_context, indent=2)}
    
    New message: {message}
    
    Parse the expense and:
    1. Extract: amount in ₹, who paid, who shares the cost
    2. Calculate equal splits
    3. Update running balances
    4. Show who owes whom in ₹
    
    Be conversational and clear. Format all amounts with ₹ symbol.
    """
    try:
        resp = call_generate_with_retries(model, prompt)
        return getattr(resp, "text", "") or str(resp)
    except Exception as e:
        return f"Error processing: {str(e)}"

# ---------------------------
# Session State and Pages (unchanged except small labels)
# ---------------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'current_room' not in st.session_state:
    st.session_state.current_room = None
if 'page' not in st.session_state:
    st.session_state.page = 'login'

# (LOGIN / ROOMS / PLANNING / SPLITSENSE pages are identical to your original, omitted here for brevity)
# For the sake of brevity in this snippet, paste your existing login_page(), rooms_page(), planning_page(), splitsense_page() here.
# They will work unchanged because we updated the AI init and the helper functions above.

# --- Small UI tweak in planning page form:
# change budget label to Indian Rupees by default (you can keep $ if you prefer)
# budget = st.number_input("Your Budget (₹)", min_value=10, max_value=5000, value=100, step=10)

# Main Router
def main():
    if not st.session_state.authenticated:
        login_page()
    else:
        if st.session_state.page == 'rooms':
            rooms_page()
        elif st.session_state.page == 'planning':
            planning_page()
        elif st.session_state.page == 'splitsense':
            splitsense_page()

if __name__ == "__main__":
    main()
