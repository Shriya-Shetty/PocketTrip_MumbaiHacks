import streamlit as st
from supabase import create_client, Client
import google.generativeai as genai
import os

# -------------------------
# CONFIGURATION
# -------------------------
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "your-supabase-anon-key")
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "your-gemini-api-key")

# Initialize clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

st.set_page_config(page_title="PocketTrip AI SQL Editor", page_icon="📱", layout="wide")
st.title("📱 PocketTrip AI + Supabase Login")

# -------------------------
# SESSION MANAGEMENT
# -------------------------
if "user" not in st.session_state:
    st.session_state.user = None

# -------------------------
# LOGIN USING PHONE OTP
# -------------------------
def phone_login():
    st.subheader("🔐 Login using Phone OTP")

    phone = st.text_input("Enter your phone number (with country code):", placeholder="+91XXXXXXXXXX")

    if st.button("Send OTP"):
        if not phone.strip():
            st.warning("Please enter your phone number first.")
        else:
            try:
                # Request Supabase to send OTP
                response = supabase.auth.sign_in_with_otp({"phone": phone})
                st.session_state.phone = phone
                st.info("✅ OTP sent successfully. Check your SMS.")
            except Exception as e:
                st.error(f"Error sending OTP: {str(e)}")

    otp = st.text_input("Enter OTP you received:")

    if st.button("Verify OTP"):
        try:
            data = supabase.auth.verify_otp({"phone": st.session_state.phone, "token": otp, "type": "sms"})
            st.session_state.user = data.user
            st.success("🎉 Logged in successfully!")
        except Exception as e:
            st.error(f"Verification failed: {str(e)}")

# -------------------------
# MAIN DASHBOARD
# -------------------------
def ai_dashboard():
    st.sidebar.header("Menu")
    if st.sidebar.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.rerun()

    st.subheader("💬 Chat with Gemini 2.5 Flash")
    prompt = st.text_area("Ask anything...")

    if st.button("Ask AI"):
        if not prompt.strip():
            st.warning("Enter a question first.")
        else:
            try:
                response = model.generate_content(prompt)
                st.markdown("### 🤖 Gemini's Answer:")
                st.markdown(response.text)
            except Exception as e:
                st.error(f"Gemini API error: {str(e)}")

# -------------------------
# MAIN
# -------------------------
def main():
    if st.session_state.user is None:
        phone_login()
    else:
        ai_dashboard()

if __name__ == "__main__":
    main()
