# app.py
import streamlit as st
import os
import io
import ssl
import platform
import socket
import json
from typing import List
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from openai import OpenAI

# ---------------------------
#  ENVIRONMENT DETECTION
# ---------------------------

st.set_page_config(
    page_title="Egyptian Dialect AI Tutor",
    layout="centered",
    page_icon="🎓",
    initial_sidebar_state="expanded"
)

# ✅ Force Light Theme Globally
st.markdown("""
<style>
/* نوقف أي تأثير لوضع الداكن */
@media (prefers-color-scheme: dark) {
  html, body, [class*="main"], [class*="block-container"], [class*="stAppViewContainer"], [class*="stApp"] {
    background-color: #f7fbff !important;
    color: #111827 !important;
    color-scheme: light !important;
  }

  div, section, article, header, footer, span, p, label, input, textarea, button {
    background-color: #f7fbff !important;
    color: #111827 !important;
    border-color: #e2e8f0 !important;
    color-scheme: light !important;
  }

  /* نجبر كل النصوص تكون غامقة واضحة */
  * {
    -webkit-text-fill-color: #111827 !important;
    -webkit-text-stroke: 0 !important;
  }

  /* نحافظ على الخلفيات البيضاء للعناصر التفاعلية */
  .stButton>button, .stTextInput>div>div>input, .stChatInput input {
    background-color: white !important;
    color: #111827 !important;
  }

  /* التبويبات */
  div[role='radiogroup'] label {
    background-color: #f7fbff !important;
    color: #111827 !important;
  }

  /* الرسائل */
  [data-testid="stChatMessage"] {
    background-color: white !important;
    color: #111827 !important;
  }
}
</style>
""", unsafe_allow_html=True)


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
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    import httplib2, ssl

    creds = service_account.Credentials.from_service_account_info(st.secrets["google"])

    try:
        # ✅ المحاولة العادية أولًا
        import time
        for _ in range(3):
            try:
                service = build("drive", "v3", credentials=creds, cache_discovery=False)
                break
            except Exception:
                time.sleep(1.5)

        return service
    except ssl.SSLError:
        # ✅ لو حصل SSL Error، نعمل اتصال بدون تحقق SSL
        st.warning("⚠️ SSL issue detected — switching to unverified HTTPS mode...")
        http = creds.authorize(httplib2.Http(disable_ssl_certificate_validation=True))
        service = build("drive", "v3", http=http, cache_discovery=False)
        return service
    except Exception as e:
        st.error(f"⚠️ Could not connect to Google Drive API: {e}")
        return None


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
        try:
            unit_results = service.files().list(q=unit_query, fields="files(id, name)").execute()
            unit_folders = unit_results.get("files", [])
            unit_id = unit_folders[0]["id"] if unit_folders else None
        except Exception as e:
            print(f"⚠️ Google Drive error while fetching unit folder: {e}")
            unit_id = None

        lesson_id = None
        if unit_id:
            # 🔹 نجيب فولدر الدرس أو التمارين العامة
            lesson_query = (
                f"(name='{lesson}' or name='{lesson.lower()}' or name='{lesson.capitalize()}') "
                f"and '{unit_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
            )
            try:
                lesson_results = service.files().list(q=lesson_query, fields="files(id, name)").execute()
                lesson_folders = lesson_results.get("files", [])
                lesson_id = lesson_folders[0]["id"] if lesson_folders else None
            except Exception as e:
                print(f"⚠️ Google Drive error while fetching lesson folder: {e}")
                lesson_id = None

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
base_explanation_prompt = ""
base_practice_prompt = ""

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
# ---------------------------
#  CACHED PROMPTS SYSTEM
# ---------------------------
CACHE_FILE = "cached_prompts.json"

def save_prompts_to_cache(prompts_data: dict):
    """Save loaded prompts to a local JSON cache."""
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(prompts_data, f, ensure_ascii=False, indent=2)
        print("✅ Prompts saved to cache.")
    except Exception as e:
        print(f"⚠️ Failed to save cache: {e}")

