# app.py
import streamlit as st
import os
import io
import ssl
import platform
import socket
from typing import List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from openai import OpenAI

# ---------------------------
#  ENVIRONMENT DETECTION
# ---------------------------
def running_in_wsl() -> bool:
    return bool(os.environ.get("WSL_DISTRO_NAME") or "microsoft" in platform.uname().release.lower())

def running_on_cloud() -> bool:
    home_path = os.getenv("HOME", "")
    hostname = socket.gethostname().lower()
    if "streamlitapp" in hostname:
        return True
    if os.getenv("STREAMLIT_RUNTIME_ENV") == "cloud":
        return True
    if os.getenv("STREAMLIT_SERVER_HEADLESS") == "1":
        return True
    if home_path.startswith("/home/appuser"):
        return True
    return False

# ---------------------------
#  GOOGLE DRIVE SERVICE
# ---------------------------
@st.cache_resource
def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(st.secrets["google"])

    # ✅ نحاول نحل مشكلة SSL سواء في WSL أو Cloud
    try:
        ssl._create_default_https_context = ssl._create_unverified_context
    except Exception:
        pass

    # ✅ تفعيل build مع تجاوز SSL
    try:
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except ssl.SSLError:
        # fallback لو حصل SSL error
        import httplib2
        from googleapiclient.discovery import build as gbuild
        http = creds.authorize(httplib2.Http(disable_ssl_certificate_validation=True))
        return gbuild("drive", "v3", http=http)

@st.cache_resource
def list_drive_units_and_lessons():
    """List all units and lessons from Google Drive prompts folder with pagination fix."""
    service = get_drive_service()
    PROMPTS_FOLDER_ID = "125CxvdIJDW63ATcbbpTTrt_BJC5fX961"

    units = {}
    try:
        all_units = []
        page_token = None

        # 🧩 نجيب كل الوحدات (unit folders)
        while True:
            results = service.files().list(
                q=f"'{PROMPTS_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="nextPageToken, files(id, name)",
                pageToken=page_token
            ).execute()
            all_units.extend(results.get("files", []))
            page_token = results.get("nextPageToken", None)
            if page_token is None:
                break

        # 🧩 نستبعد base ونرتب الباقي بالأرقام
        unit_folders = sorted(
            [u for u in all_units if u["name"].lower().startswith("unit")],
            key=lambda x: int(''.join(filter(str.isdigit, x["name"])) or 0)
        )

        for unit in unit_folders:
            unit_name = unit["name"]
            unit_id = unit["id"]
            lessons = []
            page_token = None

            # 🧩 نجيب كل الدروس داخل الوحدة (مع pagination)
            while True:
                lesson_results = service.files().list(
                    q=f"'{unit_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="nextPageToken, files(id, name)",
                    pageToken=page_token
                ).execute()
                lessons.extend(lesson_results.get("files", []))
                page_token = lesson_results.get("nextPageToken", None)
                if page_token is None:
                    break

            # ✅ نرتب الدروس (lesson 1, lesson 2...) + general_exercises
            lesson_folders = sorted(
                [l for l in lessons if l["name"].lower().startswith("lesson") or l["name"].lower() == "general_exercises"],
                key=lambda x: (0 if "general" in x["name"].lower() else int(''.join(filter(str.isdigit, x["name"])) or 0))
            )

            units[unit_name] = [l["name"] for l in lesson_folders]

    except Exception as e:
        st.warning(f"⚠️ Couldn't list units/lessons from Drive: {e}")

    return units

