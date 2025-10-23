# app.py
import streamlit as st
from openai import OpenAI
from typing import List

# ---------------------------
#  CONFIG / STYLES
# ---------------------------
st.set_page_config(page_title="Egyptian Dialect AI Tutor", layout="centered", page_icon="🎓")
st.markdown(
    """
    <style>
    /* Modern clean container */
    .main {
        background-color: #f7fbff;
        padding: 18px;
        border-radius: 14px;
        box-shadow: 0 6px 22px rgba(17,24,39,0.06);
    }
    header .decoration {
        font-size: 14px;
        color: #0f172a;
    }
    .big-title {
        font-size:28px;
        font-weight:700;
        margin-bottom:6px;
    }
    .subtitle {
        color: #334155;
        margin-bottom: 14px;
    }
    .chat-box {
        border-radius: 12px;
        padding: 10px;
        background: white;
        box-shadow: 0 2px 8px rgba(15,23,42,0.04);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
#  OPENAI CLIENT
# ---------------------------
if "OPENAI_API_KEY" not in st.secrets:
    st.error("OpenAI API key not found in st.secrets. Please add OPENAI_API_KEY.")
    st.stop()

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# ---------------------------
#  HELPERS
# ---------------------------
def safe_split_text(text: str, chunk_size: int = 600) -> List[str]:
    """Split long assistant text into readable chunks using punctuation fallbacks."""
    chunks = []
    while len(text) > chunk_size:
        # prefer sentence boundaries: ., Arabic comma/،, question marks
        candidates = [text.rfind(p, 0, chunk_size) for p in (".", "،", "?", "؟", "!")]
        split_index = max(candidates)
        if split_index <= 0:
            split_index = chunk_size
        chunks.append(text[:split_index+1].strip())
        text = text[split_index+1:].strip()
    if text:
        chunks.append(text)
    return chunks

def get_model_response(messages: List[dict], max_tokens: int = 600) -> str:
    """Call OpenAI chat completions and return assistant text. Wrap with minimal error handling."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"API error: {e}")
        return "Sorry — an error occurred while contacting the model."


def ensure_history(key: str, system_prompt: str):
    """Ensure a conversation history exists for a lesson/tab with initial system prompt."""
    if key not in st.session_state:
        st.session_state[key] = [{"role": "system", "content": system_prompt}]

def append_and_get_chunks(history_key: str, user_content: str):
    """Append user message to history, call model, append assistant chunks, and return chunks."""
    st.session_state[history_key].append({"role": "user", "content": user_content})
    assistant_text = get_model_response(st.session_state[history_key])
    # append assistant as one message (we keep raw) then split for display
    st.session_state[history_key].append({"role": "assistant", "content": assistant_text})
    return safe_split_text(assistant_text)

# ---------------------------
#  Load lessons prompts from secrets
# ---------------------------
if "lessons" not in st.secrets:
    st.error("No 'lessons' found in st.secrets. Please add your lessons prompts under [lessons].")
    st.stop()

prompts = st.secrets["lessons"]

# ---------------------------
#  Sidebar: Unit & Lesson selection
# ---------------------------
with st.sidebar:
    st.markdown("<div class='main'><div class='big-title'>Egyptian Dialect AI Tutor 🎓</div>"
                "<div class='subtitle'>Learn Egyptian Arabic with interactive lessons</div></div>", unsafe_allow_html=True)
    st.markdown("### Course")
    # NOTE: you can expand to multiple units; for now we read keys from secrets or default
    unit_options = prompts.get("units", ["Unit 1"])
    unit_choice = st.selectbox("Choose Unit", unit_options, index=0, key="sidebar_unit")

    # lessons list: we expect secrets["lessons"] to contain keys like lesson1_explanation, lesson1_dialogue, lesson1_mcq, general_exercises
    lesson_items = prompts.get("available_lessons", ["Lesson 1", "General Exercises"])
    lesson_choice = st.selectbox("Choose Lesson", lesson_items, index=0, key="sidebar_lesson")

    st.divider()
    st.markdown("### Settings")
    model_choice = st.selectbox("Model", ["gpt-4o-mini"], index=0)
    st.caption("Model choice stored for future extension.")
    st.button("Reset session", on_click=lambda: st.session_state.clear())

# ---------------------------
#  Main layout header
# ---------------------------
st.markdown("<div class='main'><div class='big-title'>Learn Egyptian Dialect — Modern UI</div>"
            "<div class='subtitle'>Interactive explanation, dialogue practice, and multiple choice.</div></div>",
            unsafe_allow_html=True)

# ---------------------------
#  Determine flow
# ---------------------------
# Map lesson_choice -> secret keys (you can adjust naming convention in secrets.toml)
# convention: lessonX_explanation, lessonX_dialogue, lessonX_mcq
def get_keys_for_lesson(lesson_label: str):
    """Return secret keys for explanation/dialogue/mcq given a label like 'Lesson 1'"""
    normalized = lesson_label.lower().replace(" ", "")
    base = normalized.replace("lesson", "lesson")  # placeholder in case you change mapping
    # simple fixed mapping for 'Lesson 1' -> lesson1_*
    if "lesson1" in normalized:
        return ("lesson1_explanation", "lesson1_dialogue", "lesson1_mcq")
    elif "general" in normalized:
        return ("general_exercises", None, None)
    else:
        # fallback: try to build
        idx = ''.join([ch for ch in normalized if ch.isdigit()])
        if idx:
            return (f"lesson{idx}_explanation", f"lesson{idx}_dialogue", f"lesson{idx}_mcq")
        return ("general_exercises", None, None)

explain_key, dialogue_key, mcq_key = get_keys_for_lesson(lesson_choice)

# ---------------------------
#  LESSON: Explanation / Dialogue / MCQ
# ---------------------------
# ---------------------------
#  LESSON: 2 Tabs (Explanation + Practice)
# ---------------------------
def lesson_two_tabs(explain_key, lesson_key, lesson_label):
    system_prompt = prompts.get("system_prompt", "You are a professional Egyptian Arabic teacher for English speakers.")

    # --- EXPLANATION TAB ---
    explain_history_key = f"{lesson_label}_explain_history"
    ensure_history(explain_history_key, prompts.get(explain_key, system_prompt))

    # --- PRACTICE TAB ---
    practice_history_key = f"{lesson_label}_practice_history"
    ensure_history(practice_history_key, prompts.get(lesson_key, system_prompt))

    tab1, tab2 = st.tabs(["📘 Explanation", "🧩 Practice Exercises"])

    # ---------------------- Tab 1: Explanation ----------------------
    # ---------------------- Tab 1: Explanation ----------------------
    with tab1:
        with st.expander("💡 How to use this explanation", expanded=True):
            st.markdown("""
            **Follow these simple steps before starting:**
    
            1️⃣ **Click "Start Explanation"** to generate the full lesson explanation.  
            2️⃣ The tutor will explain the dialogue in English with Arabic + Latin pronunciation.  
            3️⃣ You can **ask about any word, phrase, or pronunciation** using the chat below.  
            4️⃣ If you don’t understand something, just ask — the tutor will rephrase it kindly.  
            5️⃣ Stay relaxed and interactive — this is your private Arabic learning space 🎧  
            """)
    
        st.markdown("### 📘 Explanation")
        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
        for msg in st.session_state[explain_history_key]:
            if msg["role"] == "system":
                continue
            st.chat_message(msg["role"]).markdown(msg["content"])
    
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Start Explanation", key=f"start_explain_{lesson_label}"):
                with st.spinner("Generating explanation..."):
                    # use higher token limit for explanation
                    assistant_text = get_model_response(st.session_state[explain_history_key], max_tokens=1500)
                    st.session_state[explain_history_key].append({"role": "assistant", "content": assistant_text})
                    st.rerun()

    
        with col2:
            user_input = st.chat_input("Ask about the lesson explanation...", key=f"explain_input_{lesson_label}")
            if user_input:
                append_and_get_chunks(explain_history_key, user_input)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    
    # ---------------------- Tab 2: Practice Exercises ----------------------
    with tab2:
        with st.expander("📋 How to use this practice", expanded=True):
            st.markdown("""
            **Follow these simple steps before starting:**
    
            1️⃣ **Click "Start Practice"** to begin the exercises.  
            2️⃣ You can answer in **Arabic or Latin letters** (Arabic is preferred).  
            3️⃣ If the AI Tutor asks for Arabic but you can’t, reply:  
               _"I’ll use Latin instead."_  
            4️⃣ **Feel free to ask questions** if you don’t understand something.  
            5️⃣ The AI Tutor will guide you kindly **step by step** 💬  
            """)
    
        st.markdown("### 🧩 Practice Exercises")
        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
        for msg in st.session_state[practice_history_key]:
            if msg["role"] == "system":
                continue
            st.chat_message(msg["role"]).markdown(msg["content"])
    
        col1, col2 = st.columns([1, 2])
        with col1:
            if st.button("Start Practice", key=f"start_practice_{lesson_label}"):
                with st.spinner("Preparing exercises..."):
                    assistant_text = get_model_response(st.session_state[practice_history_key])
                    st.session_state[practice_history_key].append({"role": "assistant", "content": assistant_text})
                    st.rerun()
    
        with col2:
            user_input = st.chat_input("Answer or ask for help...", key=f"practice_input_{lesson_label}")
            if user_input:
                append_and_get_chunks(practice_history_key, user_input)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)