def load_prompts_from_cache() -> dict:
    """Load prompts from local JSON cache if it exists."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            print("✅ Loaded prompts from cache.")
            return data
        except Exception as e:
            print(f"⚠️ Failed to read cache: {e}")
    return {}

# ---------------------------
#  LOAD PROMPTS (SMART SWITCH)
# ---------------------------
if os.path.exists(CACHE_FILE):
    prompts = load_prompts_from_cache()
else:
    prompts = load_all_units()
    save_prompts_to_cache(prompts)

if not base_explanation_prompt:
    base_explanation_prompt = load_prompt("base", "explanation", "prompt")
if not base_practice_prompt:
    base_practice_prompt = load_prompt("base", "practice", "prompt")

# ---------------------------
#  UI CONFIG
# ---------------------------
st.markdown("""
<style>
/* ✅ القواعد العامة للـ responsiveness */
@media (max-width: 768px) {
    .block-container {
        padding: 0.8rem 0.6rem !important;
    }

    .main {
        padding: 10px !important;
        border-radius: 10px;
    }

    .big-title {
        font-size: 22px !important;
    }

    .subtitle {
        font-size: 14px !important;
    }

    /* ✅ نخلي الأزرار تملى العرض */
    button[kind="primary"], button[kind="secondary"] {
        width: 100% !important;
    }

    /* ✅ نخلي التابات تتراص عموديًا */
    div[role='radiogroup'] {
        flex-direction: column !important;
        gap: 12px !important;
    }

    /* ✅ نخلي الزر العايم في النص تحت */
    .whatsapp-float {
        width: 90% !important;
        right: 5% !important;
        bottom: 10px !important;
        border-radius: 12px !important;
        font-size: 14px !important;
        padding: 10px !important;
    }
}
</style>
""", unsafe_allow_html=True)

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
            unit_lessons = {
                u.capitalize(): len([x for x in v if not x.lower().startswith("general")])
                for u, v in drive_units.items()
            }

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
        # ✅ نحذف كل المحادثات القديمة قبل الانتقال للدرس الجديد
        for key in list(st.session_state.keys()):
            if key.endswith("_history"):
                del st.session_state[key]

        st.session_state["go_to_lesson_change"] = {
            "unit": st.session_state["selected_unit"],
            "lesson": lesson_choice,
            "tab": "Explanation"
        }

        # نصفر كمان عداد المحادثات
        if "stop_training" in st.session_state:
            del st.session_state["stop_training"]

        st.rerun()


# ---------------------------
#  MAIN HEADER (IN FIXED LIGHT BOX)
# ---------------------------

from streamlit.components.v1 import html

html("""
<div style="
    background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
    border: 2px solid #e2e8f0;
    border-radius: 22px;
    padding: 20px 18px;
    margin: 36px auto 42px auto;
    box-shadow: 0 6px 18px rgba(0,0,0,0.06);
    text-align: center;
    max-width: 92%;
    width: 600px;
">
    <h2 style="
        font-size: clamp(22px, 5vw, 28px);
        font-weight: 800;
        color: #0f172a;
        margin-bottom: 10px;
        line-height: 1.2;
    ">
        Learn Egyptian Dialect — AI Tutor
    </h2>

    <p style="
        color: #475569;
        font-size: clamp(14px, 3.8vw, 16px);
        margin-bottom: 12px;
        line-height: 1.5;
    ">
        Interactive explanation and real-time practice.
    </p>

    <p style="
        font-size: clamp(13px, 3.5vw, 15px);
        color: #334155;
        margin-bottom: 18px;
        line-height: 1.4;
    ">
        Created by <b>Yassin Rashad</b> 🇪🇬 — for Arabic learners around the world 🌍
    </p>

    <a href="https://wa.me/201064958335?text=Hi%20Yassin!%20I'm%20interested%20in%20your%20Arabic%20lessons."
       target="_blank"
       style='
         display:inline-flex;
         align-items:center;
         justify-content:center;
         gap:8px;
         background-color:#25D366;
         color:white;
         padding:12px 28px;
         border-radius:50px;
         text-decoration:none;
         font-weight:700;
         font-size:clamp(14px, 4vw, 16px);
         border:2px solid #16a34a;
         box-shadow:0px 4px 10px rgba(0,0,0,0.15);
         transition:all 0.3s ease-in-out;
         white-space: nowrap;
     '
       onmouseover="this.style.backgroundColor='#1ebe5d'"
       onmouseout="this.style.backgroundColor='#25D366'">
       <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="white" viewBox="0 0 24 24">
         <path d="M12 .5C5.73.5.5 5.73.5 12c0 2.11.55 4.1 1.58 5.88L.5 23.5l5.78-1.56A11.37 11.37 0 0 0 12 23.5c6.27 0 11.5-5.23 11.5-11.5S18.27.5 12 .5Zm0 21c-1.72 0-3.41-.45-4.89-1.3l-.35-.2-3.43.93.93-3.35-.22-.36A9.57 9.57 0 0 1 2.5 12C2.5 6.76 6.76 2.5 12 2.5S21.5 6.76 21.5 12 17.24 21.5 12 21.5Zm5.08-6.33c-.28-.14-1.64-.81-1.89-.9-.25-.1-.43-.14-.62.14-.18.25-.71.89-.88 1.07-.16.18-.32.2-.6.07-.28-.14-1.18-.43-2.25-1.38-.83-.74-1.38-1.66-1.54-1.94-.16-.28-.02-.43.12-.57.12-.12.28-.32.42-.48.14-.16.18-.28.28-.46.1-.18.05-.34-.02-.48-.07-.14-.62-1.49-.85-2.05-.22-.53-.44-.46-.62-.46-.16 0-.34-.02-.52-.02s-.48.07-.73.34c-.25.27-.96.94-.96 2.29 0 1.34.98 2.63 1.12 2.81.14.18 1.93 2.95 4.66 4.13.65.28 1.16.45 1.56.58.65.21 1.24.18 1.7.11.52-.08 1.64-.67 1.87-1.31.23-.64.23-1.18.16-1.31-.06-.13-.25-.21-.52-.34Z"/>
       </svg>
       Contact via WhatsApp
    </a>