@st.cache_resource
def read_file_from_drive(file_name, parent_folder_name=None):
    """Read text file from Google Drive with retry and SSL fallback."""
    import time
    import httplib2
    service = get_drive_service()
    PROMPTS_FOLDER_ID = "125CxvdIJDW63ATcbbpTTrt_BJC5fX961"

    # 🔁 نحاول لحد 3 مرات
    for attempt in range(3):
        try:
            if parent_folder_name:
                query = f"name='{file_name}' and trashed=false and '{parent_folder_name}' in parents"
            else:
                query = f"name='{file_name}' and trashed=false"

            results = service.files().list(
                q=query,
                fields="files(id, name, mimeType, parents)"
            ).execute()

            files = results.get("files", [])
            if not files:
                print(f"⚠️ File '{file_name}' not found in Drive.")
                return ""

            chosen_file = files[0]
            file_id = chosen_file["id"]
            mime = chosen_file["mimeType"]

            if mime.startswith("application/vnd.google-apps"):
                request = service.files().export_media(fileId=file_id, mimeType="text/plain")
            else:
                request = service.files().get_media(fileId=file_id)

            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

            fh.seek(0)
            content = fh.read().decode("utf-8", errors="ignore")
            print(f"✅ Loaded from Drive: {file_name}")
            return content

        except (ssl.SSLError, TimeoutError, ConnectionError, Exception) as e:
            print(f"⚠️ Attempt {attempt+1}/3 failed for '{file_name}': {e}")
            time.sleep(1.5)
            # ✅ في آخر محاولة نعمل fallback بدون SSL validation
            if attempt == 2:
                try:
                    creds = service_account.Credentials.from_service_account_info(st.secrets["google"])
                    http = creds.authorize(httplib2.Http(disable_ssl_certificate_validation=True))
                    service = build("drive", "v3", http=http, cache_discovery=False)
                except Exception:
                    pass

    return ""
