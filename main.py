# --- Replace or insert these functions in your main.py ---

import time

def call_generate_with_retries(model_obj, prompt, max_retries=3, initial_delay=1, max_output_tokens=16):
    """
    Calls model_obj.generate_content with a short prompt and short token limit.
    Retries on transient quota/rate errors. Returns response or raises.
    """
    delay = initial_delay
    for attempt in range(1, max_retries + 1):
        try:
            # Use a minimal request so probing is cheap
            resp = model_obj.generate_content(prompt, max_output_tokens=max_output_tokens)
            return resp
        except Exception as e:
            msg = str(e).lower()
            # Retry only for rate/quota-like errors
            if attempt < max_retries and ("quota" in msg or "429" in msg or "rate" in msg or "limit" in msg):
                st.sidebar.info(f"Transient error probing model (attempt {attempt}/{max_retries}): {msg[:120]}... retrying in {delay}s")
                time.sleep(delay)
                delay *= 2
                continue
            # Non retriable or last attempt -> propagate
            raise

@st.cache_resource
def init_gemini():
    """
    Probes a list of candidate Gemini models to find one that:
      1) can be instantiated, and
      2) successfully responds to a tiny test prompt.
    Returns a model object for the first successful model.
    Displays probe results in the sidebar.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        st.error("⚠️ GEMINI_API_KEY missing. Set the GEMINI_API_KEY env var (Streamlit secrets).")
        st.stop()
    genai.configure(api_key=api_key)

    # Order of preference — includes 2.5 flash first, then sensible fallbacks
    candidate_models = [
        os.environ.get("GEMINI_MODEL"),  # if user set explicit prefered model in env
        "gemini-2.5-flash",
        "gemini-2.5",
        "gemini-2.0-flash-exp",
        "gemini-2.0-flash",
        "gemini-1.5-flash"
    ]
    # remove None and duplicates, keep order
    seen = set()
    candidate_models = [m for m in candidate_models if m and (m not in seen and not seen.add(m))]

    probe_results = []
    test_prompt = "Say hi in one word: Hi"

    for model_name in candidate_models:
        st.sidebar.write(f"Probing model: **{model_name}** ...")
        entry = {"model": model_name, "status": "unknown", "error": None}
        try:
            # 1) attempt to instantiate model wrapper
            try:
                model_obj = genai.GenerativeModel(model_name)
            except Exception as inst_e:
                entry["status"] = "init_failed"
                entry["error"] = str(inst_e)
                probe_results.append(entry)
                st.sidebar.warning(f"{model_name}: init failed ({str(inst_e)[:120]})")
                continue

            # 2) attempt a tiny generate_content call to detect quota/429
            try:
                resp = call_generate_with_retries(model_obj, test_prompt, max_retries=2, initial_delay=1, max_output_tokens=8)
                # if we get here, model responded
                entry["status"] = "ok"
                entry["error"] = None
                probe_results.append(entry)
                st.sidebar.success(f"{model_name}: probe succeeded — selecting this model.")
                # return the first working model
                return model_obj
            except Exception as gen_e:
                entry["status"] = "generate_failed"
                entry["error"] = str(gen_e)
                probe_results.append(entry)
                st.sidebar.warning(f"{model_name}: generate failed ({str(gen_e)[:120]})")
                continue

        except Exception as e:
            # catch-all
            entry["status"] = "error"
            entry["error"] = str(e)
            probe_results.append(entry)
            st.sidebar.warning(f"{model_name}: unexpected error ({str(e)[:120]})")
            continue

    # If none available, show detailed sidebar output and stop
    st.sidebar.error("No Gemini model available from the probe list. See probe results below.")
    for r in probe_results:
        st.sidebar.write(f"- {r['model']}: {r['status']} — {r['error'][:200] if r['error'] else ''}")
    # helpful guidance
    st.error("""
        No usable Gemini model was found. Common reasons:
        - Your GEMINI_API_KEY belongs to a project with no billing and the requested model has free_quota = 0.
        - The model name is invalid.
        - The project has exhausted rate limits.
        
        Solutions:
        1. Enable billing on the Google Cloud project if you need gemini-2.x models.
        2. Use gemini-1.5-flash (free-tier) by setting GEMINI_MODEL=gemini-1.5-flash.
        3. Inspect the sidebar probe messages for exact errors.
    """)
    st.stop()
