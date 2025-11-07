import streamlit as st
import os
from openai import OpenAI
from typing import List
import io, ssl, platform, socket
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# ✅ نكشف البيئة
def running_in_wsl():
    return bool(os.environ.get("WSL_DISTRO_NAME") or "microsoft" in platform.uname().release.lower())

def running_on_cloud():
    """
    Detect if the app is running on Streamlit Cloud or local.
    """
    home_path = os.getenv("HOME", "")
    hostname = socket.gethostname().lower()

    # Streamlit Cloud runs as appuser, not root or wsl
    if "streamlitapp" in hostname:
        return True
    if os.getenv("STREAMLIT_RUNTIME_ENV") == "cloud":
        return True
    if os.getenv("STREAMLIT_SERVER_HEADLESS") == "1":
        return True
    if home_path.startswith("/home/appuser"):
        return True

    return False

@st.cache_resource
def get_drive_service():
    """Create Google Drive service using credentials from Streamlit secrets."""
    creds = service_account.Credentials.from_service_account_info(st.secrets["google"])

    # ✳️ تجاوز مؤقت لـ SSL داخل WSL فقط
    if running_in_wsl() and not running_on_cloud():
        try:
            ssl._create_default_https_context = ssl._create_unverified_context
            print("✅ Running locally in WSL — using unverified SSL context.")
        except Exception:
            pass

    return build('drive', 'v3', credentials=creds)

@st.cache_resource
def list_drive_units_and_lessons():
    """List all units and lessons from Google Drive prompts folder, including general_exercises."""
    service = get_drive_service()
    PROMPTS_FOLDER_ID = "125CxvdIJDW63ATcbbpTTrt_BJC5fX961"

    units = {}
    try:
        # نجيب كل فولدرات الوحدات (unit1, unit2, ...)
        results = service.files().list(
            q=f"'{PROMPTS_FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)"
        ).execute()

        unit_folders = results.get("files", [])

        # ✅ فلترة وترتيب الوحدات بالأرقام
        unit_folders = sorted(
            [u for u in unit_folders if u["name"].lower().startswith("unit") or u["name"].lower() == "base"],
            key=lambda x: int(''.join(filter(str.isdigit, x["name"])) or 0)
        )

        for unit in unit_folders:
            unit_name = unit["name"]
            unit_id = unit["id"]

            # نجيب فولدرات الدروس داخل الوحدة
            lesson_results = service.files().list(
                q=f"'{unit_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
                fields="files(id, name)"
            ).execute()

            lesson_folders = lesson_results.get("files", [])

            # ✅ نضيف general_exercises لو موجود
            lesson_folders = sorted(
                [l for l in lesson_folders if l["name"].lower().startswith("lesson") or l["name"].lower() == "general_exercises"],
                key=lambda x: (0 if "general" in x["name"].lower() else int(''.join(filter(str.isdigit, x["name"])) or 0))
            )

            lessons = [l["name"] for l in lesson_folders]
            units[unit_name] = lessons

        if not units:
            st.warning("⚠️ No unit folders found in Google Drive 'prompts' directory.")

    except Exception as e:
        st.warning(f"⚠️ Couldn't list units/lessons from Drive: {e}")

    return units

