# PocketTrip Pro UI - streamlit app
# Single-file Streamlit app with professional, attractive UI
# Keeps existing Supabase-backed logic and dummy plan behavior.
# Env vars required: SUPABASE_URL, SUPABASE_KEY

import streamlit as st
import json
import os
import hashlib
import string
import random
import urllib.parse
from datetime import datetime
from supabase import create_client, Client

# ---------- Page config ----------
st.set_page_config(page_title="PocketTrip Pro", page_icon="✈️", layout="wide")

# ---------- Polished CSS ----------
# Uses gradients, glassmorphism, card layouts and a responsive timeline
st.markdown(
    """
    <style>
    :root{
      --accent1: #667eea; /* purple-blue */
      --accent2: #764ba2; /* deeper purple */
      --muted: #6b7280;
      --glass: rgba(255,255,255,0.08);
      --card-bg: rgba(255,255,255,0.96);
    }
    /* Page background */
    .stApp {
      background: linear-gradient(180deg, #0f172a 0%, #07133a 100%);
      color: #e6eef8;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial;
    }
    /* Header */
    .hero {
      padding: 34px 28px;
      border-radius: 14px;
      background: linear-gradient(90deg, rgba(102,126,234,0.12), rgba(118,75,162,0.06));
      display:flex;align-items:center;gap:18px;margin-bottom:18px;
      box-shadow: 0 8px 30px rgba(2,6,23,0.6);
    }
    .logo {
      width:84px;height:84px;border-radius:16px;display:flex;align-items:center;justify-content:center;
      background: linear-gradient(135deg,var(--accent1),var(--accent2));font-size:36px;font-weight:700;color:white;
      box-shadow: 0 6px 20px rgba(102,126,234,0.28);
    }
    .hero h1{margin:0;font-size:28px}
    .hero p{margin:0;color:var(--muted)}

    /* Cards */
    .card {background:var(--card-bg);color:#0b1220;padding:14px;border-radius:12px;border:1px solid rgba(11,18,32,0.06)}
    .muted{color:var(--muted)}

    /* Timeline */
    .timeline{background:linear-gradient(180deg,#fff, #fff);padding:12px;border-radius:10px}
    .step{display:flex;gap:14px;align-items:flex-start;padding:10px;border-radius:10px}
    .dot{width:12px;height:12px;border-radius:50%;background:linear-gradient(90deg,var(--accent1),var(--accent2));margin-top:6px}
    .when{font-weight:700;color:#0b1220}
    .what{color:#0b1220}

    /* Plan tiles */
    .plan-tile{background:linear-gradient(180deg, rgba(102,126,234,0.06), rgba(118,75,162,0.03));padding:12px;border-radius:12px;border:1px solid rgba(118,75,162,0.08)}

    /* Button override for Streamlit buttons */
    .stButton>button{background:linear-gradient(90deg,var(--accent1),var(--accent2));color:white;border:none;padding:10px 18px;border-radius:10px;font-weight:600}
    .stButton>button:hover{transform:translateY(-2px);box-shadow:0 10px 30px rgba(102,126,234,0.2)}

    /* small responsive tweaks */
    @media (max-width: 880px){ .hero{flex-direction:column;align-items:flex-start}.logo{width:64px;height:64px} }

    </style>
    """,
    unsafe_allow_html=True,
)

# ---------- Initialize Supabase ----------
@st.cache_resource
def init_supabase():
    url = os.environ.get("SUPABASE_URL") or (st.secrets.get("SUPABASE_URL") if hasattr(st, "secrets") else None)
    key = os.environ.get("SUPABASE_KEY") or (st.secrets.get("SUPABASE_KEY") if hasattr(st, "secrets") else None)
    if not url or not key:
        st.error("⚠️ Supabase credentials missing. Add SUPABASE_URL and SUPABASE_KEY to env or Streamlit secrets.")
        st.stop()
    return create_client(url, key)

supabase: Client = init_supabase()

# ---------- Utilities (unchanged logic) ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

# DB helpers --- same as before but concise

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
        data = {'room_code': code, 'room_name': room_name, 'creator_id': creator_id, 'current_location': current_location,
                'members': json.dumps([creator_id]), 'status':'active','created_at': datetime.now().isoformat()}
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

