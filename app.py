import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🎓 تطبيق تعليم اللهجة المصرية")

prompts = st.secrets["lessons"]

unit_choice = st.selectbox("اختر الوحدة", ["الوحدة 1"], key="unit_select")
lesson_choice = st.selectbox("اختر الدرس", ["الدرس 1", "تمارين عامة"], key="lesson_select")

def get_ai_response(prompt, user_input=None):
    messages = [{"role": "system", "content": "You are a friendly Egyptian Arabic teacher for English speakers."}]
    messages.append({"role": "user", "content": prompt})
    if user_input:
        messages.append({"role": "user", "content": f"الطالب قال: {user_input}"})
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    return response.choices[0].message.content


if lesson_choice == "الدرس 1":
    tab1, tab2, tab3 = st.tabs(["📘 الشرح", "💬 التمارين الحوارية", "❓اختيار من متعدد"])
    # ====== تبويب الشرح ======
    with tab1:
        st.subheader("📘 الشرح")
        chat_key = "lesson1_explain_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ الشرح", key="start_explain"):
            ai_response = get_ai_response(prompts["lesson1_explanation"])
            st.session_state[chat_key].append({"role": "assistant", "content": ai_response})
            st.rerun()

        # ✅ مربع الشات هنا فقط
        user_input = st.chat_input("اكتب ردّك أو سؤالك هنا (للشرح)...")
        if user_input:
            ai_response = get_ai_response(prompts["lesson1_explanation"], user_input)
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            st.session_state[chat_key].append({"role": "assistant", "content": ai_response})
            st.rerun()


    # ====== تبويب التمارين ======
    with tab2:
        st.subheader("💬 التمارين الحوارية")
        chat_key = "lesson1_dialogue_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ التمرين", key="start_dialogue"):
            ai_response = get_ai_response(prompts["lesson1_dialogue"])
            st.session_state[chat_key].append({"role": "assistant", "content": ai_response})
            st.rerun()

        user_input = st.chat_input("اكتب ردّك هنا (للتمارين)...")
        if user_input:
            ai_response = get_ai_response(prompts["lesson1_dialogue"], user_input)
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            st.session_state[chat_key].append({"role": "assistant", "content": ai_response})
            st.rerun()


    # ====== تبويب الاختيار من متعدد ======
    with tab3:
        st.subheader("❓ أسئلة اختيار من متعدد")
        chat_key = "lesson1_mcq_chat"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []

        for msg in st.session_state[chat_key]:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ الأسئلة", key="start_mcq"):
            ai_response = get_ai_response(prompts["lesson1_mcq"])
            st.session_state[chat_key].append({"role": "assistant", "content": ai_response})
            st.rerun()

        user_input = st.chat_input("اكتب إجابتك هنا (للاختيار من متعدد)...")
        if user_input:
            ai_response = get_ai_response(prompts["lesson1_mcq"], user_input)
            st.session_state[chat_key].append({"role": "user", "content": user_input})
            st.session_state[chat_key].append({"role": "assistant", "content": ai_response})
            st.rerun()

# 🟩 تمارين عامة
elif lesson_choice == "تمارين عامة":
    st.subheader("💡 تمرين عام")
    if "general_chat" not in st.session_state:
        st.session_state.general_chat = []

    for msg in st.session_state.general_chat:
        st.chat_message(msg["role"]).markdown(msg["content"])

    if st.button("ابدأ التمرين العام", key="general_exercises_btn"):
        ai_response = get_ai_response(prompts["general_exercises"])
        st.session_state.general_chat.append({"role": "assistant", "content": ai_response})
        st.rerun()

    user_input = st.chat_input("شارك إجابتك أو سؤالك هنا...")
    if user_input:
        ai_response = get_ai_response(prompts["general_exercises"], user_input)
        st.session_state.general_chat.append({"role": "user", "content": user_input})
        st.session_state.general_chat.append({"role": "assistant", "content": ai_response})
        st.rerun()
