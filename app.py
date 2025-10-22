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

unit_choice = st.selectbox("اختر الوحدة", ["الوحدة 1"])
lesson_choice = st.selectbox("اختر الدرس", ["الدرس 1", "تمارين عامة"])

tab1, tab2, tab3 = st.tabs(["📘 الشرح", "💬 التمارين الحوارية", "❓اختيار من متعدد"])

if lesson_choice == "الدرس 1":
    with tab1:
        if st.button("Explaination", key="explain_btn"):
            response = get_ai_response(prompts["lesson1_explanation"])
            st.write(response)

    with tab2:
        if st.button("Speaking Practice", key="dialogue_btn"):
            response = get_ai_response(prompts["lesson1_dialogue"])
            st.write(response)

    with tab3:
        if st.button("MSQ Questions", key="mcq_btn"):
            response = get_ai_response(prompts["lesson1_mcq"])
            st.write(response)

elif lesson_choice == "تمارين عامة":
    with tab1:
        if st.button("General Exercises", key="general_btn"):
            response = get_ai_response(prompts["general_practice"])
            st.write(response)