# ---------- Dummy Powai plan (your timings) ----------
def generate_dummy_plan(current_location, radius, budget, interests, additional_info):
    destinations = [
        {"name": "Vihar Lake viewpoint", "address": "Vihar Lake, Powai, Mumbai", "time_slot": "07:30-08:15", "duration": "45m", "activities": ["Sunrise stroll"], "costs": {"entry":0,"food":0,"transport":50}, "total_cost":50},
        {"name": "Powai Biodiversity Park", "address": "Powai Biodiversity Park, Powai, Mumbai", "time_slot": "08:30-10:15", "duration": "1h45", "activities": ["Nature walk"], "costs": {"entry":0,"food":0,"transport":60}, "total_cost":60},
        {"name": "Powai Lake boating + promenade", "address": "Powai Lake, Powai, Mumbai", "time_slot": "10:30-12:00", "duration": "1h30", "activities": ["Boating","Promenade"], "costs": {"entry":200,"food":0,"transport":50}, "total_cost":250},
        {"name": "Lunch (Hiranandani / Powai)", "address": "Hiranandani Gardens, Powai, Mumbai", "time_slot": "12:15-13:15", "duration": "1h", "activities": ["Lunch"], "costs": {"entry":0,"food":400,"transport":30}, "total_cost":430},
        {"name": "Powai Lake Trail & small hill trek", "address": "Powai Lake Trail, Powai, Mumbai", "time_slot": "13:30-15:30", "duration": "2h", "activities": ["Trail & small hill trek"], "costs": {"entry":0,"food":0,"transport":60}, "total_cost":60},
        {"name": "Indoor climbing (High Rock, Powai)", "address": "High Rock Climbing, Powai, Mumbai", "time_slot": "16:00-17:30", "duration": "1h30", "activities": ["Indoor climbing"], "costs": {"entry":500,"food":0,"transport":80}, "total_cost":580},
        {"name": "Sunset at Powai Lake promenade", "address": "Powai Lake Promenade, Powai, Mumbai", "time_slot": "18:00-19:00", "duration": "1h", "activities": ["Sunset view"], "costs": {"entry":0,"food":0,"transport":40}, "total_cost":40},
        {"name": "Dinner / return to Chandivali", "address": "Chandivali, Mumbai", "time_slot": "19:00-20:00", "duration": "1h", "activities": ["Dinner & return"], "costs": {"entry":0,"food":300,"transport":120}, "total_cost":420},
    ]
    itinerary = {
        "morning": ["07:30–08:15 — Vihar Lake viewpoint (sunrise stroll)", "08:30–10:15 — Powai Biodiversity Park (nature walk)", "10:30–12:00 — Powai Lake boating + promenade"],
        "afternoon": ["12:15–13:15 — Lunch (Hiranandani / Powai)", "13:30–15:30 — Powai Lake Trail & small hill trek"],
        "evening": ["16:00–17:30 — Indoor climbing (High Rock, Powai)", "18:00–19:00 — Sunset at Powai Lake promenade", "19:00–20:00 — Dinner / return to Chandivali"]
    }
    total_budget = {"transport": sum(d['costs']['transport'] for d in destinations), "food": sum(d['costs']['food'] for d in destinations), "activities": sum(d['costs']['entry'] for d in destinations)}
    total_budget['miscellaneous'] = 0
    total_budget['total'] = total_budget['transport'] + total_budget['food'] + total_budget['activities'] + total_budget['miscellaneous']
    plan = {"destinations": destinations, "itinerary": itinerary, "total_budget": total_budget, "tips": ["Carry water","Wear comfortable shoes","Book boating slot if busy"]}
    return plan

# ---------- Maps builder ----------

def build_google_maps_directions(origin, destinations_list):
    if not destinations_list:
        return None
    addresses = [d.get('address', d.get('name','')) for d in destinations_list if d.get('address') or d.get('name')]
    destination = addresses[-1]
    waypoints = addresses[:-1]
    params = {'api':'1','origin': origin,'destination': destination}
    if waypoints:
        # waypoints pipe-separated
        params['waypoints'] = '|'.join(waypoints)
    base = 'https://www.google.com/maps/dir/?'
    q = '&'.join([f"{k}={urllib.parse.quote_plus(str(v))}" for k,v in params.items()])
    return base + q

# ---------- Persistence functions (plans & expenses) ----------

def save_day_plan(user_id, room_id, plan_data):
    try:
        data = {'user_id': user_id, 'room_id': room_id, 'plan_data': json.dumps(plan_data), 'votes':0, 'created_at': datetime.now().isoformat()}
        resp = supabase.table('day_plans').insert(data).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        st.error(f"Error saving plan: {e}")
        return None


def get_room_plans(room_id):
    try:
        resp = supabase.table('day_plans').select('*').eq('room_id', room_id).order('created_at', desc=True).execute()
        if resp.data:
            for p in resp.data:
                u = supabase.table('users').select('username').eq('id', p['user_id']).execute()
                p['username'] = u.data[0]['username'] if u.data else 'Unknown'
        return resp.data or []
    except Exception as e:
        st.error(f"Error fetching plans: {e}")
        return []

