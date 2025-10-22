st.session_state[chat_key].append({"role": "assistant", "content": chunk})
st.rerun()

        user_input = st.chat_input("Interact with the Tutor for more explanation")
        user_input = st.chat_input("Interact with the Tutor for more explanation", key="lesson1_explain_input")
if user_input:
chunks = get_ai_response_chunks(prompts["lesson1_explanation"], user_input)
st.session_state[chat_key].append({"role": "user", "content": user_input})
@@ -80,7 +80,7 @@ def get_ai_response_chunks(prompt, user_input=None):
st.session_state[chat_key].append({"role": "assistant", "content": chunk})
st.rerun()

        user_input = st.chat_input("Write your answer here ....")
        user_input = st.chat_input("Write your answer here ....", key="lesson1_dialogue_input")
if user_input:
chunks = get_ai_response_chunks(prompts["lesson1_dialogue"], user_input)
st.session_state[chat_key].append({"role": "user", "content": user_input})
@@ -104,7 +104,7 @@ def get_ai_response_chunks(prompt, user_input=None):
st.session_state[chat_key].append({"role": "assistant", "content": chunk})
st.rerun()

        user_input = st.chat_input("Write your answer here ....")
        user_input = st.chat_input("Write your answer here ....", key="lesson1_mcq_input")
if user_input:
chunks = get_ai_response_chunks(prompts["lesson1_mcq"], user_input)
st.session_state[chat_key].append({"role": "user", "content": user_input})
@@ -128,7 +128,7 @@ def get_ai_response_chunks(prompt, user_input=None):
st.session_state[chat_key].append({"role": "assistant", "content": chunk})
st.rerun()

    user_input = st.chat_input("Write your answer here...")
    user_input = st.chat_input("Write your answer here...", key="general_exercises_input")
if user_input:
chunks = get_ai_response_chunks(prompts["general_exercises"], user_input)
st.session_state[chat_key].append({"role": "user", "content": user_input})
