import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import json
from datetime import datetime
import os

# 🎨 Page Setup
st.set_page_config(page_title="PocketTrip AI", page_icon="✈️", layout="wide")

# 🧩 Init Supabase + Gemini
@st.cache_resource
def init_supabase():
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

@st.cache_resource
def init_gemini():
    genai.configure(api_key=os.environ["GEMINI_API_KEY"])
    return genai.GenerativeModel("gemini-2.0-flash")

supabase: Client = init_supabase()
model = init_gemini()

# 🧠 Generate Trip Plan
def generate_trip_plan(location, duration, budget, interests, special_requests):
    prompt = f"""
    Plan a trip to {location} for {duration} days with a ${budget} budget.
    Interests: {', '.join(interests)}.
    Special requests: {special_requests}.
    Return a JSON with daily itinerary, budget breakdown, and recommendations.
    """
    response = model.generate_content(prompt)
    try:
        text = response.text
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        return json.loads(text.strip())
    except:
        return {
            "daily_itinerary": [{"day": i+1, "activities": [{"activity": "Explore", "cost": budget//duration}]} for i in range(duration)],
            "budget_breakdown": {"stay": budget*0.3, "food": budget*0.3, "travel": budget*0.2, "misc": budget*0.2},
            "recommendations": ["Visit main attractions", "Try local cuisine"]
        }

# 🔐 Phone Login
def phone_login():
    st.header("📱 Login with Phone")
    phone = st.text_input("Enter your phone number (+91...):")
    
    if st.button("Send OTP"):
        supabase.auth.sign_in_with_otp({"phone": phone})
        st.session_state.phone = phone
        st.session_state.waiting_otp = True
        st.success("OTP sent! Check your SMS.")

    if st.session_state.get("waiting_otp"):
        otp = st.text_input("Enter OTP:")
        if st.button("Verify OTP"):
            res = supabase.auth.verify_otp({"phone": st.session_state.phone, "token": otp, "type": "sms"})
            if res.user:
                st.session_state.authenticated = True
                st.session_state.user = res.user
                st.success("✅ Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid OTP")

# 👥 Save user profile (auto-sync)
def sync_user_profile(user):
    phone = user.phone
    uid = user.id
    existing = supabase.table("users").select("id").eq("id", uid).execute()
    if not existing.data:
        supabase.table("users").insert({"id": uid, "phone": phone}).execute()

# 🧭 Trip Creation
def create_trip(owner_id, trip_data):
    result = supabase.table("trips").insert({
        "owner_id": owner_id,
        "trip_data": json.dumps(trip_data)
    }).execute()
    trip_id = result.data[0]["id"]
    supabase.table("trip_members").insert({"trip_id": trip_id, "user_id": owner_id}).execute()
    return trip_id

# 👥 Join Shared Trip
def join_trip(user_id, trip_id):
    supabase.table("trip_members").insert({"trip_id": trip_id, "user_id": user_id}).execute()

# 🗺️ Display Trip
def display_trip(trip):
    trip_data = json.loads(trip["trip_data"])
    st.markdown(f"## 🌍 Trip to {trip_data.get('location','Destination')}")
    st.write(f"Budget: ${trip_data.get('budget',0)} | Duration: {trip_data.get('duration',0)} days")

    if "budget_breakdown" in trip_data:
        st.subheader("💰 Budget Breakdown")
        for k, v in trip_data["budget_breakdown"].items():
            st.metric(k.capitalize(), f"${v:.0f}")

    if "daily_itinerary" in trip_data:
        st.subheader("🗓️ Daily Itinerary")
        for day in trip_data["daily_itinerary"]:
            with st.expander(f"Day {day['day']}"):
                for act in day.get("activities", []):
                    st.write(f"- {act.get('activity')} (${act.get('cost',0)})")

# 🏠 Home Page
def home_page():
    st.header("✈️ PocketTrip Planner")
    uid = st.session_state.user.id
    sync_user_profile(st.session_state.user)

    with st.form("trip_form"):
        loc = st.text_input("Destination:")
        days = st.number_input("Duration (days):", 1, 30, 3)
        budget = st.number_input("Budget ($):", 100, 50000, 1000)
        interests = st.multiselect("Interests:", ["Beach","Adventure","Culture","Food","Shopping"])
        special = st.text_area("Special requests:")
        submit = st.form_submit_button("Generate Plan")
        if submit and loc:
            with st.spinner("✨ Generating your plan..."):
                plan = generate_trip_plan(loc, days, budget, interests, special)
                plan["location"] = loc
                plan["budget"] = budget
                plan["duration"] = days
                tid = create_trip(uid, plan)
                st.success("✅ Trip created!")
                st.session_state.current_trip = {"id": tid, "trip_data": json.dumps(plan)}
                st.rerun()

    # Display trips
    trips = supabase.table("trips").select("*").execute().data
    if trips:
        st.divider()
        st.subheader("📋 My Trips")
        for t in trips:
            if st.button(f"Open: {json.loads(t['trip_data']).get('location','Trip')}", key=t["id"]):
                st.session_state.current_trip = t
                st.rerun()

    if st.session_state.current_trip:
        st.divider()
        display_trip(st.session_state.current_trip)
        st.text_input("Invite by Trip ID:", key="invite_id")
        if st.button("Join Trip"):
            join_trip(uid, st.session_state["invite_id"])
            st.success("Joined trip successfully!")

    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.user = None
        st.session_state.current_trip = None
        st.rerun()

# 🚀 Main
def main():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        phone_login()
    else:
        home_page()

if __name__ == "__main__":
    main()
