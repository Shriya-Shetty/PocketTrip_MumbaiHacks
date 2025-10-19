import streamlit as st
import google.generativeai as genai
from supabase import create_client, Client
import json
from datetime import datetime
import os
import hashlib

# Page config
st.set_page_config(
    page_title="PocketTrip AI",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
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
    .trip-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        margin: 1rem 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.3);
    }
    .budget-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        border-left: 5px solid #667eea;
        margin: 0.5rem 0;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
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
    .split-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border: 2px solid #e9ecef;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Supabase
@st.cache_resource
def init_supabase():
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        if not url or not key:
            st.error("⚠️ Supabase credentials not found. Please configure environment variables.")
            st.stop()
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error connecting to Supabase: {e}")
        st.stop()

# Initialize Gemini
@st.cache_resource
def init_gemini():
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            st.error("⚠️ Gemini API key not found. Please configure environment variables.")
            st.stop()
        genai.configure(api_key=api_key)
        # Use gemini-2.5-flash - latest and fastest model
        return genai.GenerativeModel('gemini-2.5-flash')
    except Exception as e:
        st.error(f"Error initializing Gemini: {e}")
        st.stop()

supabase: Client = init_supabase()
model = init_gemini()

# Helper Functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

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
        return response.data
    except Exception as e:
        st.error(f"User creation error: {e}")
        return None

def save_trip(user_id, trip_data):
    try:
        data = {
            'user_id': user_id,
            'trip_data': json.dumps(trip_data),
            'created_at': datetime.now().isoformat()
        }
        response = supabase.table('trips').insert(data).execute()
        return response.data
    except Exception as e:
        st.error(f"Trip save error: {e}")
        return None

