# streamlit_app.py
import streamlit as st
import requests
from supabase import create_client, Client
import json
from datetime import datetime
import os
import hashlib
import string
import random
import time
import logging

# --- Page config and CSS ---
st.set_page_config(
    page_title="PocketTrip",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

logging.basicConfig(level=logging.INFO)

# --- Initialization helpers for Supabase and Hugging Face (HF Router) ---
@st.cache_resource
def init_supabase():
    try:
        url = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
        if not url or not key:
            st.error("⚠️ Supabase credentials not found. Please configure environment variables or Streamlit secrets.")
            st.stop()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {e}")
        st.stop()

@st.cache_resource
def init_hf():
    """
    Use the new Hugging Face Router endpoint:
    https://router.huggingface.co/hf-inference/models/<model-id>
    """
    api_key = os.environ.get("HF_API_KEY") or st.secrets.get("HF_API_KEY")
    model = os.environ.get("HF_MODEL") or st.secrets.get("HF_MODEL") or "google/flan-t5-large"
    if not api_key:
        st.error("⚠️ Hugging Face API key not found. Please configure HF_API_KEY in Streamlit secrets or environment variables.")
        st.stop()
    # Build router URL for the model
    api_url = f"https://router.huggingface.co/hf-inference/models/{model}"
    return {"api_key": api_key, "model": model, "api_url": api_url}

def hf_generate(prompt, max_length=1024, temperature=0.2, retries=2, retry_delay=1.0):
    """
    Call Hugging Face Router (hf-inference) endpoint for the configured model.
    The router endpoint routes to providers and supports the same 'inputs' payload.
    Returns string output from model or raises.
    """
    cfg = init_hf()
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_length,
            "temperature": temperature,
            "return_full_text": False
        },
        "options": {"wait_for_model": True}
    }

    url = cfg["api_url"]
    # Some models support chat endpoints (e.g., /v1/chat/completions). For simplicity we call the model root.
    for attempt in range(retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=90)
            if resp.status_code == 200:
                # try JSON parse
                try:
                    data = resp.json()
                    # Common HF router responses:
                    #  - list with {'generated_text': "..."}
                    #  - dict with 'generated_text'
                    #  - plain dict (structured)
                    #  - fallback to resp.text
                    if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                        return data[0]["generated_text"]
                    if isinstance(data, dict) and "generated_text" in data:
                        return data["generated_text"]
                    # If it's a dict with choices/messages (chat-like), try to extract
                    if isinstance(data, dict) and "choices" in data and isinstance(data["choices"], list) and "message" in data["choices"][0]:
                        msg = data["choices"][0]["message"]
                        if isinstance(msg, dict) and "content" in msg:
                            # Some responses are {content: [{type: "text", text: "..."}]}
                            content = msg["content"]
                            if isinstance(content, list) and len(content) > 0:
                                # join text pieces
                                texts = [c.get("text","") for c in content if isinstance(c, dict)]
                                return " ".join(texts).strip()
                            if isinstance(content, dict) and "text" in content:
                                return content["text"]
                    # If we didn't find known keys, fallback to returning the JSON string
                    return json.dumps(data)
                except ValueError:
                    return resp.text.strip()
            else:
                # Helpful error message for 410 -> routing change
                if resp.status_code == 410:
                    raise Exception(f"Hugging Face API error 410: {resp.text}")
                # 402 payment required, 404 model not found etc — surface with explanation
                msg = f"Hugging Face API error {resp.status_code}: {resp.text}"
                logging.warning(msg)
                if attempt < retries:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
                raise Exception(msg)
        except requests.exceptions.RequestException as e:
            logging.warning(f"RequestException on attempt {attempt}: {e}")
            if attempt < retries:
                time.sleep(retry_delay * (attempt + 1))
                continue
            raise

def extract_json_from_text(text):
    """
    Try to extract JSON content from model output:
    1) fenced ```json blocks
    2) fenced ``` blocks containing JSON
    3) first {...} block
    Returns python object or None
    """
    try:
        if not text or not isinstance(text, str):
            return None
        if "```json" in text:
            body = text.split("```json", 1)[1].split("```", 1)[0]
            return json.loads(body.strip())
        if "```" in text and "{" in text:
            body = text.split("```", 1)[1].split("```", 1)[0]
            return json.loads(body.strip())
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start:end+1])
    except Exception as e:
        logging.warning(f"Failed to parse JSON from model text: {e}")
    return None

# --- Initialize Supabase and HF config (cached) ---
supabase: Client = init_supabase()
hf_config = init_hf()  # ensure HF key and model present

# --- Remaining app helpers (unchanged logic, using hf_generate where needed) ---
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

