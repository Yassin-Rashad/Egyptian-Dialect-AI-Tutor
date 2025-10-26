import streamlit as st
import os
from openai import OpenAI
from typing import List

# ---------------------------
#  LOAD PROMPTS
# ---------------------------
def load_prompt(unit, lesson, type_=""):
    """Load the content of a prompt file."""
    if type_:
        path = f"prompts/{unit}/{lesson}_{type_}.txt"
    else:
        path = f"prompts/{unit}/{lesson}.txt"
    if not os.path.exists(path):
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# ---------------------------
#  BASE PROMPTS + LESSONS
# ---------------------------
base_explanation_prompt = load_prompt("base", "explanation", "prompt")
base_practice_prompt = load_prompt("base", "practice", "prompt")
lesson1_dialogue = load_prompt("unit1", "lesson1")
lesson1_practice = load_prompt("unit1", "lesson1_practice")
lesson2_dialogue = load_prompt("unit1", "lesson2")
lesson2_practice = load_prompt("unit1", "lesson2_practice")
general_dialogue = load_prompt("unit1", "general")

prompts = {
    "Lesson 1 Dialogue": lesson1_dialogue,
    "Lesson 1 Practice": lesson1_practice,
    "Lesson 2 Dialogue": lesson2_dialogue,
    "Lesson 2 Practice": lesson2_practice,
    "General Dialogue": general_dialogue,
    "Base Explanation Prompt": base_explanation_prompt,
    "Base Practice Prompt": base_practice_prompt,
}

