# ---------- Drop-in replacement for hf_generate(...) and generate_day_plan(...) ----------
def hf_generate(prompt, max_length=512, temperature=0.2, retries=1, retry_delay=1.0):
    """
    Try a set of small/free HF models via the Router. Print status + response snippet for each attempt.
    Return the model text on success, or raise Exception if we want the caller to handle (we return None in this version).
    """
    cfg = init_hf()  # uses your existing init_hf to get API key & preferred
    api_key = cfg["api_key"]
    preferred = cfg.get("model") or cfg.get("preferred")  # handle both naming variants

    candidates = []
    if preferred:
        candidates.append(preferred)

    # Small/free models ordered by likely availability
    candidates += [
        "google/flan-t5-small",
        "google/flan-t5-base",
        "sshleifer/tiny-gpt2",
        "google/flan-t5-large",
        "facebook/bart-large-cnn"
    ]

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": max_length if isinstance(max_length, int) else 512,
            "temperature": temperature,
            "return_full_text": False
        },
        "options": {"wait_for_model": True}
    }

    diagnostics = []
    for model in candidates:
        url = f"https://router.huggingface.co/hf-inference/models/{model}"
        st.info(f"Trying HF model: `{model}` (router URL: {url})")
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
        except Exception as e:
            diagnostics.append({"model": model, "error": str(e)})
            st.error(f"Request exception for {model}: {e}")
            continue

        status = resp.status_code
        body = (resp.text or "")[:3000]  # keep long snippet but bounded
        diagnostics.append({"model": model, "status": status, "body": body})
        st.write(f"Model `{model}` → status: {status}")
        st.code(body, language="json")

        if status == 200:
            # Attempt to interpret known shapes, return first plausible text result
            try:
                data = resp.json()
                # Common shapes: list with generated_text or dict with generated_text
                if isinstance(data, list) and data and "generated_text" in data[0]:
                    return data[0]["generated_text"]
                if isinstance(data, dict) and "generated_text" in data:
                    return data["generated_text"]
                # Chat-ish shape: choices -> message -> content
                if isinstance(data, dict) and "choices" in data and isinstance(data["choices"], list):
                    choice = data["choices"][0]
                    if isinstance(choice, dict):
                        if "text" in choice:
                            return choice["text"]
                        if "message" in choice and isinstance(choice["message"], dict):
                            msg = choice["message"]
                            content = msg.get("content")
                            if isinstance(content, list):
                                texts = [c.get("text","") for c in content if isinstance(c, dict)]
                                return " ".join(texts).strip()
                            if isinstance(content, dict) and "text" in content:
                                return content["text"]
                # Fallback: return raw text
                return resp.text.strip()
            except ValueError:
                # resp wasn't JSON — return raw text
                return resp.text.strip()
        else:
            # non-200, try next candidate
            continue

    # If no model succeeded, show diagnostics (already partially shown above)
    diag_lines = []
    for d in diagnostics:
        if "status" in d:
            diag_lines.append(f"model={d['model']} status={d['status']}")
        else:
            diag_lines.append(f"model={d['model']} error={d.get('error')}")
    st.error("All HF model attempts failed. Diagnostics: " + " | ".join(diag_lines))

    # Return None to signal failure; caller can use fallback
    return None


def generate_day_plan(current_location, radius, budget, interests, additional_info):
    """
    Uses hf_generate() to request a JSON plan. If HF fails, return a deterministic fallback plan
    (so UI can continue working during debugging).
    """
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
        # Try HF
        response_text = hf_generate(prompt, max_length=512)
        if response_text:
            parsed = extract_json_from_text(response_text)
            if parsed:
                return parsed
            # Try direct json load
            try:
                return json.loads(response_text.strip())
            except Exception:
                # if HF returned plain text, still capture it as a simple plan
                return {
                    "destinations": [{
                        "name": f"AI-generated: {current_location}",
                        "address": "Various locations",
                        "distance_km": max(1, radius // 2),
                        "category": "mixed",
                        "time_slot": "all-day",
                        "duration": "8 hours",
                        "activities": [response_text[:200]],
                        "costs": {"entry": int(budget * 0.25), "food": int(budget * 0.35), "transport": int(budget * 0.25), "misc": int(budget * 0.15)},
                        "total_cost": int(budget),
                        "transport_from_previous": {"mode": "Metro/Cab", "cost": int(budget * 0.1), "time": "30 mins"}
                    }],
                    "itinerary": {
                        "morning": ["9:00 AM - Start (AI suggestions)"],
                        "afternoon": ["1:00 PM - Lunch & local activities"],
                        "evening": ["6:00 PM - Evening & dinner"]
                    },
                    "total_budget": {
                        "transport": int(budget * 0.25),
                        "food": int(budget * 0.35),
                        "activities": int(budget * 0.25),
                        "miscellaneous": int(budget * 0.15),
                        "total": int(budget)
                    },
                    "tips": ["Check local timings", "Carry water", "Keep small cash"]
                }
        else:
            # HF failed entirely — return a deterministic fallback plan
            st.warning("Hugging Face did not return a plan — using local fallback plan so you can continue testing.")
            return {
                "destinations": [{
                    "name": f"Exploring {current_location}",
                    "address": f"Central area near {current_location}",
                    "distance_km": max(1, radius // 2),
                    "category": "general",
                    "time_slot": "all-day",
                    "duration": "8 hours",
                    "activities": ["Sightseeing", "Local food", "Short walk"],
                    "costs": {"entry": int(budget * 0.2), "food": int(budget * 0.4), "transport": int(budget * 0.3), "misc": int(budget * 0.1)},
                    "total_cost": int(budget),
                    "transport_from_previous": {"mode": "Cab/Auto", "cost": int(budget * 0.1), "time": "20 mins"}
                }],
                "itinerary": {
                    "morning": ["9:00 AM - Meet & depart", "10:00 AM - Local attraction visit"],
                    "afternoon": ["1:00 PM - Lunch", "3:00 PM - Museum / Park"],
                    "evening": ["6:00 PM - Walk & snacks", "8:00 PM - Return"]
                },
                "total_budget": {
                    "transport": int(budget * 0.3),
                    "food": int(budget * 0.4),
                    "activities": int(budget * 0.2),
                    "miscellaneous": int(budget * 0.1),
                    "total": int(budget)
                },
                "tips": ["Fallback plan used — HF unavailable", "Test again after resolving HF issues"]
            }
    except Exception as e:
        st.error(f"Error generating plan: {e}")
        return None
# ---------- End replacements ----------