# --- HF-powered plan generation / combination / expense processing (use hf_generate) ---
def generate_day_plan(current_location, radius, budget, interests, additional_info):
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

Return ONLY valid JSON (no extra commentary).
"""
    try:
        response_text = hf_generate(prompt, max_length=1024)
        parsed = extract_json_from_text(response_text)
        if parsed:
            return parsed
        try:
            return json.loads(response_text.strip())
        except Exception:
            # fallback plan if parsing fails
            return {
                "destinations": [{
                    "name": f"Exploring {current_location}",
                    "address": "Various locations",
                    "distance_km": radius // 2,
                    "category": "general",
                    "time_slot": "all-day",
                    "duration": "8 hours",
                    "activities": ["Sightseeing", "Local experiences"],
                    "costs": {"entry": int(budget*0.25), "food": int(budget*0.35), "transport": int(budget*0.25), "misc": int(budget*0.15)},
                    "total_cost": int(budget),
                    "transport_from_previous": {"mode": "Metro/Cab", "cost": int(budget*0.1), "time": "30 mins"}
                }],
                "itinerary": {
                    "morning": ["9:00 AM - Start exploration"],
                    "afternoon": ["1:00 PM - Lunch & activities"],
                    "evening": ["6:00 PM - Evening activities"]
                },
                "total_budget": {
                    "transport": int(budget*0.25),
                    "food": int(budget*0.35),
                    "activities": int(budget*0.25),
                    "miscellaneous": int(budget*0.15),
                    "total": int(budget)
                },
                "tips": ["Book in advance", "Check weather", "Carry cash"]
            }
    except Exception as e:
        # Special-case if HF router returns 410 message, show clearer guidance
        msg = str(e)
        if "router.huggingface.co" in msg or "api-inference.huggingface.co" in msg:
            st.error(f"Error generating plan: {msg}\n\nHint: ensure your HF_API_KEY is valid and that your account has access/credits for the chosen model. You may need to pick a different HF_MODEL or enable billing.")
        else:
            st.error(f"Error generating plan: {msg}")
        return None

def combine_plans(plans_data):
    prompt = f"""
Combine these {len(plans_data)} day trip plans into one optimal merged plan. Optimize route, remove duplicates, average budgets intelligently, and ensure it's feasible in one day. Return valid JSON in the same format as individual plans.

Plans:
{json.dumps(plans_data, indent=2)}
"""
    try:
        response_text = hf_generate(prompt, max_length=1024)
        parsed = extract_json_from_text(response_text)
        if parsed:
            return parsed
        try:
            return json.loads(response_text.strip())
        except Exception:
            st.error("Couldn't parse combined plan from model output.")
            return None
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
If possible, return a short JSON summary and then a human-readable explanation.
"""
    try:
        response_text = hf_generate(prompt, max_length=512)
        return response_text
    except Exception as e:
        return f"Error processing: {str(e)}"

# --- Session State defaults ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'current_room' not in st.session_state:
    st.session_state.current_room = None
if 'page' not in st.session_state:
    st.session_state.page = 'login'

# --- UI pages (Login, Rooms, Planning, SplitSense) ---
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<h1 class="main-header">✈️ PocketTrip</h1>', unsafe_allow_html=True)
        st.markdown("### PocketTrip Collaborative Day Trip Planner And Expense Tracker")
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login", use_container_width=True)
                if submit and username and password:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.page = 'rooms'
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        with tab2:
            with st.form("signup_form"):
                new_username = st.text_input("Username")
                new_email = st.text_input("Email")
                new_password = st.text_input("Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                signup = st.form_submit_button("Sign Up", use_container_width=True)
                if signup and new_username and new_email and new_password:
                    if new_password == confirm_password and len(new_password) >= 6:
                        user = create_user(new_username, new_password, new_email)
                        if user:
                            st.success("Account created! Please login.")
                        else:
                            st.error("Username or email already exists")
                    else:
                        st.error("Password must be at least 6 characters and match")

def rooms_page():
    st.markdown('<h1 class="main-header">🏠 Trip Rooms</h1>', unsafe_allow_html=True)
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.user['username']}! 👋")
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.current_room = None
            st.session_state.page = 'login'
            st.rerun()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### 🆕 Create New Room")
        with st.form("create_room"):
            room_name = st.text_input("Trip Name", placeholder="Weekend Getaway")
            current_loc = st.text_input("Starting Location", placeholder="Mumbai, India")
            create = st.form_submit_button("Create Room", use_container_width=True)
            if create and room_name and current_loc:
                room = create_room(st.session_state.user['id'], room_name, current_loc)
                if room:
                    st.success(f"Room created! Code: **{room['room_code']}**")
                    st.session_state.current_room = room
                    st.session_state.page = 'planning'
                    st.rerun()
    with col2:
        st.markdown("### 🔗 Join Room")
        with st.form("join_room"):
            room_code = st.text_input("Room Code", placeholder="ABC123")
            join = st.form_submit_button("Join Room", use_container_width=True)
            if join and room_code:
                room = join_room(room_code.upper(), st.session_state.user['id'])
                if room:
                    st.success(f"Joined {room['room_name']}!")
                    st.session_state.current_room = room
                    st.session_state.page = 'planning'
                    st.rerun()
                else:
                    st.error("Room not found")
    st.divider()
    st.markdown("### 📋 Your Rooms")
    rooms = get_user_rooms(st.session_state.user['id'])
    if rooms:
        for room in rooms:
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**{room['room_name']}** - Code: `{room['room_code']}`")
                st.caption(f"📍 {room['current_location']}")
            with col_b:
                if st.button("Open", key=f"open_{room['id']}", use_container_width=True):
                    st.session_state.current_room = room
                    st.session_state.page = 'planning'
                    st.rerun()
    else:
        st.info("No rooms yet. Create or join one!")