# ---------------------------
#  PROMPTS LOADING (smart switch)
# ---------------------------
def load_prompt(unit: str, lesson: str, type_: str = "") -> str:
    """
    Loads lesson or practice/grammar file either locally or from Google Drive.
    Works with folder names like:
      prompts/unit1/lesson 1/lesson1.txt
      prompts/unit1/general_exercises/general_exercises.txt
    """
    # 🧩 حدد اسم الملف
    file_name = lesson.replace(" ", "").lower()
    if type_:
        file_name = f"{file_name}_{type_}.txt"
    else:
        file_name = f"{file_name}.txt"

    # 🧩 لو التطبيق شغال على Streamlit Cloud
    if running_on_cloud():
        service = get_drive_service()

        # 🔹 نجيب فولدر الوحدة (unit)
        unit_query = (
            f"(name='{unit}' or name='{unit.lower()}' or name='{unit.capitalize()}') "
            f"and mimeType='application/vnd.google-apps.folder' and trashed=false"
        )
        unit_results = service.files().list(q=unit_query, fields="files(id, name)").execute()
        unit_folders = unit_results.get("files", [])
        unit_id = unit_folders[0]["id"] if unit_folders else None

        lesson_id = None
        if unit_id:
            # 🔹 نجيب فولدر الدرس أو التمارين العامة
            lesson_query = (
                f"(name='{lesson}' or name='{lesson.lower()}' or name='{lesson.capitalize()}') "
                f"and '{unit_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            )
            lesson_results = service.files().list(q=lesson_query, fields="files(id, name)").execute()
            lesson_folders = lesson_results.get("files", [])
            lesson_id = lesson_folders[0]["id"] if lesson_folders else None

        # 🔹 نحدد الـ parent المناسب ونقرأ الملف
        parent_id = lesson_id or unit_id
        if parent_id:
            content = read_file_from_drive(file_name, parent_id)
            if content.strip():
                return content

    # 🧩 fallback محلي (لو شغال من الجهاز)
    if unit == "base":
        if type_:
            path = f"prompts/{unit}/{lesson}_{type_}.txt"
        else:
            path = f"prompts/{unit}/{lesson}.txt"
    else:
        path = f"prompts/{unit}/{lesson}/{lesson.replace(' ', '').lower()}"
        if type_:
            path += f"_{type_}.txt"
        else:
            path += ".txt"

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    return ""

# ---------------------------
#  BASE PROMPTS
# ---------------------------
base_explanation_prompt = load_prompt("base", "explanation", "prompt")
base_practice_prompt = load_prompt("base", "practice", "prompt")

# ---------------------------
#  LOAD ALL UNITS DYNAMICALLY
# ---------------------------
@st.cache_data(show_spinner=False)
def load_all_units() -> dict:
    data = {}
    if not os.path.exists("prompts"):
        drive_units = list_drive_units_and_lessons()
        data["Base Explanation Prompt"] = load_prompt("base", "explanation", "prompt")
        data["Base Practice Prompt"] = load_prompt("base", "practice", "prompt")
        for unit_name, lessons in drive_units.items():
            unit_label = unit_name.capitalize()
            for lesson_name in lessons:
                dialogue = load_prompt(unit_name, lesson_name)
                data[f"{lesson_name.capitalize()} Dialogue ({unit_label})"] = dialogue

                # ✅ نقرأ practice فقط لو الدرس مش general_exercises
                if lesson_name.lower() != "general_exercises":
                    practice = load_prompt(unit_name, lesson_name, "practice")
                    data[f"{lesson_name.capitalize()} Practice ({unit_label})"] = practice

            general = load_prompt(unit_name, "general_exercises")
            if general.strip():
                data[f"General Dialogue ({unit_label})"] = general
        return data


    data["Base Explanation Prompt"] = load_prompt("base", "explanation", "prompt")
    data["Base Practice Prompt"] = load_prompt("base", "practice", "prompt")
    for unit_name in sorted(os.listdir("prompts")):
        if not unit_name.lower().startswith("unit"):
            continue
        unit_path = os.path.join("prompts", unit_name)
        unit_label = f"Unit {unit_name.replace('unit', '').strip()}"
        general = load_prompt(unit_name, "general_exercises")
        data[f"General Dialogue ({unit_label})"] = general
        for lesson_folder in sorted(os.listdir(unit_path)):
            if not lesson_folder.lower().startswith("lesson"):
                continue
            dialogue = load_prompt(unit_name, lesson_folder)
            practice = load_prompt(unit_name, lesson_folder, "practice")
            data[f"{lesson_folder.capitalize()} Dialogue ({unit_label})"] = dialogue
            data[f"{lesson_folder.capitalize()} Practice ({unit_label})"] = practice
    return data

prompts = load_all_units()

# ---------------------------
#  UI CONFIG
# ---------------------------
st.set_page_config(page_title="Egyptian Dialect AI Tutor", layout="centered", page_icon="🎓")
st.markdown(
    """
    <style>
    .main { background-color: #f7fbff; padding: 18px; border-radius: 14px; box-shadow: 0 6px 22px rgba(17,24,39,0.06); }
    .big-title { font-size:28px; font-weight:700; margin-bottom:6px; }
    .subtitle { color: #334155; margin-bottom: 14px; }
    .chat-box { border-radius: 12px; padding: 10px; background: white; box-shadow: 0 2px 8px rgba(15,23,42,0.04); }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------
#  OPENAI CLIENT
# ---------------------------
api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
if not api_key:
    st.error("OPENAI_API_KEY not found. Please configure it in Streamlit secrets or environment.")
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
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"API error: {e}"

def ensure_history(key: str, system_prompt: str):
    if key not in st.session_state:
        st.session_state[key] = [{"role": "system", "content": system_prompt}]

def append_and_get_chunks(history_key: str, user_content: str) -> List[str]:
    st.session_state[history_key].append({"role": "user", "content": user_content})
    messages = st.session_state[history_key]
    assistant_text = get_model_response(messages, max_tokens=600)
    if "### END_OF_LESSON" in assistant_text:
        st.session_state["stop_training"] = True
    st.session_state[history_key].append({"role": "assistant", "content": assistant_text})
    return safe_split_text(assistant_text)

# ---------------------------
#  SESSION STATE INIT
# ---------------------------
current_unit = st.query_params.get("unit", "Unit 1")
current_lesson = st.query_params.get("lesson", "Lesson 1")
current_tab = st.query_params.get("tab", "Explanation")

st.session_state.setdefault("selected_unit", current_unit)
st.session_state.setdefault("selected_lesson", current_lesson)
st.session_state.setdefault("selected_tab", current_tab)

st.query_params["unit"] = st.session_state["selected_unit"]
st.query_params["lesson"] = st.session_state["selected_lesson"]
st.query_params["tab"] = st.session_state["selected_tab"]

# ---------------------------
#  NAV HANDLING
# ---------------------------
if "go_to_lesson" in st.session_state:
    target_lesson = st.session_state.pop("go_to_lesson")
    st.query_params = {
        "unit": st.session_state["selected_unit"],
        "lesson": target_lesson,
        "tab": st.session_state.get("selected_tab", "Explanation")
    }
    st.rerun()

if "go_to_lesson_change" in st.session_state:
    new_data = st.session_state.pop("go_to_lesson_change")
    st.session_state["selected_lesson"] = new_data["lesson"]
    st.session_state["selected_tab"] = new_data["tab"]
    st.query_params = new_data
    st.rerun()

# ---------------------------
#  SIDEBAR
# ---------------------------
with st.sidebar:
    st.markdown("<div class='main'><div class='big-title'>Egyptian Dialect AI Tutor 🎓</div>"
                "<div class='subtitle'>Learn Egyptian Arabic with interactive lessons</div></div>", unsafe_allow_html=True)
    st.markdown("### Course")

    # detect units (prefer local, otherwise drive)
    if not os.path.exists("prompts"):
        drive_units = list_drive_units_and_lessons()
        if drive_units:
            unit_options = [u.capitalize() for u in drive_units.keys()]
            unit_lessons = {u.capitalize(): len(v) for u, v in drive_units.items()}
        else:
            unit_options = ["Unit 1"]
            unit_lessons = {"Unit 1": 6}
    else:
        unit_options = sorted(
            [f"Unit {name.replace('unit', '').strip()}"
             for name in os.listdir("prompts")
             if name.lower().startswith("unit")],
            key=lambda x: int(x.split()[1])
        )
        unit_lessons = {}
        for unit_folder in os.listdir("prompts"):
            if not unit_folder.lower().startswith("unit"):
                continue
            lesson_count = len([
                name for name in os.listdir(os.path.join("prompts", unit_folder))
                if name.lower().startswith("lesson")
            ])
            unit_label = f"Unit {unit_folder.replace('unit', '').strip()}"
            unit_lessons[unit_label] = lesson_count

    current_unit = st.query_params.get("unit", "Unit 1")
    lesson_count = unit_lessons.get(current_unit, 6)
    lesson_items = [f"Lesson {i}" for i in range(1, lesson_count + 1)] + ["General Exercises"]

    default_unit = st.query_params.get("unit", "Unit 1")
    default_lesson = st.query_params.get("lesson", "Lesson 1")
    if default_unit not in unit_options:
        default_unit = "Unit 1"
    if default_lesson not in lesson_items:
        default_lesson = "Lesson 1"

    unit_choice = st.selectbox(
        "Choose Unit",
        unit_options,
        index=unit_options.index(st.session_state["selected_unit"]) if st.session_state["selected_unit"] in unit_options else 0,
        key="unit_select"
    )

    if unit_choice != st.session_state["selected_unit"]:
        st.session_state["selected_unit"] = unit_choice
        st.session_state["selected_lesson"] = "Lesson 1"
        st.session_state["selected_tab"] = "Explanation"
        st.query_params = {
            "unit": unit_choice,
            "lesson": "Lesson 1",
            "tab": "Explanation"
        }
        st.rerun()

    lesson_count = unit_lessons.get(st.session_state["selected_unit"], 6)
    lesson_items = [f"Lesson {i}" for i in range(1, lesson_count + 1)] + ["General Exercises"]

    lesson_choice = st.selectbox(
        "Choose Lesson",
        lesson_items,
        index=lesson_items.index(st.session_state["selected_lesson"]) if st.session_state["selected_lesson"] in lesson_items else 0,
        key="selected_lesson"
    )

    if lesson_choice != st.session_state["selected_lesson"]:
        st.session_state["go_to_lesson_change"] = {
            "unit": st.session_state["selected_unit"],
            "lesson": lesson_choice,
            "tab": "Explanation"
        }
        st.rerun()

# ---------------------------
#  MAIN HEADER
# ---------------------------
st.markdown(f"""
<div style='text-align:center; margin-bottom:12px;'>
  <div style='font-size:28px; font-weight:800; color:#0f172a;'>Learn Egyptian Dialect — AI Tutor</div>
  <div style='color:#475569; font-size:14px;'>Interactive explanation and real-time practice.</div>
</div>
""", unsafe_allow_html=True)

# ---------------------------
#  LESSON UTILITIES
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

def build_full_prompt(base_prompt: str, lesson_content: str) -> str:
    base = (base_prompt or "").strip()
    content = (lesson_content or "").strip()
    combined = f"{base}\n\n---\n📘 LESSON FILE START\n{content}\n📘 LESSON FILE END\n---"
    return combined

# ---------------------------
#  TABS: Explanation / Grammar / Practice
# ---------------------------
explain_key, practice_key = get_keys_for_lesson(lesson_choice)

def lesson_two_tabs(lesson_label):
    current_unit = st.query_params.get("unit", "Unit 1")
    system_prompt = "You are a professional Egyptian Arabic teacher for English speakers."

    previous_lesson = st.session_state.get("last_rendered_lesson")
    current_lesson_name = st.query_params.get("lesson", "Lesson 1")
    if previous_lesson and previous_lesson != current_lesson_name:
        st.session_state["selected_tab"] = "Explanation"
        st.query_params["tab"] = "Explanation"
    st.session_state["last_rendered_lesson"] = current_lesson_name

    unit_id = current_unit.lower().replace(" ", "")
    explain_history_key = f"{unit_id}_{lesson_label}_explain_history"
    practice_history_key = f"{unit_id}_{lesson_label}_practice_history"

    ensure_history(explain_history_key, system_prompt)
    ensure_history(practice_history_key, system_prompt)

    params = dict(st.query_params)
    current_tab = st.session_state.get("selected_tab", params.get("tab", "Explanation"))

    st.markdown("""
    <style>
    div[role='radiogroup'] input[type='radio'], div[role='radiogroup'] svg { display: none !important; }
    div[role='radiogroup'] { display: flex; justify-content: center; align-items: center; gap: 28px; margin-bottom: 16px; flex-wrap: nowrap; }
    div[role='radiogroup'] label { background: #f8fafc; border-radius: 12px; cursor: pointer; font-weight: 500; color: #334155; transition: all 0.25s ease; border: 1px solid transparent; box-shadow: 0 1px 3px rgba(0,0,0,0.04); display: flex; align-items: center; padding: 10px 22px; }
    div[role='radiogroup'] label:hover { background: #ecfdf5; }
    div[role='radiogroup'] input:checked + div { background: #d1fae5; border: 1px solid #10b981; color: #065f46 !important; font-weight: 600; box-shadow: 0 2px 6px rgba(16,185,129,0.12); }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"<div style='text-align:center; margin-bottom:12px;'><h3 style='font-size:20px; font-weight:700; color:#0f172a;'>🧠 {current_unit} — {current_lesson_name}</h3></div>", unsafe_allow_html=True)

    tab_options = ["📘 Explanation", "🧠 Grammar Note", "🧩 Practice Exercises"]
    if st.session_state.get("selected_tab") == "Grammar":
        default_tab = "🧠 Grammar Note"
    elif st.session_state.get("selected_tab") == "Practice":
        default_tab = "🧩 Practice Exercises"
    else:
        default_tab = "📘 Explanation"

    tab_choice = st.radio("Select section", tab_options, horizontal=True, label_visibility="collapsed", key="lesson_tab_choice", index=tab_options.index(default_tab))

    if "Explanation" in tab_choice:
        selected_tab = "Explanation"
    elif "Grammar" in tab_choice:
        selected_tab = "Grammar"
    else:
        selected_tab = "Practice"

    if selected_tab != current_tab:
        st.session_state["selected_tab"] = selected_tab
        st.query_params = {
            "unit": st.session_state.get("selected_unit", "Unit 1"),
            "lesson": st.session_state.get("selected_lesson", "Lesson 1"),
            "tab": selected_tab
        }
        st.rerun()

    # -------- EXPLANATION --------
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
                dialogue_content = prompts.get(f"{lesson_label} Dialogue ({current_unit})", "")
                base_explanation_prompt = prompts.get("Base Explanation Prompt", "")
                full_system_prompt = build_full_prompt(base_explanation_prompt, dialogue_content)
                st.session_state[explain_history_key] = [{"role": "system", "content": full_system_prompt}]
                assistant_text = get_model_response(st.session_state[explain_history_key], max_tokens=2500)
                st.session_state[explain_history_key].append({"role": "assistant", "content": assistant_text})
                st.rerun()
        with col2:
            user_input = st.chat_input("Ask about the lesson explanation...", key=f"explain_input_{lesson_label}")
            if user_input:
                append_and_get_chunks(explain_history_key, user_input)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # -------- GRAMMAR --------
    elif selected_tab == "Grammar":
        st.markdown("### 🧠 Grammar Note")
        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
        unit_id = st.query_params.get("unit", "Unit 1").lower().replace(" ", "")
        grammar_file = f"prompts/{unit_id}/{lesson_label.lower()}/{lesson_label.lower().replace(' ', '')}_grammar.txt"
        grammar_content = ""

        # حاول تقرأ من Drive أولًا
        if running_on_cloud():
            service = get_drive_service()
            unit_name = current_unit.lower().replace(" ", "")
            lesson_name = lesson_label.lower().replace(" ", "")
            grammar_file_name = f"{lesson_name}_grammar.txt"

            # 🔹 نجيب ID الوحدة
            unit_results = service.files().list(
                q=f"(name='{unit_name}' or name='{unit_name.capitalize()}') and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)",
            ).execute()
            unit_id = unit_results.get("files", [{}])[0].get("id")

            if unit_id:
                lesson_results = service.files().list(
                    q=f"(name='{lesson_label}' or name='{lesson_label.lower()}') and '{unit_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                    fields="files(id, name)",
                ).execute()
                lesson_id = lesson_results.get("files", [{}])[0].get("id")
                parent_id = lesson_id or unit_id
                grammar_content = read_file_from_drive(grammar_file_name, parent_id)

        # fallback المحلي
        if not grammar_content and os.path.exists(grammar_file):
            with open(grammar_file, "r", encoding="utf-8") as f:
                grammar_content = f.read().strip()

        if grammar_content:
            st.markdown(grammar_content)
        else:
            st.info("No grammar note for this lesson.")

        st.markdown("</div>", unsafe_allow_html=True)

    # -------- PRACTICE --------
    else:
        st.markdown("### 🧩 Practice Exercises")
        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
        base_practice_prompt = prompts.get("Base Practice Prompt", "")
        lesson_practice_content = prompts.get(f"{lesson_label} Practice ({current_unit})", "")
        if not base_practice_prompt.strip():
            st.info("Base practice prompt is missing or empty.")
        elif not lesson_practice_content.strip():
            st.info("No practice content found for this lesson.")
        else:
            for msg in st.session_state.get(practice_history_key, []):
                if msg["role"] == "system":
                    continue
                st.chat_message(msg["role"]).markdown(msg["content"])
            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button("Start Practice", key=f"start_practice_{lesson_label}"):
                    full_system_prompt = build_full_prompt(base_practice_prompt, lesson_practice_content)
                    st.session_state[practice_history_key] = [{"role": "system", "content": full_system_prompt}]
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
#  MAIN VIEW: General vs Lesson
# ---------------------------
if "general" in lesson_choice.lower():
    current_unit = st.query_params.get("unit", "Unit 1")
    current_lesson = "General Exercises"
    st.markdown(f"<div style='text-align:center; margin-bottom:12px;'><h3 style='font-size:20px; font-weight:700; color:#0f172a;'>🧠 {current_unit} — {current_lesson}</h3></div>", unsafe_allow_html=True)
    st.markdown("### 🗣️ General Exercises")
    st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
    general_key = "general_exercises_history"
    base_general_prompt_path = "prompts/base/practice_prompt.txt"
    current_unit_folder = st.query_params.get("unit", "Unit 1").lower().replace(" ", "")
    general_lesson_path = f"prompts/{current_unit_folder}/general_exercises/general_exercises.txt"
    base_general_prompt = ""
    general_lesson_content = ""
    if os.path.exists(base_general_prompt_path):
        with open(base_general_prompt_path, "r", encoding="utf-8") as f:
            base_general_prompt = f.read().strip()
    if os.path.exists(general_lesson_path):
        with open(general_lesson_path, "r", encoding="utf-8") as f:
            general_lesson_content = f.read().strip()
    full_general_prompt = (base_general_prompt + "\n\n" + general_lesson_content).strip()
    ensure_history(general_key, "You are an Egyptian Arabic tutor for general exercises.")
    for msg in st.session_state[general_key]:
        if msg["role"] == "system":
            continue
        st.chat_message(msg["role"]).markdown(msg["content"])
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Start Exercises", key="start_general_exercises"):
            st.session_state[general_key] = [{"role": "system", "content": full_general_prompt}]
            assistant_text = get_model_response(st.session_state[general_key], max_tokens=2000)
            st.session_state[general_key].append({"role": "assistant", "content": assistant_text})
            st.rerun()
    with col2:
        user_input = st.chat_input("Answer or ask for help...", key="general_input")
        if user_input:
            append_and_get_chunks(general_key, user_input)
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
else:
    lesson_two_tabs(lesson_choice)

# ---------------------------
#  NAVIGATION BUTTONS
# ---------------------------
current_unit = st.session_state["selected_unit"]
current_lesson = st.session_state["selected_lesson"]
lesson_count = unit_lessons.get(current_unit, 6) if 'unit_lessons' in locals() else 6
lesson_list = [f"Lesson {i}" for i in range(1, lesson_count + 1)] + ["General Exercises"]
current_index = lesson_list.index(current_lesson) if current_lesson in lesson_list else 0
col_prev, col_next = st.columns([1, 1])

def request_navigation(target_lesson):
    st.session_state["go_to_lesson"] = target_lesson
    st.rerun()

with col_prev:
    if current_index > 0:
        if st.button("⬅️ Previous Lesson"):
            request_navigation(lesson_list[current_index - 1])
with col_next:
    if current_index < len(lesson_list) - 1:
        if st.button("➡️ Next Lesson"):
            request_navigation(lesson_list[current_index + 1])

if "go_to_lesson" in st.session_state:
    target_lesson = st.session_state.pop("go_to_lesson")
    st.query_params = {
        "unit": st.session_state["selected_unit"],
        "lesson": target_lesson,
        "tab": st.session_state.get("selected_tab", "Explanation")
    }
    st.session_state["selected_lesson"] = target_lesson
    st.rerun()

# ---------------------------
#  FOOTER
# ---------------------------
st.markdown("---")
col1, col2 = st.columns([3, 1])
with col1:
    st.caption("Tip: Keep one base prompt and change dialogue/practice per lesson.")
with col2:
    total_chats = sum(1 for k in st.session_state if k.endswith("_history"))
    st.metric("Active Conversations", total_chats)