</div>
""", height=400, scrolling=False)

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
st.markdown("""
<style>
/* ✅ تنسيق التبويبات */
div[role='radiogroup'] {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 20px;
    flex-wrap: wrap;
}

/* الشكل الأساسي */
div[role='radiogroup'] label {
    background-color: #f7fbff !important; /* ✅ لون فاتح ثابت */
    color: #111827 !important;
    font-weight: 600 !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.06) !important;
    transition: all 0.25s ease-in-out !important;
    padding: 14px 26px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 8px !important;
    cursor: pointer;
    position: relative;
    white-space: nowrap !important;
    min-width: 220px;
}

/* 🔹 نص واضح دايمًا */
div[role='radiogroup'] label * {
    color: inherit !important;
}

/* ✅ نخفي أي عناصر داخلية عاملة إطار حوالين الكلام */
div[role='radiogroup'] label > div {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    padding: 0 !important;
    margin: 0 !important;
}

/* ✅ hover */
div[role='radiogroup'] label:hover {
    background-color: #eefcf4 !important;
    border-color: #10b981 !important;
    box-shadow: 0 4px 8px rgba(16,185,129,0.12) !important;
    transform: translateY(-2px);
}

/* ✅ الزر المحدد */
div[role='radiogroup'] label:has(input:checked) {
    background: linear-gradient(135deg, #a7f3d0, #6ee7b7) !important;
    border-color: #059669 !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 10px rgba(16,185,129,0.2) !important;
    transform: scale(1.02);
}

/* ✅ الرموز */
div[role='radiogroup'] label svg,
div[role='radiogroup'] label span {
    color: inherit !important;
    fill: inherit !important;
}

/* ✅ الوضع الداكن (نجبره يفضل فاتح حتى في الموبايل) */
@media (prefers-color-scheme: dark) {
    div[role='radiogroup'] label {
        background-color: #f7fbff !important;  /* ✅ نحافظ على الفاتح */
        color: #111827 !important;
        border-color: #e2e8f0 !important;
    }
    div[role='radiogroup'] label:hover {
        background-color: #eefcf4 !important;
        border-color: #10b981 !important;
    }
    div[role='radiogroup'] label:has(input:checked) {
        background: linear-gradient(135deg, #a7f3d0, #6ee7b7) !important;
        color: #ffffff !important;
    }
}

/* ✅ للموبايل */
@media (max-width: 768px) {
    div[role='radiogroup'] {
        flex-direction: column !important;
        gap: 12px !important;
    }

    div[role='radiogroup'] label {
        width: 100% !important;
        font-size: 16px !important;
        text-align: center !important;
        white-space: nowrap !important;
        background-color: #f7fbff !important; /* ✅ تأكيد اللون الفاتح للموبايل */
    }

    div[role='radiogroup'] label:active {
        transform: scale(0.98);
    }
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ✅ منع المتصفح من عكس الألوان داخل التبويبات المختارة */
div[role='radiogroup'] label:has(input:checked) * {
    color: #0f172a !important;              /* ✅ النص الغامق */
    -webkit-text-fill-color: #0f172a !important;  /* ✅ لمتصفحات الموبايل */
    mix-blend-mode: normal !important;      /* ✅ تعطيل دمج الألوان */
    text-shadow: none !important;           /* ✅ بدون تظليل */
    filter: brightness(1) contrast(1) !important;
}

/* ✅ نأكد إن أي نص داخل الزر المحدد ما يتحولش أبيض */
div[role='radiogroup'] label:has(input:checked) span,
div[role='radiogroup'] label:has(input:checked) svg {
    color: #0f172a !important;
    fill: #0f172a !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ✅ منع أي ظل أو تظليل تلقائي حوالين النصوص أو البوكسات */
html, body, [class*="main"], [class*="stAppViewContainer"], [class*="stApp"], section, div {
    background-color: #f7fbff !important;   /* ✅ نفس اللون العام */
    box-shadow: none !important;
    filter: none !important;
}

/* ✅ منع تأثير الخلفية الداكنة حوالين النصوص */
* {
    background: transparent !important;
    text-shadow: none !important;
    box-shadow: none !important;
}

/* ✅ نخلي الخلفية العامة تغطي كل الشاشة بالكامل */
body {
    background-color: #f7fbff !important;
    background-image: none !important;
    background-size: cover !important;
    background-attachment: fixed !important;
}

/* ✅ نخلي التطبيق دايمًا في الوضع الفاتح مهما حصل */
@media (prefers-color-scheme: dark) {
    html, body {
        background-color: #f7fbff !important;
        color: #111827 !important;
        color-scheme: light !important;
    }
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* ✅ حل مشكلة الخلفية البيضاء حوالين النص داخل الزر المحدد */
div[role='radiogroup'] label:has(input:checked) * {
    background-color: transparent !important; /* نخليها شفافة */
    box-shadow: none !important;              /* نشيل أي ظل */
}

/* ✅ نلغي الخلفية البيضاء اللي بتظهر ورا الإيموجي */
div[role='radiogroup'] label:has(input:checked) span {
    background: none !important;
    background-color: transparent !important;
}

/* ✅ نمنع المتصفح من عمل أي تأثير عكسي للألوان */
div[role='radiogroup'] label:has(input:checked) {
    isolation: isolate !important;
    mix-blend-mode: normal !important;
    overflow: hidden !important;
}
</style>
""", unsafe_allow_html=True)

explain_key, practice_key = get_keys_for_lesson(lesson_choice)

def lesson_two_tabs(lesson_label):
    from streamlit.components.v1 import html
    current_unit = st.query_params.get("unit", "Unit 1")
    system_prompt = "You are a professional Egyptian Arabic teacher for English speakers."
    # ✅ تهيئة التبويب الحالي من session_state أو localStorage عند أول تحميل
    st.markdown(f"""
    <div style="
        background-color: #ffffff;
        border: 2px solid #e2e8f0;
        border-radius: 16px;
        padding: 10px 16px;
        margin: 25px auto 22px auto;
        box-shadow: 0 3px 10px rgba(0,0,0,0.08);
        text-align: center;
        max-width: 500px;
    ">
        <h3 style="
            font-size: clamp(18px, 4.5vw, 22px);
            font-weight: 700;
            color: #0f172a;
            margin: 0;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        ">
            🧠 {current_unit} — {lesson_label}
        </h3>
    </div>
    """, unsafe_allow_html=True)

    tab_options = ["📘 Explanation", "🧠 Grammar Note", "🧩 Practice Exercises"]

    # ✅ استرجاع آخر تبويب محفوظ من localStorage
    html("""
    <script>
    const key = "yassin_tab_choice";
    const savedTab = window.localStorage.getItem(key);
    if (savedTab) {
        // نرسل القيمة لـ Streamlit
        window.parent.postMessage({
            type: "streamlit:setSessionState",
            key: "selected_tab",
            value: savedTab
        }, "*");
    } else {
        // لو مفيش قيمة محفوظة نخليها Explanation
        window.parent.postMessage({
            type: "streamlit:setSessionState",
            key: "selected_tab",
            value: "📘 Explanation"
        }, "*");
    }
    </script>
    """, height=0)

    # ✅ تحديد القيمة الحالية للتبويب
    current_tab = st.session_state.get("selected_tab", "📘 Explanation")

    # ✅ عرض التبويبات
    tab_choice = st.radio(
        "Select section",
        tab_options,
        horizontal=True,
        label_visibility="collapsed",
        index=tab_options.index(current_tab) if current_tab in tab_options else 0,
        key="tab_radio"
    )

    # ✅ حفظ التبويب في localStorage كل مرة المستخدم يبدله
    html(f"""
    <script>
    window.localStorage.setItem("yassin_tab_choice", "{tab_choice}");
    </script>
    """, height=0)

    # ✅ تحديث session_state (للتفاعل داخل نفس الجلسة)
    st.session_state["selected_tab"] = tab_choice

    # -------- EXPLANATION --------
    if st.session_state["selected_tab"] == "📘 Explanation":
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
    elif st.session_state["selected_tab"] == "🧠 Grammar Note":
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
#  FLOATING WHATSAPP BUTTON
# ---------------------------
st.markdown("""
<style>
.whatsapp-float {
    position: fixed;
    width: 220px;
    bottom: 20px;
    right: 20px;
    background-color: #25D366 !important;
    color: white !important;
    border-radius: 50px;
    text-align: center;
    font-weight: 700;
    font-size: 15px;
    padding: 12px 18px;
    border: 2px solid #16a34a;
    box-shadow: 0px 4px 8px rgba(0,0,0,0.2);
    z-index: 100;
    transition: all 0.3s ease-in-out;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
}
.whatsapp-float:hover {
    background-color: #1ebe5d !important;
    transform: scale(1.05);
}
.whatsapp-float a {
    color: white !important;
    text-decoration: none !important;
    display: flex;
    align-items: center;
    gap: 8px;
}
@media (max-width: 768px) {
    .whatsapp-float {
        width: 90% !important;
        right: 5% !important;
        bottom: 15px !important;
        font-size: 14px !important;
        padding: 10px 12px !important;
        border-radius: 12px !important;
    }
}
</style>

<div class="whatsapp-float">
  <a href="https://wa.me/201064958335?text=Hi%20Yassin!%20I'm%20interested%20in%20your%20Arabic%20lessons."
     target="_blank">
     <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" fill="white" viewBox="0 0 24 24">
       <path d="M12 .5C5.73.5.5 5.73.5 12c0 2.11.55 4.1 1.58 5.88L.5 23.5l5.78-1.56A11.37 11.37 0 0 0 12 23.5c6.27 0 11.5-5.23 11.5-11.5S18.27.5 12 .5Zm0 21c-1.72 0-3.41-.45-4.89-1.3l-.35-.2-3.43.93.93-3.35-.22-.36A9.57 9.57 0 0 1 2.5 12C2.5 6.76 6.76 2.5 12 2.5S21.5 6.76 21.5 12 17.24 21.5 12 21.5Zm5.08-6.33c-.28-.14-1.64-.81-1.89-.9-.25-.1-.43-.14-.62.14-.18.25-.71.89-.88 1.07-.16.18-.32.2-.6.07-.28-.14-1.18-.43-2.25-1.38-.83-.74-1.38-1.66-1.54-1.94-.16-.28-.02-.43.12-.57.12-.12.28-.32.42-.48.14-.16.18-.28.28-.46.1-.18.05-.34-.02-.48-.07-.14-.62-1.49-.85-2.05-.22-.53-.44-.46-.62-.46-.16 0-.34-.02-.52-.02s-.48.07-.73.34c-.25.27-.96.94-.96 2.29 0 1.34.98 2.63 1.12 2.81.14.18 1.93 2.95 4.66 4.13.65.28 1.16.45 1.56.58.65.21 1.24.18 1.7.11.52-.08 1.64-.67 1.87-1.31.23-.64.23-1.18.16-1.31-.06-.13-.25-.21-.52-.34Z"/>
     </svg>
     Contact for Private Lessons
  </a>
</div>
""", unsafe_allow_html=True)

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
