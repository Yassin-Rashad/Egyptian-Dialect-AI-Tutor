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
lesson3_dialogue = load_prompt("unit1", "lesson3")
lesson3_practice = load_prompt("unit1", "lesson3_practice")
lesson4_dialogue = load_prompt("unit1", "lesson4")
lesson4_practice = load_prompt("unit1", "lesson4_practice")
lesson5_dialogue = load_prompt("unit1", "lesson5")
lesson5_practice = load_prompt("unit1", "lesson5_practice")
lesson6_dialogue = load_prompt("unit1", "lesson6")
lesson6_practice = load_prompt("unit1", "lesson6_practice")
general_dialogue = load_prompt("unit1", "general")

prompts = {
    "Lesson 1 Dialogue": lesson1_dialogue,
    "Lesson 1 Practice": lesson1_practice,
    "Lesson 2 Dialogue": lesson2_dialogue,
    "Lesson 2 Practice": lesson2_practice,
    "Lesson 3 Dialogue": lesson3_dialogue,
    "Lesson 3 Practice": lesson3_practice,
    "Lesson 4 Dialogue": lesson4_dialogue,
    "Lesson 4 Practice": lesson4_practice,
    "Lesson 5 Dialogue": lesson5_dialogue,
    "Lesson 5 Practice": lesson5_practice,
    "Lesson 6 Dialogue": lesson6_dialogue,
    "Lesson 6 Practice": lesson6_practice,
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
api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
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

    # ✅ نتحقق هل الموديل أنهى الدرس
    if "### END_OF_LESSON" in assistant_text:
        st.session_state["stop_training"] = True

    st.session_state[history_key].append({"role": "assistant", "content": assistant_text})
    return safe_split_text(assistant_text)


# ---------------------------
#  SIDEBAR
# ---------------------------
with st.sidebar:
    st.markdown("<div class='main'><div class='big-title'>Egyptian Dialect AI Tutor 🎓</div>"
                "<div class='subtitle'>Learn Egyptian Arabic with interactive lessons</div></div>", unsafe_allow_html=True)
    st.markdown("### Course")

    # ✅ استخدم query_params الجديدة
    params = dict(st.query_params)
    unit_options = ["Unit 1"]
    lesson_items = ["Lesson 1", "Lesson 2", "Lesson 3", "Lesson 4", "Lesson 5", "Lesson 6", "General Exercises"]


    # اقرأ القيم من الرابط أو استخدم الافتراضي
    default_unit = params.get("unit", "Unit 1")
    default_lesson = params.get("lesson", "Lesson 1")

    # لو القيم مش ضمن القوائم، استخدم الافتراضي
    if default_unit not in unit_options:
        default_unit = "Unit 1"
    if default_lesson not in lesson_items:
        default_lesson = "Lesson 1"

    # الصناديق
    unit_choice = st.selectbox("Choose Unit", unit_options,
                               index=unit_options.index(default_unit))
    lesson_choice = st.selectbox("Choose Lesson", lesson_items,
                                 index=lesson_items.index(default_lesson))

    # ✅ حدّث الرابط لو تغيّر الاختيار
    if (unit_choice != default_unit) or (lesson_choice != default_lesson):
        st.query_params = {"unit": unit_choice, "lesson": lesson_choice}

    st.divider()
    st.markdown("### Settings")
    model_choice = st.selectbox("Model", ["gpt-4o-mini"], index=0)
    st.caption("Model choice stored for future extension.")

    if st.button("Reset session"):
        st.session_state.clear()
        st.query_params = {"unit": "Unit 1", "lesson": "Lesson 1"}
        st.rerun()


# ---------------------------
#  MAIN HEADER (MODERN STYLE)
# ---------------------------
st.markdown("""
<div class='main' style='text-align:center;'>
  <div class='big-title' style='font-size:32px; font-weight:800; color:#0f172a; margin-bottom:6px;'>
    Learn Egyptian Dialect — AI Tutor
  </div>
  <div class='subtitle' style='color:#475569; font-size:18px; margin-bottom:16px;'>
    Interactive explanation and real-time practice.
  </div>
  <div style='margin:0 auto; width:fit-content; padding:10px 16px; border-radius:14px; background-color:#f8fafc; display:flex; align-items:center; gap:10px; box-shadow:0 2px 6px rgba(15,23,42,0.08);'>
    <img src='https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg' width='22' style='vertical-align:middle;'/>
    <span style='color:#334155; font-size:15px;'>
      Created by <b style='color:#0f766e;'>Yassin Rashad</b> — 
      <a href='https://wa.me/201064958335' target='_blank' style='color:#22c55e; text-decoration:none; font-weight:600;'>
        Contact via WhatsApp
      </a>
      for private lessons & practice.
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

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
#  LESSON TWO TABS (works 100% with refresh)
# ---------------------------
def lesson_two_tabs(explain_key, lesson_key, lesson_label):
    system_prompt = "You are a professional Egyptian Arabic teacher for English speakers."
    explain_history_key = f"{lesson_label}_explain_history"
    practice_history_key = f"{lesson_label}_practice_history"

    ensure_history(explain_history_key, system_prompt)
    ensure_history(practice_history_key, system_prompt)

    # ✅ نقرأ التاب الحالي من الرابط أو نبدأ بـ Explanation
    params = dict(st.query_params)
    current_tab = params.get("tab", "Explanation")

    # ✅ نعرض تبويبات قابلة للحفظ
    # ✅ تنسيق شكل التبويبات (radio)
# ✅ تصميم تبويبات حديث بدون دوائر
    # ✅ تصميم تبويبات بلون محايد (بدون أخضر)
# ✅ تصميم تبويبات بلون محايد (بدون أخضر)
# ✅ تصميم تبويبات بلون أخضر أنيق مع مسافات مضبوطة
# ✅ تبويبات بلون أخضر أنيق ومتوازن (Padding مضبوط)
# ✅ تبويبات بلون أخضر أنيق ومتوازن (Padding مضبوط)
# ✅ تبويبات بلون أخضر أنيق ومسافات مظبوطة تمامًا
# ✅ تبويبات متوازنة ومظبوطة تمامًا من كل الجوانب
# ✅ تبويبات بدون علامة الراديو — تصميم أنيق وحديث
    st.markdown("""
        <style>
        /* إخفاء كل عناصر الراديو */
        div[role='radiogroup'] input[type='radio'],
        div[role='radiogroup'] svg {
            display: none !important;
        }

        /* ترتيب التبويبات */
        div[role='radiogroup'] {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-bottom: 20px;
        }

        /* الشكل العام للتبويب */
        div[role='radiogroup'] label {
            background: #f8fafc;
            border-radius: 10px;
            cursor: pointer;
            font-weight: 500;
            color: #334155;
            transition: all 0.25s ease;
            border: 1px solid transparent;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            display: flex;
            align-items: center;
        }

        /* ضبط النص داخل التبويب */
        div[role='radiogroup'] label > div:last-child {
            padding: 10px 28px;
        }

        /* عند المرور */
        div[role='radiogroup'] label:hover {
            background: #ecfdf5;
        }

        /* التبويب النشط */
        div[role='radiogroup'] input:checked + div {
            background: #d1fae5;
            border: 1px solid #10b981;
            color: #065f46 !important;
            font-weight: 600;
            box-shadow: 0 2px 6px rgba(16,185,129,0.15);
        }

        /* مسافة بين الأيقونة والنص */
        div[role='radiogroup'] label > div:first-child {
            margin-right: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

    tab_choice = st.radio(
        "Select section",
        ["📘 Explanation", "🧩 Practice Exercises"],
        horizontal=True,
        index=0 if current_tab == "Explanation" else 1,
        label_visibility="collapsed",
        key="lesson_tab_choice"
    )

    # ✅ نحدث الرابط لو المستخدم بدّل
    selected_tab = "Explanation" if "Explanation" in tab_choice else "Practice"
    if selected_tab != current_tab:
        st.query_params = {
            "unit": st.query_params.get("unit", "Unit 1"),
            "lesson": st.query_params.get("lesson", "Lesson 1"),
            "tab": selected_tab
        }

    # -------- TAB 1 (EXPLANATION) --------
    if selected_tab == "Explanation":
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

                    # دمج البرومبت الأساسي + محتوى الحوار في system واحد
                    full_system_prompt = (
                        base_explanation_prompt.strip() + "\n\n" +
                        dialogue_content.strip()
                    )

                    st.session_state[explain_history_key] = [
                        {"role": "system", "content": full_system_prompt}
                    ]

                    # أول رد من الموديل مباشرة بعد قراءة الملفات
                    assistant_text = get_model_response(st.session_state[explain_history_key], max_tokens=2500)
                    st.session_state[explain_history_key].append({"role": "assistant", "content": assistant_text})
                    st.rerun()

        with col2:
            user_input = st.chat_input("Ask about the lesson explanation...", key=f"explain_input_{lesson_label}")
            if user_input:
                append_and_get_chunks(explain_history_key, user_input)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # -------- TAB 2 (PRACTICE) --------
    else:
        st.markdown("### 🧩 Practice Exercises")
        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
        base_practice_prompt = prompts.get("Base Practice Prompt", "")
        lesson_practice_content = prompts.get(f"{lesson_label} Practice", "")

        if not base_practice_prompt.strip():
            st.warning("⚠️ The base practice prompt file (prompts/base/practice_prompt.txt) is missing or empty.")
        elif not lesson_practice_content.strip():
            st.warning("⚠️ No practice content found for this lesson (e.g. prompts/unit1/lesson1_practice.txt).")
        else:
            for msg in st.session_state.get(practice_history_key, []):
                if msg["role"] == "system":
                    continue
                st.chat_message(msg["role"]).markdown(msg["content"])

            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button("Start Practice", key=f"start_practice_{lesson_label}"):
                    with st.spinner("Preparing interactive exercises..."):
                        # دمج البرومبت الأساسي مع محتوى الدرس في system واحد
                        full_system_prompt = (
                            base_practice_prompt.strip() + "\n\n" +
                            lesson_practice_content.strip()
                        )
                        st.session_state[practice_history_key] = [
                            {"role": "system", "content": full_system_prompt}
                        ]

                        # أول استدعاء علشان يبدأ الموديل الحوار بناءً على التعليمات
                        assistant_text = get_model_response(st.session_state[practice_history_key], max_tokens=2500)
                        st.session_state[practice_history_key].append({"role": "assistant", "content": assistant_text})
                        st.rerun()


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
