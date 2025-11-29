# app.py
# Requirements: streamlit, requests, supabase-py
# Env vars / Streamlit secrets required:
#   SUPABASE_URL
#   SUPABASE_KEY

import streamlit as st
import json
import os
import hashlib
import string
import random
import urllib.parse
from datetime import datetime
from supabase import create_client, Client

# ---------------------------
# Page config & CSS
# ---------------------------
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
        padding: 1.2rem;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 0.8rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        color: #333;
    }
    .member-badge {
        background: #e7f3ff;
        padding: 0.4rem 0.8rem;
        border-radius: 8px;
        margin: 0.2rem;
        display: inline-block;
        color: #333;
    }
    .stButton>button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 0.55rem 1.2rem;
        border-radius: 18px;
        font-weight: bold;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 20px rgba(102, 126, 234, 0.25);
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Supabase init
# ---------------------------
@st.cache_resource
def init_supabase():
    try:
        url = os.environ.get("SUPABASE_URL") or (st.secrets.get("SUPABASE_URL") if hasattr(st, "secrets") else None)
        key = os.environ.get("SUPABASE_KEY") or (st.secrets.get("SUPABASE_KEY") if hasattr(st, "secrets") else None)
        if not url or not key:
            st.error("⚠️ Supabase credentials not found. Please configure SUPABASE_URL and SUPABASE_KEY in environment variables or Streamlit secrets.")
            st.stop()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {e}")
        st.stop()

supabase: Client = init_supabase()

# ---------------------------
# Helpers (users, rooms, plans)
# ---------------------------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def authenticate_user(username, password):
    try:
        resp = supabase.table('users').select('*').eq('username', username).execute()
        if resp.data and len(resp.data) > 0:
            user = resp.data[0]
            if user['password'] == hash_password(password):
                return user
        return None
    except Exception as e:
        st.error(f"Authentication error: {e}")
        return None

def create_user(username, password, email):
    try:
        data = {'username': username, 'password': hash_password(password), 'email': email, 'created_at': datetime.now().isoformat()}
        resp = supabase.table('users').insert(data).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        st.error(f"User creation error: {e}")
        return None

def create_room(creator_id, room_name, current_location):
    try:
        code = generate_room_code()
        data = {'room_code': code, 'room_name': room_name, 'creator_id': creator_id,
                'current_location': current_location, 'members': json.dumps([creator_id]),
                'status': 'active', 'created_at': datetime.now().isoformat()}
        resp = supabase.table('rooms').insert(data).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        st.error(f"Room creation error: {e}")
        return None

def join_room(room_code, user_id):
    try:
        resp = supabase.table('rooms').select('*').eq('room_code', room_code).execute()
        if resp.data:
            room = resp.data[0]
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
        resp = supabase.table('rooms').select('*').order('created_at', desc=True).execute()
        if resp.data:
            return [r for r in resp.data if user_id in json.loads(r['members'])]
        return []
    except Exception as e:
        st.error(f"Error fetching rooms: {e}")
        return []

def get_room_members(room_id):
    try:
        room = supabase.table('rooms').select('members').eq('id', room_id).execute()
        if room.data:
            ids = json.loads(room.data[0]['members'])
            members = []
            for mid in ids:
                user = supabase.table('users').select('id, username').eq('id', mid).execute()
                if user.data:
                    members.append(user.data[0])
            return members
        return []
    except Exception as e:
        return []

def save_day_plan(user_id, room_id, plan_data):
    try:
        data = {'user_id': user_id, 'room_id': room_id, 'plan_data': json.dumps(plan_data), 'votes': 0, 'created_at': datetime.now().isoformat()}
        resp = supabase.table('day_plans').insert(data).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        st.error(f"Error saving plan: {e}")
        return None

def get_room_plans(room_id):
    try:
        resp = supabase.table('day_plans').select('*').eq('room_id', room_id).order('created_at', desc=True).execute()
        if resp.data:
            for plan in resp.data:
                u = supabase.table('users').select('username').eq('id', plan['user_id']).execute()
                plan['username'] = u.data[0]['username'] if u.data else 'Unknown'
        return resp.data
    except Exception as e:
        st.error(f"Error fetching plans: {e}")
        return []