@st.cache_resource
def read_file_from_drive(file_name):
    """Read text file from Google Drive (search deeply in all subfolders of prompts)."""
    service = get_drive_service()

    PROMPTS_FOLDER_ID = "125CxvdIJDW63ATcbbpTTrt_BJC5fX961"  # Folder: prompts

    try:
        # نبحث داخل كل الملفات النصية داخل مجلد prompts وأي فولدر تحته
        query = f"name='{file_name}' and trashed = false"
        page_token = None
        all_results = []

        while True:
            results = service.files().list(
                q=query,
                fields="nextPageToken, files(id, name, mimeType, parents)",
                pageToken=page_token
            ).execute()
            all_results.extend(results.get("files", []))
            page_token = results.get("nextPageToken", None)
            if page_token is None:
                break

    except Exception as e:
        st.warning(f"⚠️ Google Drive not reachable ({e}). Using local version.")
        return ""

    if not all_results:
        st.warning(f"⚠️ File '{file_name}' not found anywhere in Drive under prompts folder.")
        return ""

    # نطبع كل الملفات اللي بنفس الاسم علشان نعرف المسار
    st.write("🔍 Found matches for", file_name, ":", all_results)

    # نحاول نختار اللي جوه prompts فقط
    chosen_file = None
    for f in all_results:
        # لو الملف جواه فولدر prompts أو أحد فروعه
        parents = f.get("parents", [])
        if parents:
            chosen_file = f
            break
    if not chosen_file:
        chosen_file = all_results[0]

    file_id = chosen_file["id"]
    mime = chosen_file["mimeType"]

    try:
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
        st.success(f"✅ Loaded '{file_name}' from Drive.")
        return content

    except Exception as e:
        st.warning(f"⚠️ Couldn't download '{file_name}' from Drive ({e}). Using local version.")
        return ""
# ---------------------------
#  LOAD PROMPTS (smart switch)
# ---------------------------
def load_prompt(unit, lesson, type_=""):
    """
    Load prompt file according to folder structure.
    If running locally (WSL/PC), prefer local files.
    If running on Streamlit Cloud, load from Google Drive.
    """

    # تحديد المسار المحلي للملف
    if unit == "base":
        if type_:
            path = f"prompts/{unit}/{lesson}_{type_}.txt"
        else:
            path = f"prompts/{unit}/{lesson}.txt"
    else:
        file_name = lesson.replace(" ", "")
        if type_:
            path = f"prompts/{unit}/{lesson}/{file_name}_{type_}.txt"
        else:
            path = f"prompts/{unit}/{lesson}/{file_name}.txt"

    file_name = os.path.basename(path)

    # ✅ إذا كنا على الكلاود نحاول نقرأ من Drive أولاً
    if running_on_cloud():
        content = read_file_from_drive(file_name)
        if content.strip():
            return content
        else:
            st.warning(f"⚠️ Using local fallback for {file_name}")

    # ✅ محلي أو فشل Drive → نقرأ من الملفات المحلية
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        st.warning(f"⚠️ File '{file_name}' not found locally or on Drive.")
        return ""


# ---------------------------
#  BASE PROMPTS + LESSONS (new folder structure)
# ---------------------------
base_explanation_prompt = load_prompt("base", "explanation", "prompt")
base_practice_prompt = load_prompt("base", "practice", "prompt")