# ---------- Session state ----------
if 'authenticated' not in st.session_state: st.session_state.authenticated = False
if 'user' not in st.session_state: st.session_state.user = None
if 'current_room' not in st.session_state: st.session_state.current_room = None
if 'page' not in st.session_state: st.session_state.page = 'login'

# ---------- UI components ----------

def header():
    st.markdown(
        f"""
        <div class="hero card">
            <div class="logo">PT</div>
            <div>
                <h1>PocketTrip — Smart Day-trip Planner</h1>
                <p class="muted">Agentic travel planning for groups • collaborative itineraries • fair expense splitting</p>
            </div>
            <div style="margin-left:auto;text-align:right;">
                <div class="muted">Logged in: {st.session_state.user['username'] if st.session_state.user else 'Guest'}</div>
                <div class="muted">{datetime.now().strftime('%b %d, %Y')}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Tiny card helper

def card(title, content, width='100%'):
    st.markdown(f"<div class='card' style='width:{width}; margin-bottom:10px'><h3>{title}</h3><div>{content}</div></div>", unsafe_allow_html=True)

# ---------- Pages ----------

def login_page():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        header()
        st.write("## Welcome — please login or sign up to create trips")
        tabs = st.tabs(["Login","Sign Up"])
        with tabs[0]:
            with st.form('login'):
                username = st.text_input('Username')
                password = st.text_input('Password', type='password')
                submit = st.form_submit_button('Login')
                if submit:
                    user = authenticate_user(username, password)
                    if user:
                        st.session_state.authenticated = True
                        st.session_state.user = user
                        st.session_state.page = 'rooms'
                        st.experimental_rerun()
                    else:
                        st.error('Invalid credentials')
        with tabs[1]:
            with st.form('signup'):
                username = st.text_input('Choose a username')
                email = st.text_input('Email')
                password = st.text_input('Password', type='password')
                confirm = st.text_input('Confirm password', type='password')
                submit2 = st.form_submit_button('Create Account')
                if submit2:
                    if password and password==confirm and len(password) >=6:
                        user = create_user(username, password, email)
                        if user:
                            st.success('Account created — please login')
                        else:
                            st.error('Could not create account')
                    else:
                        st.error('Passwords must match and be >=6 chars')


def rooms_page():
    header()
    with st.sidebar:
        st.markdown('### Room Controls')
        st.write(f"User: {st.session_state.user['username']}")
        if st.button('Logout'):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.current_room = None
            st.session_state.page = 'login'
            st.experimental_rerun()

    col1, col2 = st.columns(2)
    with col1:
        st.markdown('### Create a new trip room')
        with st.form('newroom'):
            name = st.text_input('Trip name', value='Weekend Powai Trip')
            start = st.text_input('Starting location', value='Chandivali, Mumbai')
            create = st.form_submit_button('Create Room')
            if create:
                room = create_room(st.session_state.user['id'], name, start)
                if room:
                    st.success(f'Room created — code {room['room_code']}')
                    st.session_state.current_room = room
                    st.session_state.page = 'planning'
                    st.experimental_rerun()
    with col2:
        st.markdown('### Join a room')
        with st.form('join'):
            code = st.text_input('Room code')
            join = st.form_submit_button('Join')
            if join:
                room = join_room(code.upper(), st.session_state.user['id'])
                if room:
                    st.success(f"Joined {room['room_name']}")
                    st.session_state.current_room = room
                    st.session_state.page = 'planning'
                    st.experimental_rerun()
                else:
                    st.error('Room not found')

    st.divider()
    st.markdown('### Your Rooms')
    rooms = get_user_rooms(st.session_state.user['id'])
    if rooms:
        for r in rooms:
            cols = st.columns([4,1])
            cols[0].markdown(f"**{r['room_name']}** — {r['current_location']}\n`{r['room_code']}`")
            if cols[1].button('Open', key=f"open_{r['id']}"):
                st.session_state.current_room = r
                st.session_state.page = 'planning'
                st.experimental_rerun()
    else:
        st.info('No rooms yet — create one')


def planning_page():
    room = st.session_state.current_room
    header()
    with st.sidebar:
        if st.button('← Back to Rooms'):
            st.session_state.page = 'rooms'
            st.experimental_rerun()
        st.markdown('### Room Members')
        members = get_room_members(room['id'])
        for m in members:
            st.markdown(f"- {m['username']}")
        st.divider()
        if st.button('Go to SplitSense'):
            st.session_state.page = 'splitsense'
            st.experimental_rerun()

    st.markdown(f"<div class='card'><h3>{room['room_name']}</h3><div class='muted'>Code: {room['room_code']} — Start: {room['current_location']}</div></div>", unsafe_allow_html=True)

    c1, c2 = st.columns([2,1])
    with c1:
        st.markdown('### Create Plan')
        with st.form('plan'):
            radius = st.slider('Radius (km)', 1, 100, 10)
            budget = st.number_input('Budget (₹)', 100, 50000, 2000)
            interests = st.multiselect('Interests', ['Nature','Food','Adventure','Relaxation'], default=['Nature','Food'])
            additional = st.text_area('Notes', placeholder='Any food preferences, mobility constraints...')
            gen = st.form_submit_button('Generate My Plan (Use Powai dummy)')
            if gen:
                plan = generate_dummy_plan(room['current_location'], radius, budget, interests, additional)
                plan['user_preferences'] = {'radius':radius,'budget':budget,'interests':interests,'additional_info':additional}
                saved = save_day_plan(st.session_state.user['id'], room['id'], plan)
                if saved:
                    st.success('Plan saved — view in All Plans')
                    st.experimental_rerun()

    with c2:
        st.markdown('### Quick Actions')
        st.button('Invite Members')
        st.markdown('### Tips')
        st.markdown('- Use the Find Location link on each plan to open Google Maps with waypoints')

    st.divider()
    st.markdown('### All Plans')
    plans = get_room_plans(room['id'])
    if plans:
        for p in plans:
            try:
                pd = json.loads(p['plan_data'])
            except Exception:
                pd = {}
            st.markdown('<div class="plan-tile">', unsafe_allow_html=True)
            st.write(f"**{p['username']}'s plan** — Votes: {p['votes']}")
            if 'destinations' in pd:
                # timeline
                st.markdown('<div style="padding:6px;background:rgba(255,255,255,0.02);border-radius:8px">', unsafe_allow_html=True)
                for d in pd['destinations']:
                    st.markdown(f"<div class='step'><div class='dot'></div><div><div class='when'>{d['time_slot']}</div><div class='what'><strong>{d['name']}</strong> — {d['activities'][0]}<br><span class='muted'>{d['address']}</span></div></div></div>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            if 'total_budget' in pd:
                tb = pd['total_budget']
                cols = st.columns(len(tb))
                for i,(k,v) in enumerate(tb.items()):
                    cols[i].metric(k.title(), f"₹{v}")

            # find location link
            if 'destinations' in pd and pd['destinations']:
                maps = build_google_maps_directions(room['current_location'], pd['destinations'])
                st.markdown(f"[🔎 Find Location]({maps})", unsafe_allow_html=True)

            if st.button('👍 Vote', key=f"vote_{p['id']}"):
                vote_plan(p['id'], st.session_state.user['id'])
                st.experimental_rerun()

            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info('No plans yet — create one using Generate My Plan')


def splitsense_page():
    room = st.session_state.current_room
    header()
    with st.sidebar:
        if st.button('← Back to Planning'):
            st.session_state.page = 'planning'
            st.experimental_rerun()
    st.markdown('<div class="card"><h3>SplitSense — Expense Tracker</h3><p class="muted">Simple group expense recorder</p></div>', unsafe_allow_html=True)
    expenses = get_room_expenses(room['id'])
    for e in expenses:
        st.markdown(f"**{e['username']}** — {e['message']}\n*{e['created_at']}*")
    with st.form('exp'):
        msg = st.text_input('Record expense (e.g. I paid ₹500 for lunch)')
        send = st.form_submit_button('Send')
        if send and msg:
            resp = f"Recorded: {msg}"
            save_expense_message(room['id'], st.session_state.user['id'], msg, resp)
            st.experimental_rerun()

# ---------- Voting helper ----------

def vote_plan(plan_id, user_id):
    try:
        check = supabase.table('plan_votes').select('*').eq('plan_id', plan_id).eq('user_id', user_id).execute()
        if check.data:
            st.warning('Already voted')
            return False
        supabase.table('plan_votes').insert({'plan_id': plan_id, 'user_id': user_id}).execute()
        plan = supabase.table('day_plans').select('votes').eq('id', plan_id).execute()
        current = plan.data[0]['votes'] if plan.data else 0
        supabase.table('day_plans').update({'votes': current+1}).eq('id', plan_id).execute()
        return True
    except Exception as e:
        st.error(f"Vote error: {e}")
        return False

# ---------- Expenses storage ----------

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

# ---------- Main router ----------

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

if __name__ == '__main__':
    main()
