import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🎓 تطبيق تعليم اللهجة المصرية")

prompts = st.secrets["lessons"]

unit_choice = st.selectbox("اختر الوحدة", ["الوحدة 1"], key="unit_select")
lesson_choice = st.selectbox("اختر الدرس", ["الدرس 1", "تمارين عامة"], key="lesson_select")

tab1, tab2, tab3 = st.tabs(["📘 الشرح", "💬 التمارين الحوارية", "❓اختيار من متعدد"])

# تعريف دالة الذكاء الاصطناعي
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

# 🟦 الدرس 1
if lesson_choice == "الدرس 1":
    # تبويب الشرح
    with tab1:
        st.subheader("📘 الشرح")
        if "lesson1_chat" not in st.session_state:
            st.session_state.lesson1_chat = []

        for msg in st.session_state.lesson1_chat:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ الشرح", key="lesson1_explain_btn"):
            ai_response = get_ai_response(prompts["lesson1_explanation"])
            st.session_state.lesson1_chat.append({"role": "assistant", "content": ai_response})
            st.rerun()

        user_input = st.chat_input("اكتب ردّك أو سؤالك هنا...")
        if user_input:
            ai_response = get_ai_response(prompts["lesson1_explanation"], user_input)
            st.session_state.lesson1_chat.append({"role": "user", "content": user_input})
            st.session_state.lesson1_chat.append({"role": "assistant", "content": ai_response})
            st.rerun()

    # تبويب التمارين الحوارية
    with tab2:
        st.subheader("💬 التمارين الحوارية")
        if "lesson1_dialogue" not in st.session_state:
            st.session_state.lesson1_dialogue = []

        for msg in st.session_state.lesson1_dialogue:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ التمرين", key="lesson1_dialogue_btn"):
            ai_response = get_ai_response(prompts["lesson1_dialogue"])
            st.session_state.lesson1_dialogue.append({"role": "assistant", "content": ai_response})
            st.rerun()

        user_input = st.chat_input("اكتب ردّك في التمرين هنا...")
        if user_input:
            ai_response = get_ai_response(prompts["lesson1_dialogue"], user_input)
            st.session_state.lesson1_dialogue.append({"role": "user", "content": user_input})
            st.session_state.lesson1_dialogue.append({"role": "assistant", "content": ai_response})
            st.rerun()

    # تبويب اختيار من متعدد
    with tab3:
        st.subheader("❓ أسئلة اختيار من متعدد")
        if "lesson1_mcq" not in st.session_state:
            st.session_state.lesson1_mcq = []

        for msg in st.session_state.lesson1_mcq:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ الأسئلة", key="lesson1_mcq_btn"):
            ai_response = get_ai_response(prompts["lesson1_mcq"])
            st.session_state.lesson1_mcq.append({"role": "assistant", "content": ai_response})
            st.rerun()

        user_input = st.chat_input("اكتب إجابتك هنا...")
        if user_input:
            ai_response = get_ai_response(prompts["lesson1_mcq"], user_input)
            st.session_state.lesson1_mcq.append({"role": "user", "content": user_input})
            st.session_state.lesson1_mcq.append({"role": "assistant", "content": ai_response})
            st.rerun()


# 🟩 تمارين عامة
elif lesson_choice == "تمارين عامة":
    with tab1:
        st.subheader("💡 تمرين عام")
        if "general_chat" not in st.session_state:
            st.session_state.general_chat = []

        for msg in st.session_state.general_chat:
            st.chat_message(msg["role"]).markdown(msg["content"])

        if st.button("ابدأ التمرين العام", key="general_practice_btn"):
            ai_response = get_ai_response(prompts["general_practice"])
            st.session_state.general_chat.append({"role": "assistant", "content": ai_response})
            st.rerun()

        user_input = st.chat_input("شارك إجابتك أو سؤالك هنا...")
        if user_input:
            ai_response = get_ai_response(prompts["general_practice"], user_input)
            st.session_state.general_chat.append({"role": "user", "content": user_input})
            st.session_state.general_chat.append({"role": "assistant", "content": ai_response})
            st.rerun()