# ---------------------------
#  CONFIG / STYLES
# ---------------------------
st.set_page_config(page_title="Egyptian Dialect AI Tutor", layout="centered", page_icon="🎓")
st.markdown(
    """
    <style>
    .main {
        background-color: #f7fbff;
        padding: 18px;
        border-radius: 14px;
        box-shadow: 0 6px 22px rgba(17,24,39,0.06);
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
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("❌ OPENAI_API_KEY not found. Please set it as an environment variable.")
    st.stop()

client = OpenAI(api_key=api_key)

# ---------------------------
#  HELPERS
# ---------------------------
def safe_split_text(text: str, chunk_size: int = 600) -> List[str]:
    chunks = []
    while len(text) > chunk_size:
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
    """Call the model."""
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
    """Handle chat continuation."""
    st.session_state[history_key].append({"role": "user", "content": user_content})
    messages = st.session_state[history_key]
    assistant_text = get_model_response(messages, max_tokens=600)
    st.session_state[history_key].append({"role": "assistant", "content": assistant_text})
    return safe_split_text(assistant_text)

# ---------------------------
#  SIDEBAR
# ---------------------------
with st.sidebar:
    st.markdown("<div class='main'><div class='big-title'>Egyptian Dialect AI Tutor 🎓</div>"
                "<div class='subtitle'>Learn Egyptian Arabic with interactive lessons</div></div>", unsafe_allow_html=True)
    st.markdown("### Course")
    unit_options = ["Unit 1"]
    unit_choice = st.selectbox("Choose Unit", unit_options, index=0, key="sidebar_unit")
    lesson_items = ["Lesson 1", "Lesson 2", "General Exercises"]
    lesson_choice = st.selectbox("Choose Lesson", lesson_items, index=0, key="sidebar_lesson")
    st.divider()
    st.markdown("### Settings")
    model_choice = st.selectbox("Model", ["gpt-4o-mini"], index=0)
    st.caption("Model choice stored for future extension.")
    st.button("Reset session", on_click=lambda: st.session_state.clear())

# ---------------------------
#  MAIN HEADER
# ---------------------------
st.markdown("<div class='main'><div class='big-title'>Learn Egyptian Dialect — Modern UI</div>"
            "<div class='subtitle'>Interactive explanation, dialogue practice, and multiple choice.</div></div>",
            unsafe_allow_html=True)

# ---------------------------
#  LESSON HANDLER
# ---------------------------
def get_keys_for_lesson(lesson_label: str):
    normalized = lesson_label.lower().replace(" ", "")
    if "lesson1" in normalized:
        return ("lesson1_explanation", "lesson1_practice")
    elif "general" in normalized:
        return ("general_exercises", None)
    else:
        idx = ''.join([ch for ch in normalized if ch.isdigit()])
        if idx:
            return (f"lesson{idx}_explanation", f"lesson{idx}_practice")
        return ("general_exercises", None)

explain_key, practice_key = get_keys_for_lesson(lesson_choice)

# ---------------------------
#  LESSON TWO TABS
# ---------------------------
def lesson_two_tabs(explain_key, lesson_key, lesson_label):
    # إعداد الـ system prompt الأساسي
    system_prompt = "You are a professional Egyptian Arabic teacher for English speakers."
    explain_history_key = f"{lesson_label}_explain_history"
    practice_history_key = f"{lesson_label}_practice_history"

    ensure_history(explain_history_key, system_prompt)
    ensure_history(practice_history_key, system_prompt)

    tab1, tab2 = st.tabs(["📘 Explanation", "🧩 Practice Exercises"])

    # -------- TAB 1 (EXPLANATION) --------
    with tab1:
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
                    dialogue_content = prompts.get(f"{lesson_label} Dialogue", "")
                    base_explanation_prompt = prompts.get("Base Explanation Prompt", "")

                    # ✅ نفصل بوضوح بين الـsystem prompt والبيانات التعليمية
                    st.session_state[explain_history_key] = [
                        {"role": "system", "content": base_explanation_prompt},
                        {"role": "user", "content": f"Now explain this Egyptian Arabic dialogue step by step:\n\n{dialogue_content.strip()}"}
                    ]

                    assistant_text = get_model_response(
                        st.session_state[explain_history_key],
                        max_tokens=2500
                    )
                    st.session_state[explain_history_key].append({"role": "assistant", "content": assistant_text})
                    st.rerun()

        with col2:
            user_input = st.chat_input("Ask about the lesson explanation...", key=f"explain_input_{lesson_label}")
            if user_input:
                append_and_get_chunks(explain_history_key, user_input)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # -------- TAB 2 (PRACTICE) --------
    with tab2:
        st.markdown("### 🧩 Practice Exercises")
        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)

        base_practice_prompt = prompts.get("Base Practice Prompt", "")
        lesson_practice_content = prompts.get(f"{lesson_label} Practice", "")

        # تحقق من وجود الملفات
        if not base_practice_prompt.strip():
            st.warning("⚠️ The base practice prompt file (prompts/base/practice_prompt.txt) is missing or empty.")
        elif not lesson_practice_content.strip():
            st.warning("⚠️ No practice content found for this lesson (e.g. prompts/unit1/lesson1_practice.txt).")
        else:
            # عرض المحادثات السابقة
            for msg in st.session_state.get(practice_history_key, []):
                if msg["role"] == "system":
                    continue
                st.chat_message(msg["role"]).markdown(msg["content"])

            col1, col2 = st.columns([1, 2])

            # زر بدء التمارين
            with col1:
                if st.button("Start Practice", key=f"start_practice_{lesson_label}"):
                    with st.spinner("Preparing interactive exercises..."):
                        # ✅ نحافظ على سياق الجلسة، ونضيف المحتوى بشكل تفاعلي
                        st.session_state[practice_history_key] = [
                            {"role": "system", "content": base_practice_prompt},
                            {"role": "user", "content": f"Start training based on the following lesson content:\n\n{lesson_practice_content.strip()}"}
                        ]

                        assistant_text = get_model_response(
                            st.session_state[practice_history_key],
                            max_tokens=2500
                        )
                        st.session_state[practice_history_key].append({"role": "assistant", "content": assistant_text})
                        st.rerun()

            # إدخال إجابات الطالب
            with col2:
                user_input = st.chat_input("Answer or ask for help...", key=f"practice_input_{lesson_label}")
                if user_input:
                    append_and_get_chunks(practice_history_key, user_input)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------
#  MAIN
# ---------------------------
if "general" in lesson_choice.lower():
    st.write("🗣️ General exercises section coming soon.")
else:
    lesson_two_tabs(explain_key, practice_key, lesson_choice)

# ---------------------------
#  FOOTER
# ---------------------------
st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    st.caption("Tip: You can now keep one base prompt and just change dialogue or practice files per lesson!")
with col2:
    total_chats = sum(1 for k in st.session_state if k.endswith("_history"))
    st.metric("Active Conversations", total_chats)