def vote_plan(plan_id, user_id):
    try:
        check = supabase.table('plan_votes').select('*').eq('plan_id', plan_id).eq('user_id', user_id).execute()
        if check.data:
            st.warning("You already voted for this plan!")
            return False
        supabase.table('plan_votes').insert({'plan_id': plan_id, 'user_id': user_id}).execute()
        plan = supabase.table('day_plans').select('votes').eq('id', plan_id).execute()
        current = plan.data[0]['votes'] if plan.data else 0
        supabase.table('day_plans').update({'votes': current + 1}).eq('id', plan_id).execute()
        return True
    except Exception as e:
        st.error(f"Error voting: {e}")
        return False

# ---------------------------
# Dummy plan & maps helper
# ---------------------------
def generate_dummy_plan(current_location, radius, budget, interests, additional_info):
    """
    Deterministic Powai plan using the exact times & activities you provided.
    Returns a dict matching the JSON schema used elsewhere in the app.
    """
    destinations = [
        {"name": "Vihar Lake viewpoint", "address": "Vihar Lake, Powai, Mumbai", "distance_km": 2, "category": "nature", "time_slot": "07:30-08:15", "duration": "45 mins", "activities": ["Sunrise stroll"], "costs": {"entry": 0, "food": 0, "transport": 50, "misc": 0}, "total_cost": 50},
        {"name": "Powai Biodiversity Park", "address": "Powai Biodiversity Park, Powai, Mumbai", "distance_km": 3, "category": "nature", "time_slot": "08:30-10:15", "duration": "1h45m", "activities": ["Nature walk"], "costs": {"entry": 0, "food": 0, "transport": 60, "misc": 0}, "total_cost": 60},
        {"name": "Powai Lake boating + promenade", "address": "Powai Lake, Powai, Mumbai", "distance_km": 1, "category": "relaxation", "time_slot": "10:30-12:00", "duration": "1h30m", "activities": ["Boating", "Promenade"], "costs": {"entry": 200, "food": 0, "transport": 50, "misc": 0}, "total_cost": 250},
        {"name": "Lunch (Hiranandani / Powai)", "address": "Hiranandani Gardens, Powai, Mumbai", "distance_km": 1, "category": "food", "time_slot": "12:15-13:15", "duration": "1h", "activities": ["Lunch"], "costs": {"entry": 0, "food": 400, "transport": 30, "misc": 0}, "total_cost": 430},
        {"name": "Powai Lake Trail & small hill trek", "address": "Powai Lake Trail, Powai, Mumbai", "distance_km": 3, "category": "adventure", "time_slot": "13:30-15:30", "duration": "2h", "activities": ["Trail & small hill trek"], "costs": {"entry": 0, "food": 0, "transport": 60, "misc": 0}, "total_cost": 60},
        {"name": "Indoor climbing (High Rock, Powai)", "address": "High Rock Climbing, Powai, Mumbai", "distance_km": 4, "category": "adventure", "time_slot": "16:00-17:30", "duration": "1h30m", "activities": ["Indoor climbing"], "costs": {"entry": 500, "food": 0, "transport": 80, "misc": 0}, "total_cost": 580},
        {"name": "Sunset at Powai Lake promenade", "address": "Powai Lake Promenade, Powai, Mumbai", "distance_km": 1, "category": "relaxation", "time_slot": "18:00-19:00", "duration": "1h", "activities": ["Sunset view"], "costs": {"entry": 0, "food": 0, "transport": 40, "misc": 0}, "total_cost": 40},
        {"name": "Dinner / return to Chandivali", "address": "Chandivali, Mumbai", "distance_km": 5, "category": "food", "time_slot": "19:00-20:00", "duration": "1h", "activities": ["Dinner", "Return"], "costs": {"entry": 0, "food": 300, "transport": 120, "misc": 0}, "total_cost": 420},
    ]

    itinerary = {
        "morning": ["07:30–08:15 — Vihar Lake viewpoint (sunrise stroll)",
                    "08:30–10:15 — Powai Biodiversity Park (nature walk)",
                    "10:30–12:00 — Powai Lake boating + promenade"],
        "afternoon": ["12:15–13:15 — Lunch (Hiranandani / Powai)",
                      "13:30–15:30 — Powai Lake Trail & small hill trek"],
        "evening": ["16:00–17:30 — Indoor climbing (High Rock, Powai)",
                    "18:00–19:00 — Sunset at Powai Lake promenade",
                    "19:00–20:00 — Dinner / return to Chandivali"]
    }

    total_budget = {
        "transport": sum(d["costs"]["transport"] for d in destinations),
        "food": sum(d["costs"]["food"] for d in destinations),
        "activities": sum(d["costs"]["entry"] for d in destinations),
        "miscellaneous": sum(d["costs"]["misc"] for d in destinations),
    }
    total_budget["total"] = total_budget["transport"] + total_budget["food"] + total_budget["activities"] + total_budget["miscellaneous"]

    plan = {
        "destinations": destinations,
        "itinerary": itinerary,
        "total_budget": total_budget,
        "tips": ["Carry water", "Wear comfortable shoes for the trek", "Book boating time if needed"]
    }
    return plan