def get_user_trips(user_id):
    try:
        response = supabase.table('trips').select('*').eq('user_id', user_id).order('created_at', desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching trips: {e}")
        return []

def save_split_expense(user_id, trip_id, expense_data):
    try:
        data = {
            'user_id': user_id,
            'trip_id': trip_id,
            'expense_data': json.dumps(expense_data),
            'created_at': datetime.now().isoformat()
        }
        response = supabase.table('split_expenses').insert(data).execute()
        return response.data
    except Exception as e:
        st.error(f"Error saving expense: {e}")
        return None

def generate_trip_plan(location, duration, budget, interests, special_requests):
    prompt = f"""
    Create a detailed trip plan for:
    Location: {location}
    Duration: {duration} days
    Budget: ${budget}
    Interests: {', '.join(interests)}
    Special Requests: {special_requests}
    
    Provide a JSON response with:
    1. Daily itinerary with activities
    2. Budget breakdown by category (accommodation, food, activities, transport, miscellaneous)
    3. Recommended places to visit
    4. Budget-saving tips
    5. Estimated costs for each activity
    
    Format the response as valid JSON with this structure:
    {{
        "daily_itinerary": [
            {{
                "day": 1,
                "activities": [
                    {{"time": "9:00 AM", "activity": "Visit beach", "cost": 20}}
                ]
            }}
        ],
        "budget_breakdown": {{
            "accommodation": 200,
            "food": 150,
            "activities": 100,
            "transport": 50
        }},
        "recommendations": ["tip1", "tip2"],
        "tips": ["Save money by..."]
    }}
    """
    
    try:
        response = model.generate_content(prompt)
        text = response.text
        
        # Extract JSON if wrapped in markdown
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        return json.loads(text.strip())
    except json.JSONDecodeError as e:
        st.warning("AI response wasn't in perfect JSON format. Using backup structure.")
        return {
            "daily_itinerary": [{"day": i+1, "activities": [{"time": "TBD", "activity": "Exploring", "cost": budget//duration}]} for i in range(duration)],
            "budget_breakdown": {
                "accommodation": budget * 0.35,
                "food": budget * 0.25,
                "activities": budget * 0.25,
                "transport": budget * 0.15
            },
            "recommendations": [f"Visit {location}'s top attractions", "Try local cuisine", "Book accommodations in advance"],
            "tips": ["Travel during off-peak season", "Use public transport", "Book tickets online for discounts"],
            "raw_response": response.text[:500]
        }
    except Exception as e:
        st.error(f"Error generating trip plan: {e}")
        return {
            "error": str(e),
            "daily_itinerary": [],
            "budget_breakdown": {},
            "recommendations": [],
            "tips": []
        }

def process_split_expense(message, context=None):
    context_str = json.dumps(context) if context else ""
    prompt = f"""
    You are SplitSense AI, an expense splitting assistant. 
    Context: {context_str}
    
    User message: {message}
    
    Extract expense information and calculate fair splits. If the user mentions:
    - An amount spent
    - Who paid
    - Who should share the expense
    
    Respond with:
    1. Expense summary
    2. Equal split calculation
    3. Who owes whom and how much
    4. Running balance if applicable
    
    Be conversational and helpful. Format amounts clearly with currency symbols.
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"I'm having trouble processing that. Error: {str(e)}"

# Session State Initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'login'
if 'current_trip' not in st.session_state:
    st.session_state.current_trip = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'expense_context' not in st.session_state:
    st.session_state.expense_context = {'expenses': [], 'balances': {}}

# Login/Signup Page
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<h1 class="main-header">✈️ PocketTrip AI</h1>', unsafe_allow_html=True)
        st.markdown("### Smart Travel Planning & Expense Splitting")
        
        tab1, tab2 = st.tabs(["Login", "Sign Up"])
        
        with tab1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submit = st.form_submit_button("Login", use_container_width=True)
                
                if submit:
                    if username and password:
                        user = authenticate_user(username, password)
                        if user:
                            st.session_state.authenticated = True
                            st.session_state.user = user
                            st.session_state.current_page = 'home'
                            st.rerun()
                        else:
                            st.error("Invalid credentials")
                    else:
                        st.error("Please fill all fields")
        
        with tab2:
            with st.form("signup_form"):
                new_username = st.text_input("Choose Username")
                new_email = st.text_input("Email")
                new_password = st.text_input("Choose Password", type="password")
                confirm_password = st.text_input("Confirm Password", type="password")
                signup = st.form_submit_button("Sign Up", use_container_width=True)
                
                if signup:
                    if new_username and new_email and new_password and confirm_password:
                        if new_password == confirm_password:
                            if len(new_password) >= 6:
                                user = create_user(new_username, new_password, new_email)
                                if user:
                                    st.success("Account created! Please login.")
                                else:
                                    st.error("Username or email already exists")
                            else:
                                st.error("Password must be at least 6 characters")
                        else:
                            st.error("Passwords don't match")
                    else:
                        st.error("Please fill all fields")

# Home/PocketTrip Page
def home_page():
    st.markdown('<h1 class="main-header">🌍 PocketTrip Planner</h1>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state.user['username']}! 👋")
        
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.current_page = 'login'
            st.session_state.current_trip = None
            st.rerun()
        
        st.divider()
        
        st.markdown("### 📊 My Trips")
        trips = get_user_trips(st.session_state.user['id'])
        if trips:
            for trip in trips[:5]:
                try:
                    trip_data = json.loads(trip['trip_data'])
                    if st.button(f"📍 {trip_data.get('location', 'Trip')}", key=f"trip_{trip['id']}", use_container_width=True):
                        st.session_state.current_trip = trip_data
                        st.rerun()
                except:
                    pass
        else:
            st.info("No trips yet. Create your first one!")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 🗺️ Plan Your Trip")
        
        with st.form("trip_form"):
            location = st.text_input("📍 Destination", placeholder="e.g., Goa, Paris, Tokyo")
            
            col_a, col_b = st.columns(2)
            with col_a:
                duration = st.number_input("📅 Duration (days)", min_value=1, max_value=30, value=3)
            with col_b:
                budget = st.number_input("💰 Budget ($)", min_value=100, max_value=50000, value=1000, step=100)
            
            interests = st.multiselect(
                "🎯 Interests",
                ["Beach", "Adventure", "Culture", "Food", "Shopping", "Nightlife", "Nature", "History", "Photography"]
            )
            
            special_requests = st.text_area("📝 Special Requests (Optional)", placeholder="Dietary restrictions, accessibility needs, preferences...")
            
            generate = st.form_submit_button("🚀 Generate Trip Plan", use_container_width=True)
            
            if generate:
                if location and interests:
                    with st.spinner("✨ Creating your personalized trip plan..."):
                        trip_plan = generate_trip_plan(location, duration, budget, interests, special_requests or "None")
                        trip_plan['location'] = location
                        trip_plan['duration'] = duration
                        trip_plan['budget'] = budget
                        trip_plan['interests'] = interests
                        
                        st.session_state.current_trip = trip_plan
                        save_trip(st.session_state.user['id'], trip_plan)
                        st.success("Trip plan generated! 🎉")
                        st.rerun()
                else:
                    st.error("Please fill in destination and select at least one interest")
    
    with col2:
        st.markdown("### 💡 Features")
        st.info("📊 AI-powered trip planning")
        st.info("💵 Smart budget allocation")
        st.info("👥 Group expense splitting")
        st.info("🔄 Real-time cost tracking")
        st.info("📱 Save & share trips")
    
    # Display current trip
    if st.session_state.current_trip:
        st.divider()
        display_trip_plan(st.session_state.current_trip)

def display_trip_plan(trip):
    st.markdown(f'<div class="trip-card"><h2>🎒 Trip to {trip.get("location", "Your Destination")}</h2><p>Duration: {trip.get("duration", "?")} days | Budget: ${trip.get("budget", 0)}</p></div>', unsafe_allow_html=True)
    
    # Navigation to SplitSense
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("💸 Open SplitSense", use_container_width=True, type="primary"):
            st.session_state.current_page = 'splitsense'
            st.rerun()
    
    st.divider()
    
    # Budget Breakdown
    if 'budget_breakdown' in trip and trip['budget_breakdown']:
        st.markdown("### 💰 Budget Breakdown")
        breakdown = trip['budget_breakdown']
        
        num_cols = len(breakdown)
        cols = st.columns(num_cols if num_cols > 0 else 1)
        for idx, (category, amount) in enumerate(breakdown.items()):
            with cols[idx]:
                st.metric(category.title(), f"${amount:.0f}")
    
    # Daily Itinerary
    if 'daily_itinerary' in trip and trip['daily_itinerary']:
        st.markdown("### 📅 Daily Itinerary")
        for day_info in trip['daily_itinerary']:
            with st.expander(f"Day {day_info.get('day', '?')}", expanded=False):
                activities = day_info.get('activities', [])
                if activities:
                    for activity in activities:
                        time_str = activity.get('time', 'TBD')
                        activity_str = activity.get('activity', 'Activity')
                        cost = activity.get('cost', 0)
                        st.markdown(f"**{time_str}** - {activity_str}")
                        if cost:
                            st.caption(f"Estimated cost: ${cost}")
                else:
                    st.info("No activities planned for this day yet.")
    
    # Recommendations
    if 'recommendations' in trip and trip['recommendations']:
        st.markdown("### ⭐ Recommendations")
        for rec in trip['recommendations']:
            st.markdown(f'<div class="budget-card">✨ {rec}</div>', unsafe_allow_html=True)
    
    # Tips
    if 'tips' in trip and trip['tips']:
        st.markdown("### 💡 Money-Saving Tips")
        for tip in trip['tips']:
            st.success(f"💰 {tip}")

# SplitSense Page
def splitsense_page():
    st.markdown('<h1 class="main-header">💸 SplitSense AI</h1>', unsafe_allow_html=True)
    st.markdown("### Smart expense splitting for your trip")
    
    col1, col2 = st.columns([3, 2])
    
    with col1:
        # Back button
        if st.button("← Back to Trip Plan"):
            st.session_state.current_page = 'home'
            st.rerun()
        
        st.divider()
        
        # Chat interface
        st.markdown("### 💬 Chat with SplitSense")
        
        # Display chat history
        for msg in st.session_state.chat_history:
            if msg['role'] == 'user':
                st.markdown(f'<div class="split-card"><strong>You:</strong> {msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="split-card" style="background: #e7f3ff;"><strong>SplitSense:</strong> {msg["content"]}</div>', unsafe_allow_html=True)
        
        # Chat input
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input("Type your expense...", placeholder="e.g., I spent $50 on lunch and want to split with John and Sarah")
            col_a, col_b = st.columns([4, 1])
            with col_b:
                send = st.form_submit_button("Send", use_container_width=True)
            
            if send and user_input:
                # Add user message
                st.session_state.chat_history.append({'role': 'user', 'content': user_input})
                
                # Get AI response
                with st.spinner("Processing..."):
                    response = process_split_expense(user_input, st.session_state.expense_context)
                    st.session_state.chat_history.append({'role': 'assistant', 'content': response})
                    
                    # Save to database
                    if st.session_state.current_trip:
                        save_split_expense(
                            st.session_state.user['id'],
                            st.session_state.current_trip.get('id', 'temp'),
                            {'message': user_input, 'response': response}
                        )
                
                st.rerun()
    
    with col2:
        st.markdown("### 📊 Expense Summary")
        
        # Sample expense tracking
        if st.session_state.expense_context['expenses']:
            total = sum(exp.get('amount', 0) for exp in st.session_state.expense_context['expenses'])
            st.metric("Total Expenses", f"${total:.2f}")
            
            st.markdown("#### Balances")
            for person, balance in st.session_state.expense_context['balances'].items():
                color = "🟢" if balance >= 0 else "🔴"
                st.markdown(f"{color} **{person}**: ${abs(balance):.2f} {'owed to them' if balance > 0 else 'they owe'}")
        else:
            st.info("No expenses tracked yet. Start chatting to add expenses!")
        
        st.divider()
        
        st.markdown("### 💡 Example Commands")
        st.code("I spent $100 on dinner, split with 3 people", language=None)
        st.code("John paid $50 for tickets", language=None)
        st.code("Split $200 equally among 4 people", language=None)
        st.code("What's the current balance?", language=None)
        
        if st.button("🗑️ Clear Chat", use_container_width=True):
            st.session_state.chat_history = []
            st.session_state.expense_context = {'expenses': [], 'balances': {}}
            st.rerun()

# Main App Router
def main():
    if not st.session_state.authenticated:
        login_page()
    else:
        if st.session_state.current_page == 'home':
            home_page()
        elif st.session_state.current_page == 'splitsense':
            splitsense_page()

if __name__ == "__main__":
    main()
