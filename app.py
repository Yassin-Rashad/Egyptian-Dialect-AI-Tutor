import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def get_ai_response(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

prompts = st.secrets["lessons"]

st.title("🎓 تطبيق تعليم اللهجة المصرية")

unit_choice = st.selectbox("اختر الوحدة", ["الوحدة 1"], key="unit_select")
lesson_choice = st.selectbox("اختر الدرس", ["الدرس 1", "تمارين عامة"], key="lesson_select")

tab1, tab2, tab3 = st.tabs(["📘 الشرح", "💬 التمارين الحوارية", "❓اختيار من متعدد"])

if lesson_choice == "الدرس 1":
    with tab1:
        if st.button("ابدأ الشرح", key="lesson1_explain_btn"):
            response = get_ai_response(prompts["lesson1_explanation"])
            st.text_area("نتيجة الشرح", response, height=400)

    with tab2:
        if st.button("ابدأ التمرين الحواري", key="lesson1_dialogue_btn"):
            response = get_ai_response(prompts["lesson1_dialogue"])
            st.text_area("نتيجة التمرين", response, height=400)

    with tab3:
        if st.button("ابدأ أسئلة الاختيار", key="lesson1_mcq_btn"):
            response = get_ai_response(prompts["lesson1_mcq"])
            st.text_area("نتيجة الأسئلة", response, height=400)

elif lesson_choice == "تمارين عامة":
    with tab1:
        if st.button("ابدأ التمرين العام", key="general_practice_btn"):
            response = get_ai_response(prompts["general_practice"])
            st.text_area("نتيجة التمرين العام", response, height=400)
