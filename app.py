import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
st.title("🎓 تطبيق تعليم اللهجة المصرية")

prompts = st.secrets["lessons"]

unit_choice = st.selectbox("اختر الوحدة", ["الوحدة 1"], key="unit_select")
lesson_choice = st.selectbox("اختر الدرس", ["الدرس 1", "تمارين عامة"], key="lesson_select")

# ====== دوال تقسيم النصوص ======
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

def get_ai_response_chunks(prompt, user_input=None):
    messages = [{"role": "system", "content": "You are a friendly Egyptian Arabic teacher for English speakers."}]
    messages.append({"role": "user", "content": prompt})
    if user_input:
        messages.append({"role": "user", "content": f"الطالب قال: {user_input}"})
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=600
    )
    text = response.choices[0].message.content
    return split_text(text, chunk_size=600)

# ====== تبويبات الدرس 1 ======
if lesson_choice == "الدرس 1":
    tab1, tab2, tab3 = st.tabs(["📘 الشرح", "💬 التمارين الحوارية", "❓اختيار من متعدد"])

    # ====== الشرح ======
    with tab1:
        st.subheader("📘 الشرح")
        chat_key = "lesson1_explain_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ الشرح", key="start_explain"):
            chunks = get_ai_response_chunks(prompts["lesson1_explanation"])
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

        user_input = st.chat_input("اكتب ردّك أو سؤالك هنا (للشرح)...")
        if user_input:
            chunks = get_ai_response_chunks(prompts["lesson1_explanation"], user_input)
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

    # ====== التمارين الحوارية ======
    with tab2:
        st.subheader("💬 التمارين الحوارية")
        chat_key = "lesson1_dialogue_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ التمرين", key="start_dialogue"):
            chunks = get_ai_response_chunks(prompts["lesson1_dialogue"])
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

        user_input = st.chat_input("اكتب ردّك هنا (للتمارين)...")
        if user_input:
            chunks = get_ai_response_chunks(prompts["lesson1_dialogue"], user_input)
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

    # ====== أسئلة اختيار من متعدد ======
    with tab3:
        st.subheader("❓ أسئلة اختيار من متعدد")
        chat_key = "lesson1_mcq_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ الأسئلة", key="start_mcq"):
            chunks = get_ai_response_chunks(prompts["lesson1_mcq"])
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

        user_input = st.chat_input("اكتب إجابتك هنا (للاختيار من متعدد)...")
        if user_input:
            chunks = get_ai_response_chunks(prompts["lesson1_mcq"], user_input)
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            for chunk in chunks:
                st.session_state[chat_key].append({"role": "assistant", "content": chunk})
            st.rerun()

# ====== تمارين عامة ======
elif lesson_choice == "تمارين عامة":
    st.subheader("💡 تمرين عام")
    chat_key = "general_chat"
    if chat_key not in st.session_state:
        st.session_state[chat_key] = []

    for msg in st.session_state[chat_key]:
        st.chat_message(msg["role"]).markdown(msg["content"])

    if st.button("ابدأ التمرين العام", key="general_exercises_btn"):
        chunks = get_ai_response_chunks(prompts["general_exercises"])
        for chunk in chunks:
            st.session_state[chat_key].append({"role": "assistant", "content": chunk})
        st.rerun()

    user_input = st.chat_input("شارك إجابتك أو سؤالك هنا...")
    if user_input:
        chunks = get_ai_response_chunks(prompts["general_exercises"], user_input)
        st.session_state[chat_key].append({"role": "user", "content": user_input})
        for chunk in chunks:
            st.session_state[chat_key].append({"role": "assistant", "content": chunk})
        st.rerun()