# ---------------------------
#  LOAD ALL UNITS DYNAMICALLY
# ---------------------------
def load_all_units():
    """
    Automatically load all units and lessons from the prompts/ folder.
    Each unit folder (e.g. unit1, unit2...) can contain lesson folders like 'lesson 1', 'lesson 2', etc.
    Supports automatic detection of number of lessons and files.
    """
    data = {}
    # ✅ لو مجلد prompts مش موجود محليًا (على الكلاود مثلًا)
    if not os.path.exists("prompts"):
        st.warning("⚠️ Local 'prompts' folder not found — loading from Google Drive only.")
        drive_units = list_drive_units_and_lessons()

        if drive_units:
            unit_options = [u.capitalize() for u in drive_units.keys()]
            unit_lessons = {u.capitalize(): len(v) for u, v in drive_units.items()}
        else:
            unit_options = ["Unit 1"]
            unit_lessons = {"Unit 1": 6}

        # ✅ تحميل البرومبتات الأساسية من Google Drive
        data["Base Explanation Prompt"] = load_prompt("base", "explanation", "prompt")
        data["Base Practice Prompt"] = load_prompt("base", "practice", "prompt")

        # ✅ تحميل تمارين عامة (General) للوحدة 1 مؤقتًا من Drive
        general = load_prompt("unit1", "general_exercises")
        data["General Dialogue (Unit 1)"] = general

        return data  # ✅ نرجع البيانات اللي اتحملت من Google Drive

        
    # أولاً نحمل البرومبتات الأساسية
    base_explanation_prompt = load_prompt("base", "explanation", "prompt")
    base_practice_prompt = load_prompt("base", "practice", "prompt")

    data["Base Explanation Prompt"] = base_explanation_prompt
    data["Base Practice Prompt"] = base_practice_prompt

    # 🧩 نقرأ كل فولدر يبدأ بـ unit في مجلد prompts
    for unit_name in sorted(os.listdir("prompts")):
        if not unit_name.lower().startswith("unit"):
            continue  # تجاهل أي فولدر مش وحدة

        unit_path = os.path.join("prompts", unit_name)
        unit_number = unit_name.replace("unit", "").strip().capitalize()

        # ✅ General Exercises
        general = load_prompt(unit_name, "general_exercises")
        data[f"General Dialogue (Unit {unit_number})"] = general

        # 🧠 نجيب كل الدروس تلقائيًا
        for lesson_folder in sorted(os.listdir(unit_path)):
            if not lesson_folder.lower().startswith("lesson"):
                continue

            lesson_label = lesson_folder.capitalize()  # مثل "Lesson 1"
            dialogue = load_prompt(unit_name, lesson_folder)
            practice = load_prompt(unit_name, lesson_folder, "practice")

            data[f"{lesson_label} Dialogue (Unit {unit_number})"] = dialogue
            data[f"{lesson_label} Practice (Unit {unit_number})"] = practice

    return data

# كل البرومبتات في dict واحدة
prompts = load_all_units()


# ---------------------------
#  CONFIG / STYLES
# ---------------------------
st.set_page_config(page_title="Egyptian Dialect AI Tutor", layout="centered", page_icon="🎓")
st.markdown(
    """
    <style>
    .main {
        background-color: #f7fbff;
        padding: 18px;
        border-radius: 14px;
        box-shadow: 0 6px 22px rgba(17,24,39,0.06);
    }
    .big-title {
        font-size:28px;
        font-weight:700;
        margin-bottom:6px;
    }
    .subtitle {
        color: #334155;
        margin-bottom: 14px;
    }
    .chat-box {
        border-radius: 12px;
        padding: 10px;
        background: white;
        box-shadow: 0 2px 8px rgba(15,23,42,0.04);
    }
    </style>
    """,
    unsafe_allow_html=True,
)
#سطور مؤقتة
# 🧪 DEBUG: show current environment (remove this block after testing)
mode = "☁️ Cloud Mode" if running_on_cloud() else "💻 Local Mode"
st.sidebar.info(f"Environment: {mode}")
st.sidebar.write("🧠 DEBUG INFO:")
st.sidebar.write("Hostname:", socket.gethostname())
st.sidebar.write("Runtime Env:", os.getenv("STREAMLIT_RUNTIME_ENV"))
st.sidebar.write("Headless:", os.getenv("STREAMLIT_SERVER_HEADLESS"))
st.sidebar.write("Home:", os.getenv("HOME"))

# 🧪 END DEBUG BLOCK

# ---------------------------
#  OPENAI CLIENT
# ---------------------------

api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

if not api_key:
    st.error("❌ OPENAI_API_KEY not found. Please set it as an environment variable.")
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
    """Call the model."""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=max_tokens
        )
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"API error: {e}")
        return "Sorry — an error occurred while contacting the model."

def ensure_history(key: str, system_prompt: str):
    """Ensure a conversation history exists for a lesson/tab with initial system prompt."""
    if key not in st.session_state:
        st.session_state[key] = [{"role": "system", "content": system_prompt}]