def build_google_maps_directions(origin, destinations_list):
    """
    Builds a google maps directions URL:
    origin: string
    destinations_list: list of destination dicts with 'address' fields (ordered)
    We'll set final destination to the last address and waypoints to intermediate addresses.
    """
    if not destinations_list:
        return None
    # Clean and encode addresses
    addresses = [d.get("address", d.get("name", "")) for d in destinations_list if d.get("address") or d.get("name")]
    # If origin is same as final (return), we can set destination to origin; otherwise set destination to last address
    destination = addresses[-1]
    waypoints = addresses[:-1]  # all but last
    params = {
        "api": "1",
        "origin": origin,
        "destination": destination
    }
    if waypoints:
        # waypoints separated by | and must be URL encoded
        wp = "|".join([urllib.parse.quote_plus(w) for w in waypoints])
        params["waypoints"] = wp
    # Build base url
    base = "https://www.google.com/maps/dir/?"
    query = "&".join([f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in params.items()])
    return base + query

# ---------------------------
# Replaced generate_day_plan -> uses dummy plan
# ---------------------------
def generate_day_plan(current_location, radius, budget, interests, additional_info):
    # For now, return the deterministic Powai dummy plan regardless of interests
    return generate_dummy_plan(current_location, radius, budget, interests, additional_info)

def combine_plans(plans_data):
    # Simple combine: pick destinations unique by name, keep itinerary of first plan
    merged = {"destinations": [], "itinerary": {}, "total_budget": {"transport":0,"food":0,"activities":0,"miscellaneous":0,"total":0}, "tips": []}
    seen = set()
    for p in plans_data:
        try:
            plan = p if isinstance(p, dict) else json.loads(p)
        except Exception:
            continue
        for d in plan.get("destinations", []):
            if d.get("name") not in seen:
                merged["destinations"].append(d)
                seen.add(d.get("name"))
        # add budgets
        tb = plan.get("total_budget", {})
        for k in ["transport","food","activities","miscellaneous"]:
            merged["total_budget"][k] = merged["total_budget"].get(k,0) + int(tb.get(k,0) or 0)
    merged["total_budget"]["total"] = merged["total_budget"]["transport"] + merged["total_budget"]["food"] + merged["total_budget"]["activities"] + merged["total_budget"]["miscellaneous"]
    merged["tips"] = ["Combined plan - review timings"]
    return merged

# ---------------------------
# Expenses (simple store/display)
# ---------------------------
def save_expense_message(room_id, user_id, message, response_text):
    try:
        data = {'room_id': room_id, 'user_id': user_id, 'message': message, 'response': response_text, 'created_at': datetime.now().isoformat()}
        supabase.table('split_expenses').insert(data).execute()
    except Exception as e:
        st.error(f"Error saving expense: {e}")

