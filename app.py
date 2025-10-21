import streamlit as st
from openai import OpenAI

# إعداد الاتصال بالـ API
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# --- عنوان التطبيق ---
st.title("📚 أداة تعليم اللهجة المصرية")

# --- اختيار الوحدة والدرس ---
st.sidebar.header("اختيار الدرس")
unit = st.sidebar.selectbox("اختر رقم الوحدة:", ["الوحدة 1", "الوحدة 2", "الوحدة 3"])
lesson_type = st.sidebar.radio("اختر نوع الدرس:", ["شرح الدرس", "تمارين عامة"])

if lesson_type == "شرح الدرس":
    lesson = st.sidebar.selectbox("اختر رقم الدرس:", ["الدرس 1", "الدرس 2", "الدرس 3"])

# دالة لتوليد الرد من الذكاء الاصطناعي
def generate_ai_response(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# --- التبويبات ---
if lesson_type == "شرح الدرس":
    tab1, tab2, tab3 = st.tabs(["📘 الشرح", "💬 تمارين حوارية", "📝 اختيار من متعدد"])

    with tab1:
        st.subheader("شرح الدرس")
        if st.button("ابدأ الشرح"):
            prompt = f"أنت الآن معلم لغة عربية محترف لغير الناطقين بها. اشرح درس {lesson} من {unit} بأسلوب بسيط وسهل الفهم."
            result = generate_ai_response(prompt)
            st.write(result)

    with tab2:
        st.subheader("تمارين حوارية")
        if st.button("ابدأ التمرين"):
            prompt = f"أنشئ محادثة تعليمية باللغة العربية الفصحى من {unit} - {lesson}، لتدريب الطالب على التحدث بطلاقة."
            result = generate_ai_response(prompt)
            st.write(result)

    with tab3:
        st.subheader("اختيار من متعدد")
        if st.button("ابدأ الاختبار"):
            prompt = f"اكتب 5 أسئلة اختيار من متعدد حول {lesson} من {unit} مع 4 خيارات لكل سؤال وحدد الإجابة الصحيحة."
            result = generate_ai_response(prompt)
            st.write(result)

else:
    st.subheader("💡 تمارين عامة على الوحدة")
    if st.button("ابدأ التمرين العام"):
        prompt = f"أنشئ تمرين عام على {unit} باللغة العربية الفصحى لمستوى المبتدئين مع تصحيح الإجابات بعد الحل."
        result = generate_ai_response(prompt)
        st.write(result)

prompts = st.secrets["lessons"]

lesson_prompt = prompts["lesson1"]