def append_and_get_chunks(history_key: str, user_content: str):
    """Handle chat continuation."""
    st.session_state[history_key].append({"role": "user", "content": user_content})
    messages = st.session_state[history_key]
    assistant_text = get_model_response(messages, max_tokens=600)

    # ✅ نتحقق هل الموديل أنهى الدرس
    if "### END_OF_LESSON" in assistant_text:
        st.session_state["stop_training"] = True

    st.session_state[history_key].append({"role": "assistant", "content": assistant_text})
    return safe_split_text(assistant_text)

# ---------------------------
#  INIT SESSION STATE
# ---------------------------

# نقرأ القيم الحالية من الرابط أو نستخدم الافتراضي
current_unit = st.query_params.get("unit", "Unit 1")
current_lesson = st.query_params.get("lesson", "Lesson 1")
current_tab = st.query_params.get("tab", "Explanation")

# نحافظ على القيم في session_state (علشان تفضل حتى بعد الريفريش)
st.session_state.setdefault("selected_unit", current_unit)
st.session_state.setdefault("selected_lesson", current_lesson)
st.session_state.setdefault("selected_tab", current_tab)

# كل مرة المستخدم يغيّر حاجة، نحدّث الرابط علشان نحافظ عليها بعد الريفريش
st.query_params["unit"] = st.session_state["selected_unit"]
st.query_params["lesson"] = st.session_state["selected_lesson"]
st.query_params["tab"] = st.session_state["selected_tab"]


# نخزنهم في session_state لو مش موجودين
if "selected_unit" not in st.session_state:
    st.session_state["selected_unit"] = current_unit
if "selected_lesson" not in st.session_state:
    st.session_state["selected_lesson"] = current_lesson

# كل مرة المستخدم يغيّر حاجة، نحدّث الرابط علشان نحافظ عليها بعد الريفريش
st.query_params["unit"] = st.session_state["selected_unit"]
st.query_params["lesson"] = st.session_state["selected_lesson"]

# ---------------------------
#  HANDLE NAVIGATION REQUEST (before sidebar)
# ---------------------------
if "go_to_lesson" in st.session_state:
    target_lesson = st.session_state.pop("go_to_lesson")
    st.query_params = {
        "unit": st.session_state["selected_unit"],
        "lesson": target_lesson,
        "tab": st.session_state.get("selected_tab", "Explanation")
    }
    st.rerun()