def get_room_expenses(room_id):
    try:
        resp = supabase.table('split_expenses').select('*').eq('room_id', room_id).order('created_at', desc=False).execute()
        if resp.data:
            for e in resp.data:
                u = supabase.table('users').select('username').eq('id', e['user_id']).execute()
                e['username'] = u.data[0]['username'] if u.data else 'Unknown'
        return resp.data or []
    except Exception:
        return []

# ---------------------------
# Session state & UI pages
# ---------------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'current_room' not in st.session_state:
    st.session_state.current_room = None
if 'page' not in st.session_state:
    st.session_state.page = 'login'

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
            current_loc = st.text_input("Starting Location", placeholder="Chandivali, Mumbai")
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
                radius = st.number_input("Radius (km)", min_value=1, max_value=200, value=30, step=1)
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
                with st.spinner("Creating your plan... (using local dummy plan)"):
                    plan = generate_day_plan(room['current_location'], radius, budget, interests, additional_info or "None")
                    if plan:
                        plan['user_preferences'] = {'radius': radius, 'budget': budget, 'interests': interests, 'additional_info': additional_info}
                        saved = save_day_plan(st.session_state.user['id'], room['id'], plan)
                        if saved:
                            st.success("Plan created! Check 'All Plans' tab.")
                            st.rerun()

    with tab2:
        st.markdown("### All Member Plans")
        plans = get_room_plans(room['id'])
        if plans:
            for plan in plans:
                try:
                    plan_data = json.loads(plan['plan_data'])
                except Exception:
                    plan_data = {}
                with st.expander(f"🗺️ {plan['username']}'s Plan - Votes: {plan['votes']}", expanded=False):
                    col_a, col_b = st.columns([3, 1])
                    with col_a:
                        if 'destinations' in plan_data:
                            st.markdown("**Destinations:**")
                            for idx, dest in enumerate(plan_data['destinations']):
                                st.markdown(f"📍 **{dest.get('name','Unknown')}** — {dest.get('time_slot','TBD')}")
                                st.caption(f"Address: {dest.get('address','N/A')} | Cost: ₹{dest.get('total_cost',0)}")
                        if 'total_budget' in plan_data:
                            st.markdown("**Budget Breakdown:**")
                            tb = plan_data['total_budget']
                            cols = st.columns(len(tb))
                            for i, (cat, amt) in enumerate(tb.items()):
                                cols[i].metric(cat.title(), f"₹{amt}")
                    with col_b:
                        # Find Location link
                        if 'destinations' in plan_data and plan_data['destinations']:
                            maps_url = build_google_maps_directions(room['current_location'], plan_data['destinations'])
                            if maps_url:
                                st.markdown(f"[🔎 Find Location on Google Maps]({maps_url})", unsafe_allow_html=True)
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
                # For now we echo message as response (no LLM)
                response = f"Recorded: {message}"
                save_expense_message(room['id'], st.session_state.user['id'], message, response)
                st.rerun()
        st.divider()
        if st.button("📊 Calculate Split", use_container_width=True, type="primary"):
            expenses = get_room_expenses(room['id'])
            if expenses:
                # Very simple settlement summary (equal split)
                members = get_room_members(room['id'])
                member_names = [m['username'] for m in members]
                # Sum numeric amounts found in messages (naive parse)
                total = 0
                for e in expenses:
                    # find ₹ amounts in message text
                    msg = e.get('message','')
                    # simple parse: extract digits sequences
                    import re
                    nums = re.findall(r'₹\s*([0-9]+)', msg)
                    for n in nums:
                        total += int(n)
                avg = total / max(1, len(member_names))
                st.markdown("---")
                st.markdown(f"**Total recorded (naive parse):** ₹{int(total)}")
                st.markdown(f"**Each should pay (equal):** ₹{int(avg)}")
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
                st.success("All expenses cleared!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

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
