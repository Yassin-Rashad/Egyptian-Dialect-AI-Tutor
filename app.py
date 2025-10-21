import streamlit as st

st.set_page_config(page_title="تعلم اللهجة المصرية 🇪🇬", layout="wide")

st.title("🇪🇬 تعلم اللهجة المصرية بالذكاء الاصطناعي")

# اختيار الوحدة
unit = st.selectbox("اختر رقم الوحدة:", ["Unit 1", "Unit 2", "Unit 3"])

# اختيار الدرس أو تمارين عامة
lesson = st.selectbox("اختر الدرس أو تمارين عامة:", ["الدرس 1", "الدرس 2", "تمارين عامة"])

st.markdown("---")

if "تمارين عامة" in lesson:
    st.subheader(f"🧩 تمارين عامة على {unit}")
    user_input = st.text_area("اكتب هنا للتفاعل مع التمرين:", height=150)
    if st.button("إرسال"):
        # هنا هيشتغل prompt التمارين العامة
        st.write("🔹 النتيجة (رد الذكاء الاصطناعي):")
        st.write("_سيظهر هنا الرد من الـ API_")

else:
    st.subheader(f"📘 {lesson} - {unit}")
    tab1, tab2, tab3 = st.tabs(["شرح الدرس", "تمارين حوارية", "اختيار من متعدد"])

    with tab1:
        st.write("🧠 هنا هيظهر شرح الدرس باستخدام الـ prompt المخصص له")
        st.text_area("الشرح:", height=250)

    with tab2:
        st.write("💬 تمرين حواري تفاعلي مع الذكاء الاصطناعي")
        st.text_area("ابدأ المحادثة:", height=150)

    with tab3:
        st.write("📝 أسئلة اختيار من متعدد")
        st.text_area("الأسئلة:", height=200)
