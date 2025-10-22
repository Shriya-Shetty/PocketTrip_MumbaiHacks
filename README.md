# 🌍 PocketTrip - AI-Powered Collaborative Travel Planner

> **Agentic AI for Smart Budget Planning & Group Expense Management**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Gemini](https://img.shields.io/badge/Google-Gemini%202.0-orange.svg)](https://ai.google.dev/)

---

## 📖 Overview

**PocketTrip** is an intelligent, collaborative day-trip planning platform that leverages **Agentic AI** to autonomously manage travel budgets and group expenses. Built for the modern traveler, it combines AI-powered itinerary generation with smart expense splitting in one seamless experience.

### 🎯 Key Features

- **🤖 AI Trip Planning**: Generate optimized day-trip itineraries with realistic costs in Indian Rupees (₹)
- **👥 Collaborative Rooms**: Create or join trip rooms using unique 6-character codes
- **🗳️ Democratic Voting**: Vote on your favorite plans and let the group decide
- **🔄 Plan Merging**: AI combines multiple user plans into one optimal itinerary
- **💸 SplitSense AI**: Natural language expense tracking with smart debt settlement
- **📊 Split Calculator**: Minimizes payment transactions using graph optimization algorithms
- **⚡ Real-time Sync**: All changes sync instantly across all room members

---

## 🏗️ Architecture

### Tech Stack

| Component | Technology |
|-----------|------------|
| **Frontend** | Streamlit (Python) |
| **AI Model** | Google Gemini 2.5 Flash |
| **Database** | Supabase (PostgreSQL) |
| **Authentication** | Custom (SHA-256) |
| **Deployment** | Streamlit Cloud |

### Database Schema

```sql
users           → User accounts (username, password, email)
rooms           → Collaborative trip rooms (room_code, members JSONB)
day_plans       → Individual AI-generated plans (plan_data JSONB, votes)
plan_votes      → Voting tracking (prevents duplicate votes)
split_expenses  → Expense chat history per room (message, response)
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Supabase account
- Google Gemini API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Shriya-Shetty/PocketTrip_MumbaiHacks.git
   cd pockettrip
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   
   Create a `.streamlit/secrets.toml` file:
   ```toml
   SUPABASE_URL = "your_supabase_project_url"
   SUPABASE_KEY = "your_supabase_anon_key"
   GEMINI_API_KEY = "your_gemini_api_key"
   ```

   Or set environment variables:
   ```bash
   export SUPABASE_URL="your_supabase_project_url"
   export SUPABASE_KEY="your_supabase_anon_key"
   export GEMINI_API_KEY="your_gemini_api_key"
   ```

4. **Set up Supabase database**
   
   Run the SQL script in your Supabase SQL Editor:
   ```bash
   # Copy contents of database_schema.sql to Supabase SQL Editor
   # Execute the script to create all tables and functions
   ```

5. **Run the application**
   ```bash
   streamlit run main.py
   ```

6. **Open your browser**
   ```
   http://localhost:8501
   ```

---

## 📋 Requirements

Create a `requirements.txt` file:

```txt
streamlit==1.28.0
google-generativeai==0.3.0
supabase==2.0.0
python-dotenv==1.0.0
```

---

## 🎮 Usage Guide

### 1️⃣ Create Account

- Sign up with username, email, and password
- Login to access the dashboard

### 2️⃣ Create/Join Room

**Create Room:**
- Enter trip name (e.g., "Mumbai Weekend")
- Specify starting location
- Get a unique 6-character room code
- Share code with friends

**Join Room:**
- Enter room code shared by creator
- Instantly join the collaborative planning session

### 3️⃣ Generate Your Plan

- **Current Location**: Your starting point (e.g., Mumbai, India)
- **Radius**: Search area in kilometers (5-200 km)
- **Budget**: Your spending limit in ₹ (₹100 - ₹100,000)
- **Interests**: Select from Nature, Food, Culture, Adventure, etc.
- **Additional Info**: Dietary restrictions, mobility needs, preferences

**AI generates:**
- Optimized itinerary with precise timings
- Realistic cost breakdown (transport, food, activities)
- Travel modes and costs between locations
- Budget-saving tips

### 4️⃣ Collaborate & Vote

- View all room members' plans
- Vote for your favorite plans (👍 button)
- See vote counts in real-time
- Most voted plan rises to the top

### 5️⃣ Combine Plans

- Click "🔄 Combine All Plans" (requires 2+ plans)
- AI merges everyone's ideas
- Creates balanced itinerary optimizing:
  - Best destinations from each plan
  - Route efficiency
  - Average budget allocation
  - Time management

### 6️⃣ Track Expenses with SplitSense AI

**Chat Interface:**
```
You: "I paid ₹850 for Gateway of India tickets"
AI: "Got it! ₹850 split among 3 people = ₹283.33 each.
     Rahul owes you ₹283.33
     Priya owes you ₹283.33"
```

**Example Commands:**
- `"I paid ₹500 for lunch, split among 4 people"`
- `"Rahul paid ₹300 for cab"`
- `"Split ₹800 equally"`
- `"What's everyone's balance?"`

### 7️⃣ Calculate Final Split

- Click "📊 Calculate Split" button
- AI analyzes all expenses
- Minimizes transactions using debt graph optimization
- Shows: "Rahul pays Priya ₹425" (simplified settlements)

**Example Output:**
```
Total Expenses: ₹2,450
Per Person: ₹816.67

Optimized Settlements:
✅ Amit pays Rahul ₹83.33
✅ Priya pays Rahul ₹200
Done! Only 2 transactions instead of 6.
```

---

## 🧠 AI Agents Explained

### 1. Financial Planning Agent 💰

**Purpose:** Autonomous budget optimization and itinerary generation

**How it works:**
```python
def generate_day_plan(location, radius, budget, interests, additional_info):
    # AI receives constraints
    # Analyzes realistic costs for the location
    # Generates optimized itinerary
    # Returns structured JSON with budget breakdown
```

**Output:**
- Destinations within radius
- Time-based schedule (morning/afternoon/evening)
- Itemized costs (entry fees, food, transport)
- Travel modes between locations (Metro/Cab/Auto)
- Total budget allocation

**Fintech Application:** Robo-advisory for experience optimization

---

### 2. Collaborative Intelligence Agent 🤝

**Purpose:** Democratic plan merging and conflict resolution

**How it works:**
```python
def combine_plans(plans_data):
    # Takes multiple user plans
    # Identifies overlapping destinations
    # Resolves budget conflicts
    # Optimizes route and timing
    # Returns merged plan
```

**Features:**
- Removes duplicate suggestions
- Balances different budget constraints
- Optimizes travel efficiency
- Creates consensus without bias

**Fintech Application:** Multi-party financial consensus (like syndicated lending)

---

### 3. Expense Settlement Agent 💸 (SplitSense AI)

**Purpose:** Natural language expense tracking and smart settlements

**How it works:**
```python
def process_expense_split(message, room_expenses_context):
    # Parses natural language expense
    # Extracts: amount, payer, split count
    # Maintains running balances
    # Calculates who owes whom
```

**Advanced Features:**
- Persistent context across all messages
- Debt graph optimization (minimizes transactions)
- Real-time balance updates
- Settlement instructions generation