def planning_page():
    room = st.session_state.current_room
    st.markdown(f'<div class="room-card"><h2>🎒 {room["room_name"]}</h2><p>Room Code: {room["room_code"]} | Location: {room["current_location"]}</p></div>', unsafe_allow_html=True)
    with st.sidebar:
        if st.button("← Back to Rooms"):
            st.session_state.page = 'rooms'
            st.rerun()
        st.divider()
        st.markdown("### 👥 Room Members")
        members = get_room_members(room['id'])
        for member in members:
            st.markdown(f'<div class="member-badge">👤 {member["username"]}</div>', unsafe_allow_html=True)
        st.divider()
        if st.button("💸 SplitSense", use_container_width=True, type="primary"):
            st.session_state.page = 'splitsense'
            st.rerun()
    tab1, tab2, tab3 = st.tabs(["📝 Create Plan", "👀 All Plans", "🤝 Combined Plan"])
    with tab1:
        st.markdown("### Create Your Day Plan")
        with st.form("day_plan_form"):
            col_a, col_b = st.columns(2)
            with col_a:
                radius = st.number_input("Radius (km)", min_value=5, max_value=200, value=30, step=5)
            with col_b:
                budget = st.number_input("Your Budget (₹)", min_value=100, max_value=50000, value=2000, step=100)
            interests = st.multiselect(
                "Interests",
                ["Nature", "Food", "Culture", "Adventure", "History", "Shopping", "Photography", "Relaxation"],
                default=["Nature", "Food"]
            )
            additional_info = st.text_area("Additional Info", placeholder="Dietary restrictions, mobility needs, preferences...")
            generate = st.form_submit_button("🚀 Generate My Plan", use_container_width=True)
            if generate and interests:
                with st.spinner("Creating your plan..."):
                    plan = generate_day_plan(room['current_location'], radius, budget, interests, additional_info or "None")
                    if plan:
                        plan['user_preferences'] = {
                            'radius': radius,
                            'budget': budget,
                            'interests': interests,
                            'additional_info': additional_info
                        }
                        saved = save_day_plan(st.session_state.user['id'], room['id'], plan)
                        if saved:
                            st.success("Plan created! Check 'All Plans' tab.")
                            st.rerun()
    with tab2:
        st.markdown("### All Member Plans")
        plans = get_room_plans(room['id'])
        if plans:
            for plan in plans:
                plan_data = {}
                try:
                    plan_data = json.loads(plan['plan_data'])
                except Exception:
                    plan_data = {}
                with st.expander(f"🗺️ {plan['username']}'s Plan - Votes: {plan['votes']}", expanded=False):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        if 'destinations' in plan_data:
                            st.markdown("**Destinations:**")
                            for dest in plan_data['destinations']:
                                st.markdown(f"📍 **{dest.get('name','Unknown')}** ({dest.get('distance_km', '?')} km)")
                                st.caption(f"Time: {dest.get('time_slot', 'TBD')} | Cost: ₹{dest.get('total_cost', 0)}")
                        if 'total_budget' in plan_data:
                            st.markdown("**Budget Breakdown:**")
                            budget = plan_data['total_budget']
                            cols = st.columns(len(budget))
                            for idx, (cat, amt) in enumerate(budget.items()):
                                cols[idx].metric(cat.title(), f"₹{amt}")
                    with col_b:
                        if st.button("👍 Vote", key=f"vote_{plan['id']}", use_container_width=True):
                            if vote_plan(plan['id'], st.session_state.user['id']):
                                st.success("Voted!")
                                st.rerun()
        else:
            st.info("No plans yet. Create one in the 'Create Plan' tab!")
    with tab3:
        st.markdown("### Combined Group Plan")
        plans = get_room_plans(room['id'])
        if len(plans) >= 2:
            if st.button("🔄 Combine All Plans", use_container_width=True, type="primary"):
                with st.spinner("Merging everyone's ideas..."):
                    plans_data = []
                    for p in plans:
                        try:
                            plans_data.append(json.loads(p['plan_data']))
                        except Exception:
                            continue
                    combined = combine_plans(plans_data)
                    if combined:
                        st.session_state['combined_plan'] = combined
                        st.rerun()
            if 'combined_plan' in st.session_state:
                combined = st.session_state['combined_plan']
                if 'destinations' in combined:
                    st.markdown("### 🗺️ Merged Destinations")
                    for dest in combined['destinations']:
                        st.markdown(f'<div class="plan-card"><strong>{dest.get("name","Unknown")}</strong><br>📍 {dest.get("address", "N/A")}<br>⏰ {dest.get("time_slot", "TBD")} | 💰 ₹{dest.get("total_cost", 0)}</div>', unsafe_allow_html=True)
                if 'total_budget' in combined:
                    st.markdown("### 💰 Combined Budget")
                    cols = st.columns(len(combined['total_budget']))
                    for idx, (cat, amt) in enumerate(combined['total_budget'].items()):
                        cols[idx].metric(cat.title(), f"₹{amt}")
        else:
            st.info("Need at least 2 plans to combine. Create more plans!")