# ✅ لو المستخدم غيّر الدرس، نرجع تلقائيًا لتبويب الشرح قبل بناء الصفحة
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

    # ✅ استخدم query_params الجديدة
    params = dict(st.query_params)
    # 🧩 اكتشف الوحدات تلقائيًا من مجلد prompts أو استخدم قيم افتراضية لو مش موجود
    if not os.path.exists("prompts"):
        st.warning("⚠️ Local 'prompts' folder not found — loading from Google Drive only.")
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

        # 🧩 نكتشف عدد الدروس الحقيقي في كل وحدة
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

    # 🧮 الوحدة الحالية من الرابط أو الافتراضي
    current_unit = st.query_params.get("unit", "Unit 1")
    lesson_count = unit_lessons.get(current_unit, 6)
    lesson_items = [f"Lesson {i}" for i in range(1, lesson_count + 1)] + ["General Exercises"]

    default_unit = st.query_params.get("unit", "Unit 1")
    default_lesson = st.query_params.get("lesson", "Lesson 1")

    if default_unit not in unit_options:
        default_unit = "Unit 1"
    if default_lesson not in lesson_items:
        default_lesson = "Lesson 1"

    # ---------------------------
    #  UNIT & LESSON SELECTORS
    # ---------------------------

    # 🧮 نقرأ القيم من الرابط أو نستخدم الافتراضي
    current_unit = st.query_params.get("unit", "Unit 1")
    current_lesson = st.query_params.get("lesson", "Lesson 1")
    current_tab = st.query_params.get("tab", "Explanation")

    # نخزن القيم دي في session_state علشان نحافظ عليها بعد الريفريش
    st.session_state.setdefault("selected_unit", current_unit)
    st.session_state.setdefault("selected_lesson", current_lesson)
    st.session_state.setdefault("selected_tab", current_tab)

    # ---------------------------
    #  اختيار الوحدة
    # ---------------------------
    unit_choice = st.selectbox(
        "Choose Unit",
        unit_options,
        index=unit_options.index(st.session_state["selected_unit"])
        if st.session_state["selected_unit"] in unit_options else 0,
        key="unit_select"
    )

    # ✅ لو المستخدم غيّر الوحدة، نرجع لدرس 1 ونخلي التبويب الافتراضي "Explanation"
    if unit_choice != st.session_state["selected_unit"]:
        st.session_state["selected_unit"] = unit_choice
        st.session_state["selected_lesson"] = "Lesson 1"
        st.session_state["selected_tab"] = "Explanation"  # 👈 دي الإضافة الجديدة
        st.query_params = {
            "unit": unit_choice,
            "lesson": "Lesson 1",
            "tab": "Explanation"
        }
        st.rerun()


    # ---------------------------
    #  تحميل الدروس للوحدة الحالية
    # ---------------------------
    lesson_count = unit_lessons.get(st.session_state["selected_unit"], 6)
    lesson_items = [f"Lesson {i}" for i in range(1, lesson_count + 1)] + ["General Exercises"]

    # ---------------------------
    #  اختيار الدرس
    # ---------------------------
    lesson_choice = st.selectbox(
        "Choose Lesson",
        lesson_items,
        index=lesson_items.index(st.session_state["selected_lesson"])
        if st.session_state["selected_lesson"] in lesson_items else 0,
        key="selected_lesson"
    )

    # ✅ لو المستخدم غيّر الدرس نحفظ الطلب ونرجع فورًا
    if lesson_choice != st.session_state["selected_lesson"]:
        st.session_state["go_to_lesson_change"] = {
            "unit": st.session_state["selected_unit"],
            "lesson": lesson_choice,
            "tab": "Explanation"
        }
        st.rerun()


