import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import os

# -----------------------
# CONFIGURATION
# -----------------------

# Set your Supabase and Gemini keys here or from environment variables
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "your-supabase-anon-key")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "your-gemini-api-key")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure Gemini 2.5 Flash
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# -----------------------
# STREAMLIT UI
# -----------------------

st.set_page_config(page_title="PocketTrip AI SQL Editor", page_icon="🧠", layout="wide")
st.title("🧠 PocketTrip SQL + AI Assistant")

# Session states
if "session" not in st.session_state:
    st.session_state.session = None
if "user" not in st.session_state:
    st.session_state.user = None

# -----------------------
# AUTHENTICATION SECTION
# -----------------------
def login_email():
    st.subheader("🔐 Login with Email OTP")
    email = st.text_input("Enter your email:")
    if st.button("Send OTP"):
        try:
            response = supabase.auth.sign_in_with_otp({"email": email})
            st.info("✅ OTP sent to your email. Check your inbox.")
        except Exception as e:
            st.error(f"Error: {str(e)}")

    otp = st.text_input("Enter OTP:")
    if st.button("Verify"):
        try:
            data = supabase.auth.verify_otp({"email": email, "token": otp, "type": "email"})
            st.session_state.user = data.user
            st.success("🎉 Logged in successfully!")
        except Exception as e:
            st.error(f"Verification failed: {str(e)}")

def logout():
    st.session_state.user = None
    supabase.auth.sign_out()
    st.success("Logged out successfully!")

# -----------------------
# MAIN DASHBOARD
# -----------------------
def ai_sql_dashboard():
    st.sidebar.header("🧭 Navigation")
    st.sidebar.button("Logout", on_click=logout)

    st.subheader("🧩 AI SQL Query Assistant")
    sql_query = st.text_area("Write your SQL query here:")

    if st.button("Run Query"):
        try:
            data = supabase.table("trips").select("*").execute()
            st.write("📊 Sample data from 'trips' table:", data.data)
        except Exception as e:
            st.error(f"Database Error: {e}")

    st.subheader("💬 Chat with Gemini 2.5 Flash")
    prompt = st.text_area("Ask anything (AI will respond):")
    if st.button("Ask Gemini"):
        if not prompt.strip():
            st.warning("Please enter a question.")
        else:
            try:
                response = model.generate_content(prompt)
                st.write("🧠 Gemini says:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Gemini API error: {str(e)}")

# -----------------------
# ROUTING
# -----------------------
def main():
    if st.session_state.user is None:
        login_email()
    else:
        ai_sql_dashboard()

if __name__ == "__main__":
    main()