# ---------------------------
#  GENERAL EXERCISES (single tab)
# ---------------------------
def general_exercises_tab(general_key):
    # ---------- Usage Instructions ----------
    with st.expander("📋 How to use this practice", expanded=True):
        st.markdown("""
        **Follow these simple steps before starting:**
    
        1️⃣ **Click "Start General Exercises"** to begin the conversation.  
        2️⃣ **Answer in Arabic script or Latin letters** (Latin is accepted, Arabic is preferred).  
        3️⃣ If the AI Tutor asks you to write in Arabic but you can’t — just say:  
           _"I can’t write in Arabic, I’ll use Latin instead."_  
        4️⃣ **Feel free to ask questions** anytime if you don’t understand something.  
        5️⃣ **Stay relaxed** — the AI Tutor will always reply kindly and help you learn step by step 💬
        """)
    system_prompt = prompts.get("system_prompt", "You are a professional Egyptian Arabic teacher for English speakers.")
    history_key = "general_exercises_history"
    ensure_history(history_key, prompts.get(general_key, system_prompt))

    st.subheader("💡 General Practice")
    st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
    for msg in st.session_state[history_key]:
        if msg["role"] == "system":
            continue
        if msg["role"] == "assistant":
            st.chat_message("assistant").markdown(msg["content"])
        else:
            st.chat_message("user").markdown(msg["content"])

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Start General Exercises", key="start_general"):
            with st.spinner("Generating exercises..."):
                assistant_text = get_model_response(st.session_state[history_key])
                st.session_state[history_key].append({"role": "assistant", "content": assistant_text})
                st.rerun()
    with col2:
        user_input = st.chat_input("Answer or practice here...", key="general_input")
        if user_input:
            append_and_get_chunks(history_key, user_input)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)




# ---------------------------
#  MAIN: Render appropriate UI
# ---------------------------
if "general" in lesson_choice.lower() or explain_key == "general_exercises":
    # show only general exercises tab
    general_exercises_tab("general_exercises")
else:
    # lesson with 2 tabs (Explanation + Practice)
    lesson_two_tabs(explain_key, f"{lesson_choice.lower()}", lesson_choice)

# ---------------------------
#  Footer: small tips and progress summary (basic)
# ---------------------------
st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    st.caption("Tip: Put long lesson prompts in st.secrets under [lessons] to avoid resending them every message.")
with col2:
    # show simple counts
    total_chats = sum(1 for k in st.session_state if k.endswith("_history"))
    st.metric("Active Conversations", total_chats)
