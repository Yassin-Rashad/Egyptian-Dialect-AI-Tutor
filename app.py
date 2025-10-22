import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
st.title("Learn Egyptian dialect with ai-Tutor🎓")

prompts = st.secrets["lessons"]

unit_choice = st.selectbox("Choose Unit", ["Unit 1"], key="unit_select")
lesson_choice = st.selectbox("Choose Lesson", ["Lesson 1", "General Exercises"], key="lesson_select")

# ====== تقسيم النصوص ======
def split_text(text, chunk_size=600):
    chunks = []
    while len(text) > chunk_size:
        split_index = text.rfind('.', 0, chunk_size)
        if split_index == -1:
            split_index = chunk_size
        chunks.append(text[:split_index+1].strip())
        text = text[split_index+1:].strip()
    if text:
        chunks.append(text)
    return chunks

# ====== استدعاء الـAI مع الاحتفاظ بالمحادثة ======
def get_ai_response(user_input=None, chat_history=[], initial_prompt=None):
    # system prompt ثابت لكل تبويب
    messages = []
    if not chat_history and initial_prompt:
        messages.append({"role": "system", "content": initial_prompt})
    
    # إضافة المحادثة السابقة
    messages.extend(chat_history)
    
    # إضافة input جديد أو initial prompt
    if user_input:
        messages.append({"role": "user", "content": user_input})
    elif initial_prompt:
        messages.append({"role": "user", "content": initial_prompt})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=600
    )
    
    text = response.choices[0].message.content
    return split_text(text, chunk_size=600)


# ====== Lesson 1 ======
if lesson_choice == "Lesson 1":
    tab1, tab2, tab3 = st.tabs(["📘 Explanation", "💬 Answer Questions", "❓ Multiple Choice"])

    # ====== Explanation ======
    with tab1:
        st.subheader("📘 Explanation")
        chat_key = "lesson1_explain_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("Explain", key="start_explain"):
            chunks = get_ai_response(chat_history=st.session_state[chat_key], initial_prompt=prompts["lesson1_explanation"])
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

        user_input = st.chat_input("Interact with the Tutor for more explanation", key="lesson1_explain_input")
        if user_input:
            chunks = get_ai_response(user_input=user_input, chat_history=st.session_state[chat_key])
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

    # ====== Answer Questions ======
    with tab2:
        st.subheader("💬 Answer Questions")
        chat_key = "lesson1_dialogue_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("Start Questions", key="start_dialogue"):
            chunks = get_ai_response(chat_history=st.session_state[chat_key], initial_prompt=prompts["lesson1_dialogue"])
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

        user_input = st.chat_input("Write your answer here ....", key="lesson1_dialogue_input")
        if user_input:
            chunks = get_ai_response(user_input=user_input, chat_history=st.session_state[chat_key])
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

    # ====== Multiple Choice ======
    with tab3:
        st.subheader("❓ Multiple Choice")
        chat_key = "lesson1_mcq_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("Start MCQ Questions", key="start_mcq"):
            chunks = get_ai_response(chat_history=st.session_state[chat_key], initial_prompt=prompts["lesson1_mcq"])
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

        user_input = st.chat_input("Write your answer here ....", key="lesson1_mcq_input")
        if user_input:
            chunks = get_ai_response(user_input=user_input, chat_history=st.session_state[chat_key])
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

# ====== General Exercises ======
elif lesson_choice == "General Exercises":
    st.subheader("💡 General Exercises")
    chat_key = "general_chat"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    for msg in st.session_state[chat_key]:
        st.chat_message(msg["role"]).markdown(msg["content"])

    if st.button("Start General Exercises", key="general_exercises_btn"):
        chunks = get_ai_response(chat_history=st.session_state[chat_key], initial_prompt=prompts["general_exercises"])
        for chunk in chunks:
            st.session_state[chat_key].append({"role": "assistant", "content": chunk})
        st.rerun()

    user_input = st.chat_input("Write your answer here...", key="general_exercises_input")
    if user_input:
        chunks = get_ai_response(user_input=user_input, chat_history=st.session_state[chat_key])
        st.session_state[chat_key].append({"role": "user", "content": user_input})
        for chunk in chunks:
            st.session_state[chat_key].append({"role": "assistant", "content": chunk})
        st.rerun()