def splitsense_page():
    room = st.session_state.current_room
    st.markdown('<h1 class="main-header">💸 SplitSense AI</h1>', unsafe_allow_html=True)
    st.markdown(f"### Room: {room['room_name']}")
    if st.button("← Back to Planning"):
        st.session_state.page = 'planning'
        st.rerun()
    st.divider()
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("### 💬 Expense Chat")
        expenses = get_room_expenses(room['id'])
        for exp in expenses:
            st.markdown(f'<div class="chat-user"><strong>{exp["username"]}:</strong><br>{exp["message"]}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="chat-assistant"><strong>SplitSense AI:</strong><br>{exp["response"]}</div>', unsafe_allow_html=True)
        with st.form("expense_form", clear_on_submit=True):
            message = st.text_input("Enter expense", placeholder="I paid ₹500 for lunch, split among 4 people")
            send = st.form_submit_button("Send", use_container_width=True)
            if send and message:
                with st.spinner("Processing..."):
                    context = [{'user': e['username'], 'message': e['message'], 'response': e['response']} for e in expenses]
                    response = process_expense_split(message, context)
                    save_expense_message(room['id'], st.session_state.user['id'], message, response)
                    st.rerun()
        st.divider()
        if st.button("📊 Calculate Split", use_container_width=True, type="primary"):
            if expenses:
                with st.spinner("Calculating final splits..."):
                    members = get_room_members(room['id'])
                    member_names = [m['username'] for m in members]
                    split_prompt = f"""
Based on all these expense messages, calculate the final settlement for everyone.

Room members: {', '.join(member_names)}

Expense history:
{json.dumps([{'user': e['username'], 'message': e['message']} for e in expenses], indent=2)}

Provide a clear summary in Indian Rupees (₹):
1. Total expenses
2. Each person's share
3. Who owes whom and exact amounts
4. Simplified settlements (minimize number of transactions)

Format it clearly with headings and use ₹ symbol for all amounts.
"""
                    try:
                        final_split = hf_generate(split_prompt, max_length=1024)
                        st.session_state['final_split'] = final_split
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error calculating final split: {e}")
        if 'final_split' in st.session_state and st.session_state.get('final_split'):
            st.markdown("---")
            st.markdown("### 💰 Final Settlement Summary")
            st.markdown(f'<div class="split-summary">{st.session_state["final_split"]}</div>', unsafe_allow_html=True)
            if st.button("✅ Clear Settlement", use_container_width=True):
                st.session_state['final_split'] = None
                st.rerun()
    with col2:
        st.markdown("### 💡 Quick Guide")
        st.info("💬 Examples:\n\n- 'I paid ₹500 for tickets'\n- 'Split ₹800 among 3 people'\n- 'Rahul owes me ₹250'\n- 'What's everyone's balance?'")
        st.markdown("### 👥 Room Members")
        members = get_room_members(room['id'])
        for member in members:
            st.markdown(f'<div class="member-badge">👤 {member["username"]}</div>', unsafe_allow_html=True)
        st.divider()
        if st.button("🗑️ Clear All Expenses", use_container_width=True):
            try:
                supabase.table('split_expenses').delete().eq('room_id', room['id']).execute()
                if 'final_split' in st.session_state:
                    st.session_state['final_split'] = None
                st.success("All expenses cleared!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

# --- Main router ---
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