# ---------------------------
#  MAIN HEADER (MODERN STYLE)
# ---------------------------
st.markdown("""
<div class='main' style='text-align:center;'>
  <div class='big-title' style='font-size:32px; font-weight:800; color:#0f172a; margin-bottom:6px;'>
    Learn Egyptian Dialect — AI Tutor
  </div>
  <div class='subtitle' style='color:#475569; font-size:18px; margin-bottom:16px;'>
    Interactive explanation and real-time practice.
  </div>
  <div style='margin:0 auto; width:fit-content; padding:10px 16px; border-radius:14px; background-color:#f8fafc; display:flex; align-items:center; gap:10px; box-shadow:0 2px 6px rgba(15,23,42,0.08);'>
    <img src='https://upload.wikimedia.org/wikipedia/commons/6/6b/WhatsApp.svg' width='22' style='vertical-align:middle;'/>
    <span style='color:#334155; font-size:15px;'>
      Created by <b style='color:#0f766e;'>Yassin Rashad</b> — 
      <a href='https://wa.me/201064958335' target='_blank' style='color:#22c55e; text-decoration:none; font-weight:600;'>
        Contact via WhatsApp
      </a>
      for private lessons & practice.
    </span>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------
#  LESSON HANDLER
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

explain_key, practice_key = get_keys_for_lesson(lesson_choice)

def build_full_prompt(base_prompt: str, lesson_content: str) -> str:
    """
    Merge the base prompt and the lesson content into a single system prompt.
    Adds clear delimiters so the model sees them as one unit.
    """
    base = (base_prompt or "").strip()
    content = (lesson_content or "").strip()

    # If either part is empty, still return a safe combined string
    combined = f"{base}\n\n---\n📘 LESSON FILE START\n{content}\n📘 LESSON FILE END\n---"
    return combined

# ---------------------------
#  LESSON TWO TABS (works 100% with refresh)
# ---------------------------
def lesson_two_tabs(explain_key, lesson_key, lesson_label):
    current_unit = st.query_params.get("unit", "Unit 1")
    system_prompt = "You are a professional Egyptian Arabic teacher for English speakers."
        # ✅ لو المستخدم اختار درس جديد نرجع فورًا لتبويب الشرح
    previous_lesson = st.session_state.get("last_rendered_lesson")
    current_lesson_name = st.query_params.get("lesson", "Lesson 1")
    previous_tab = st.session_state.get("selected_tab")

    # ✅ لو المستخدم فعلاً غيّر الدرس (مش مجرد refresh)
    if previous_lesson and previous_lesson != current_lesson_name:
        st.session_state["selected_tab"] = "Explanation"
        st.query_params["tab"] = "Explanation"

    # ✅ حدّث آخر درس معروض بعد التأكد
    st.session_state["last_rendered_lesson"] = current_lesson_name


    unit_id = current_unit.lower().replace(" ", "")
    explain_history_key = f"{unit_id}_{lesson_label}_explain_history"
    practice_history_key = f"{unit_id}_{lesson_label}_practice_history"

    ensure_history(explain_history_key, system_prompt)
    ensure_history(practice_history_key, system_prompt)

    # ✅ نقرأ التاب الحالي من الرابط أو نبدأ بـ Explanation
    params = dict(st.query_params)
    # ✅ التبويب الحالي — يقرأ من session_state أولاً ثم من الرابط
    current_tab = st.session_state.get("selected_tab", params.get("tab", "Explanation"))

    # ✅ نعرض تبويبات قابلة للحفظ
    # ✅ تنسيق شكل التبويبات (radio)
# ✅ تصميم تبويبات حديث بدون دوائر
    # ✅ تصميم تبويبات بلون محايد (بدون أخضر)
# ✅ تصميم تبويبات بلون محايد (بدون أخضر)
# ✅ تصميم تبويبات بلون أخضر أنيق مع مسافات مضبوطة
# ✅ تبويبات بلون أخضر أنيق ومتوازن (Padding مضبوط)
# ✅ تبويبات بلون أخضر أنيق ومتوازن (Padding مضبوط)
# ✅ تبويبات بلون أخضر أنيق ومسافات مظبوطة تمامًا
# ✅ تبويبات متوازنة ومظبوطة تمامًا من كل الجوانب
# ✅ تبويبات بدون علامة الراديو — تصميم أنيق وحديث
    st.markdown("""
        <style>
        /* إخفاء عناصر الراديو */
        div[role='radiogroup'] input[type='radio'],
        div[role='radiogroup'] svg {
            display: none !important;
        }

        /* ترتيب التبويبات في صف واحد */
        div[role='radiogroup'] {
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 32px;
            margin-bottom: 20px;
            flex-wrap: nowrap;
        }

        /* الشكل العام للتبويب */
        div[role='radiogroup'] label {
            background: #f8fafc;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 500;
            color: #334155;
            transition: all 0.25s ease;
            border: 1px solid transparent;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            display: flex;
            align-items: center;
            padding: 10px 26px;
        }

        /* عند المرور */
        div[role='radiogroup'] label:hover {
            background: #ecfdf5;
        }

        /* التبويب النشط */
        div[role='radiogroup'] input:checked + div {
            background: #d1fae5;
            border: 1px solid #10b981;
            color: #065f46 !important;
            font-weight: 600;
            box-shadow: 0 2px 6px rgba(16,185,129,0.15);
        }

        /* النص داخل التبويب */
        div[role='radiogroup'] label > div:last-child {
            padding: 0;
        }
        </style>
    """, unsafe_allow_html=True)

    # نجيب الوحدة الحالية من الرابط
    current_unit = st.query_params.get("unit", "Unit 1")
    current_lesson = st.query_params.get("lesson", "Lesson 1")

    # نعرض العنوان فوق التبويبات
    st.markdown(f"""
    <div style='text-align:center; margin-bottom:16px;'>
    <h3 style='font-size:22px; font-weight:700; color:#0f172a;'>
        🧠 {current_unit} — {current_lesson}
    </h3>
    </div>
    """, unsafe_allow_html=True)

    tab_options = ["📘 Explanation", "🧠 Grammar Note", "🧩 Practice Exercises"]

    # ✅ نحدد التبويب الحالي بشكل واضح
    if st.session_state.get("selected_tab") == "Grammar":
        default_tab = "🧠 Grammar Note"
    elif st.session_state.get("selected_tab") == "Practice":
        default_tab = "🧩 Practice Exercises"
    else:
        default_tab = "📘 Explanation"

    # ✅ نعرض التبويبات مع تحديد القيمة الحالية يدويًا
    tab_choice = st.radio(
        "Select section",
        tab_options,
        horizontal=True,
        label_visibility="collapsed",
        key="lesson_tab_choice",
        index=tab_options.index(default_tab)
    )


    # ✅ نحدث الرابط لو المستخدم بدّل
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


    # -------- TAB 1 (EXPLANATION) --------
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
                with st.spinner("Generating explanation..."):
                    dialogue_content = prompts.get(f"{lesson_label} Dialogue ({current_unit})", "")
                    base_explanation_prompt = prompts.get("Base Explanation Prompt", "")

                    # دمج البرومبت الأساسي + محتوى الحوار في system واحد
                    full_system_prompt = build_full_prompt(base_explanation_prompt, dialogue_content)
                    st.session_state[explain_history_key] = [
                        {"role": "system", "content": full_system_prompt}
                    ]

                    # أول رد من الموديل مباشرة بعد قراءة الملفات
                    assistant_text = get_model_response(st.session_state[explain_history_key], max_tokens=2500)
                    st.session_state[explain_history_key].append({"role": "assistant", "content": assistant_text})
                    st.rerun()

        with col2:
            user_input = st.chat_input("Ask about the lesson explanation...", key=f"explain_input_{lesson_label}")
            if user_input:
                append_and_get_chunks(explain_history_key, user_input)
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # -------- TAB 2 (GRAMMAR NOTE) --------
    elif selected_tab == "Grammar":
        st.markdown("### 🧠 Grammar Note")
        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)

        grammar_file = f"prompts/{unit_id}/{lesson_label.lower()}/{lesson_label.lower().replace(' ', '')}_grammar.txt"
        if os.path.exists(grammar_file):
            with open(grammar_file, "r", encoding="utf-8") as f:
                grammar_content = f.read().strip()
                st.markdown(grammar_content)
        else:
            st.warning("⚠️ No grammar note found for this lesson.")

        st.markdown("</div>", unsafe_allow_html=True)

    # -------- TAB 3 (PRACTICE) --------
    else:
        st.markdown("### 🧩 Practice Exercises")
        st.markdown("<div class='chat-box'>", unsafe_allow_html=True)
        base_practice_prompt = prompts.get("Base Practice Prompt", "")
        lesson_practice_content = prompts.get(f"{lesson_label} Practice ({current_unit})", "")

        if not base_practice_prompt.strip():
            st.warning("⚠️ The base practice prompt file (prompts/base/practice_prompt.txt) is missing or empty.")
        elif not lesson_practice_content.strip():
            st.warning("⚠️ No practice content found for this lesson (e.g. prompts/unit1/lesson1_practice.txt).")
        else:
            for msg in st.session_state.get(practice_history_key, []):
                if msg["role"] == "system":
                    continue
                st.chat_message(msg["role"]).markdown(msg["content"])

            col1, col2 = st.columns([1, 2])
            with col1:
                if st.button("Start Practice", key=f"start_practice_{lesson_label}"):
                    with st.spinner("Preparing interactive exercises..."):
                        # دمج البرومبت الأساسي مع محتوى الدرس في system واحد
                        full_system_prompt = build_full_prompt(base_practice_prompt, lesson_practice_content)
                        st.session_state[practice_history_key] = [
                            {"role": "system", "content": full_system_prompt}
                        ]

                        # أول استدعاء علشان يبدأ الموديل الحوار بناءً على التعليمات
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
#  MAIN
# ---------------------------
if "general" in lesson_choice.lower():
    # 🧠 نعرض اسم الوحدة والدرس فوق التمارين العامة
    current_unit = st.query_params.get("unit", "Unit 1")
    current_lesson = st.query_params.get("lesson", "General Exercises")

    st.markdown(f"""
    <div style='text-align:center; margin-bottom:16px;'>
    <h3 style='font-size:22px; font-weight:700; color:#0f172a;'>
        🧠 {current_unit} — {current_lesson}
    </h3>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("### 🗣️ General Exercises")
    st.markdown("<div class='chat-box'>", unsafe_allow_html=True)

    general_key = "general_exercises_history"

    # مسارات الملفات
    base_general_prompt_path = "prompts/base/practice_prompt.txt"
    current_unit_folder = st.query_params.get("unit", "Unit 1").lower().replace(" ", "")
    general_lesson_path = f"prompts/{current_unit_folder}/general_exercises/general_exercises.txt"

    # نقرأ البرومبت الأساسي من base
    if os.path.exists(base_general_prompt_path):
        with open(base_general_prompt_path, "r", encoding="utf-8") as f:
            base_general_prompt = f.read().strip()
    else:
        st.error("⚠️ Base general exercises prompt file not found.")
        base_general_prompt = ""

    # نقرأ المحتوى الخاص بالـ general
    if os.path.exists(general_lesson_path):
        with open(general_lesson_path, "r", encoding="utf-8") as f:
            general_lesson_content = f.read().strip()
    else:
        st.error("⚠️ General exercises content file not found.")
        general_lesson_content = ""

    # دمج البرومبتين في system واحد
    full_general_prompt = (
        base_general_prompt + "\n\n" + general_lesson_content
    ).strip()

    ensure_history(general_key, "You are an Egyptian Arabic tutor for general exercises.")

    # عرض المحادثة القديمة (لو فيه)
    for msg in st.session_state[general_key]:
        if msg["role"] == "system":
            continue
        st.chat_message(msg["role"]).markdown(msg["content"])

    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("Start Exercises", key="start_general_exercises"):
            with st.spinner("Starting general exercises..."):
                st.session_state[general_key] = [
                    {"role": "system", "content": full_general_prompt}
                ]
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
    lesson_two_tabs(explain_key, practice_key, lesson_choice)

# ---------------------------
#  NAVIGATION BUTTONS (FINAL WORKING VERSION)
# ---------------------------

current_unit = st.session_state["selected_unit"]
current_lesson = st.session_state["selected_lesson"]

# 🧩 عدد الدروس في الوحدة الحالية
lesson_count = unit_lessons.get(current_unit, 6)
lesson_list = [f"Lesson {i}" for i in range(1, lesson_count + 1)] + ["General Exercises"]

if current_lesson in lesson_list:
    current_index = lesson_list.index(current_lesson)
else:
    current_index = 0

col_prev, col_next = st.columns([1, 1])

# ✅ الوظيفة بتخزن الطلب مؤقتًا (بدل ما تحدث الـ query_params مباشرة)
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

# ✅ معالجة التنقل قبل بناء الـ sidebar
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
    st.caption("Tip: You can now keep one base prompt and just change dialogue or practice files per lesson!")
with col2:
    total_chats = sum(1 for k in st.session_state if k.endswith("_history"))
    st.metric("Active Conversations", total_chats)