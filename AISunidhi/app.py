import base64
import hmac
import io
import json
import os
import time
import uuid
from datetime import date
from pathlib import Path

import requests
import streamlit as st
from google import genai
from google.genai import types
from PIL import Image, ImageOps
from pypdf import PdfReader

# ============================================================
# 1. PATHS + PAGE CONFIG
# ============================================================

BASE_DIR = Path(__file__).parent
IMAGE_PATH = BASE_DIR / "profile.jpg"
PDF_PATH = BASE_DIR / "Sunidhi_Portfolio.pdf"
DATA_FILE = BASE_DIR / "data" / "projects.json"
PROJECT_IMG_DIR = BASE_DIR / "assets" / "projects"

st.set_page_config(page_title="Sunidhi AI", page_icon="✨", layout="wide")


def get_secret(name, default=None):
    try:
        return st.secrets[name]
    except Exception:
        return os.environ.get(name, default)


# ============================================================
# 2. STYLING
# ============================================================

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

html, body, .stApp, [class*="css"] { font-family: 'Manrope', 'Segoe UI', sans-serif; }
.stApp { background: #FFFFFF; }
#MainMenu, footer { visibility: hidden; }

[data-testid="stSidebar"] { background: #F8FAFC; border-right: 1px solid #E2E8F0; }
[data-testid="stSidebar"] img {
    border-radius: 50%; width: 150px; height: 150px; object-fit: cover;
    margin: 0 auto; display: block; border: 3px solid #fff;
    box-shadow: 0 0 0 2px #4F46E5;
}
.side-name { text-align: center; font-size: 1.35rem; font-weight: 800; margin: 14px 0 0 0; }
.side-role { text-align: center; font-size: .9rem; color: #475569; margin: 2px 0 10px 0; }
.side-links { text-align: center; margin-bottom: 8px; }
.side-links a { color: #4F46E5 !important; font-weight: 600; text-decoration: none; margin: 0 8px; }
.side-links a:hover { text-decoration: underline; }

.hero-title { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; line-height: 1.1; margin: 0; }
.hero-sub { color: #475569; font-size: 1.05rem; margin: 10px 0 22px 0; max-width: 60ch; }

.stChatMessage { background: transparent; border: none; box-shadow: none; }
.stChatMessage:has([data-testid="stChatMessageAvatarUser"]) {
    background: #EEF2FF; border-radius: 18px; padding: 10px 18px; width: fit-content;
    max-width: 80%; margin-left: auto;
}
[data-testid="stChatInput"] { border-radius: 24px; border: 1px solid #CBD5E1; }
[data-testid="stChatInput"]:focus-within { border-color: #4F46E5; }

.stButton > button {
    border-radius: 999px; border: 1px solid #CBD5E1; background: #fff;
    font-weight: 600; padding: .35rem 1rem;
}
.stButton > button:hover { border-color: #4F46E5; color: #4F46E5; }

[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; }
.proj-title { font-size: 1.2rem; font-weight: 700; margin: 8px 0 2px 0; }
.proj-date { font-size: .8rem; color: #64748B; margin-bottom: 6px; }
</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# 3. GEMINI SETUP (same GEMINI_API_KEY secret as before)
# ============================================================

API_KEY = str(get_secret("GEMINI_API_KEY", "")).strip()
if not API_KEY:
    st.error("GEMINI_API_KEY is missing. Add it under Settings → Secrets (or .streamlit/secrets.toml).")
    st.stop()


@st.cache_resource
def get_client(key):
    return genai.Client(api_key=key)


client = get_client(API_KEY)

# Tried in order. If a model is retired or renamed, the next one is used automatically.
# Set GEMINI_MODEL in Secrets to put your own choice first.
_custom_model = get_secret("GEMINI_MODEL")
MODELS = ([_custom_model] if _custom_model else []) + [
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
]


def is_key_error(e):
    t = str(e).lower()
    return any(s in t for s in ("api key", "api_key_invalid", "permission_denied", "403", "leaked"))


def explain_error(e):
    t = str(e).lower()
    if is_key_error(e):
        return (
            "Google rejected the API key. It may have been disabled (this happens when a key is "
            "exposed publicly) or restricted. Create a new key in Google AI Studio and paste it "
            "as GEMINI_API_KEY in Secrets."
        )
    if "429" in t or "resource_exhausted" in t or "quota" in t:
        return "The Gemini quota is used up for now. Wait a minute and try again, or enable billing in Google AI Studio."
    if "503" in t or "unavailable" in t or "overloaded" in t:
        return "Gemini is busy right now. Try again in a moment."
    if "404" in t or "not found" in t:
        return "None of the configured Gemini models were found. Set GEMINI_MODEL in Secrets to a current model name."
    return f"Something went wrong: {e}"


# ============================================================
# 4. PORTFOLIO PDF
# ============================================================

@st.cache_data
def extract_portfolio_data():
    if not PDF_PATH.exists():
        return "Portfolio document not found. Ensure Sunidhi_Portfolio.pdf is in the repo."
    try:
        reader = PdfReader(str(PDF_PATH))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as e:
        return f"Error reading PDF: {e}"


portfolio_data = extract_portfolio_data()


# ============================================================
# 5. PROJECT STORAGE
# ============================================================

def load_projects():
    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_projects_local(projects):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")


def github_enabled():
    token = str(get_secret("GITHUB_TOKEN", "")).strip()
    repo = str(get_secret("GITHUB_REPO", "")).strip()
    if not token or not repo:
        return False
    # Ignore example values that were never replaced
    if "your-username" in repo or "your-repo" in repo or token.endswith("..."):
        return False
    return True


def _check_github(resp):
    if resp.ok:
        return
    repo = get_secret("GITHUB_REPO")
    if resp.status_code == 401:
        raise RuntimeError(
            "GitHub rejected the token (401). Create a new fine-grained token and paste the full "
            "value into GITHUB_TOKEN in Secrets. It may be wrong, expired, or revoked."
        )
    if resp.status_code in (403, 404):
        raise RuntimeError(
            f"GitHub can't access '{repo}' ({resp.status_code}). Check that GITHUB_REPO is exactly "
            "'username/repo-name', and that the token has access to that repo with "
            "Contents: Read and write."
        )
    if resp.status_code == 422:
        raise RuntimeError("GitHub rejected the request (422). Check that GITHUB_BRANCH matches your branch name.")
    resp.raise_for_status()


def github_commit(repo_path, content, message):
    """Create/update a file in the GitHub repo. content=None deletes it."""
    repo = str(get_secret("GITHUB_REPO")).strip()
    branch = str(get_secret("GITHUB_BRANCH", "main")).strip()
    headers = {
        "Authorization": f"Bearer {str(get_secret('GITHUB_TOKEN')).strip()}",
        "Accept": "application/vnd.github+json",
    }
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    r = requests.get(url, headers=headers, params={"ref": branch}, timeout=20)
    if r.status_code not in (200, 404):
        _check_github(r)
    sha = r.json().get("sha") if r.status_code == 200 else None

    if content is None:
        if sha:
            _check_github(requests.delete(
                url, headers=headers, timeout=20,
                json={"message": message, "sha": sha, "branch": branch},
            ))
        return

    payload = {"message": message, "content": base64.b64encode(content).decode(), "branch": branch}
    if sha:
        payload["sha"] = sha
    _check_github(requests.put(url, headers=headers, json=payload, timeout=30))


def process_image(uploaded_file):
    img = ImageOps.exif_transpose(Image.open(uploaded_file)).convert("RGB")
    img.thumbnail((1600, 1600))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85, optimize=True)
    return buf.getvalue()


def projects_bytes(projects):
    return json.dumps(projects, indent=2, ensure_ascii=False).encode()


def add_project(title, description, files):
    projects = load_projects()
    pid = uuid.uuid4().hex[:8]
    PROJECT_IMG_DIR.mkdir(parents=True, exist_ok=True)

    images = []
    for i, f in enumerate(files):
        data = process_image(f)
        rel = f"assets/projects/{pid}_{i}.jpg"
        (BASE_DIR / rel).write_bytes(data)
        if github_enabled():
            github_commit(rel, data, f"Add image for project: {title}")
        images.append(rel)

    projects.insert(
        0,
        {
            "id": pid,
            "title": title,
            "description": description,
            "images": images,
            "date": date.today().strftime("%b %Y"),
        },
    )
    save_projects_local(projects)
    if github_enabled():
        github_commit("data/projects.json", projects_bytes(projects), f"Add project: {title}")


def delete_project(pid):
    projects = load_projects()
    target = next((p for p in projects if p["id"] == pid), None)
    if not target:
        return
    for rel in target.get("images", []):
        (BASE_DIR / rel).unlink(missing_ok=True)
        if github_enabled():
            github_commit(rel, None, f"Remove image for project: {target['title']}")
    projects = [p for p in projects if p["id"] != pid]
    save_projects_local(projects)
    if github_enabled():
        github_commit("data/projects.json", projects_bytes(projects), f"Remove project: {target['title']}")


# ============================================================
# 6. SIDEBAR
# ============================================================

with st.sidebar:
    if IMAGE_PATH.exists():
        st.image(str(IMAGE_PATH))
    st.markdown('<p class="side-name">Sunidhi Rusia</p>', unsafe_allow_html=True)
    st.markdown('<p class="side-role">AI Architect & Data Engineer</p>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="side-links">
            <a href="https://www.linkedin.com/in/sunidhi-rusia" target="_blank">LinkedIn</a>
            <a href="mailto:sunidhirusia22@gmail.com">Email</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()
    st.markdown("**About**")
    st.write(
        "M.S. in Business Analytics & AI at Stevens Institute of Technology. "
        "Specializing in ML, supply chain analytics, and enterprise AI orchestration."
    )
    st.markdown("**Skills**")
    st.write("**AI/ML:** Llama-3.3-70B, Azure OpenAI, Claude API, Prompt Engineering, NLP")
    st.write("**Data:** Python, SQL, Pandas, XGBoost, AWS S3, Supabase")
    with st.expander("Featured projects"):
        st.markdown("- **Athenica Generative AI:** Enterprise Llama-3 deployment.")
        st.markdown("- **StartupHub:** Full-stack talent platform via Claude API.")
        st.markdown("- **Agentic Coach:** Microsoft Copilot Studio system.")


# ============================================================
# 7. HEADER + NAVIGATION
# ============================================================

st.markdown('<h1 class="hero-title">Hi, I\'m Sunidhi AI</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="hero-sub">Ask about my experience, skills, and coursework, '
    "or browse the projects I've built.</p>",
    unsafe_allow_html=True,
)

page = st.radio("Section", ["Chat", "Projects", "Manage"], horizontal=True, label_visibility="collapsed")


# ============================================================
# 8. CHAT PAGE
# ============================================================

GREETING = (
    "I'm trained on Sunidhi's portfolio, skills, projects, and coursework. "
    "What would you like to know?"
)
SUGGESTIONS = [
    "What projects has Sunidhi built?",
    "Summarize her technical skills",
    "What is her education?",
]


def build_system_prompt():
    projects = load_projects()
    project_text = "\n".join(
        f"- {p['title']} ({p.get('date', '')}): {p['description']}" for p in projects
    ) or "No additional projects have been added yet."

    return f"""You are Sunidhi AI, the interactive professional portfolio assistant for Sunidhi Rusia.

Your source of truth is the portfolio data below.

<portfolio_database>
{portfolio_data}
</portfolio_database>

<additional_projects>
{project_text}
</additional_projects>

Rules:
1. Answer ONLY from the information above. Never invent experience, education, skills, projects, companies, titles, achievements, dates, or technologies.
2. Be concise, professional, and helpful. Use Markdown (short paragraphs, bullets, bold) when it helps.
3. If asked for contact details, give: Email: sunidhirusia22@gmail.com, LinkedIn: https://www.linkedin.com/in/sunidhi-rusia
4. If something isn't covered, say your knowledge is limited to Sunidhi's professional portfolio.
5. You are a portfolio assistant, not a general-purpose assistant.
"""


def stream_reply(history):
    """Stateless call: sends the full history each time, so nothing can go stale between reruns.
    Retries once on busy errors and falls back to the next model if one is unavailable."""
    contents = [
        types.Content(
            role="user" if m["role"] == "user" else "model",
            parts=[types.Part(text=m["content"])],
        )
        for m in history
    ]
    config = types.GenerateContentConfig(system_instruction=build_system_prompt(), temperature=0.4)

    last_error = None
    for model in MODELS:
        for attempt in range(2):
            started = False
            try:
                for chunk in client.models.generate_content_stream(
                    model=model, contents=contents, config=config
                ):
                    if chunk.text:
                        started = True
                        yield chunk.text
                return
            except Exception as e:
                last_error = e
                if started or is_key_error(e):
                    raise
                if attempt == 0 and any(s in str(e).lower() for s in ("503", "unavailable", "overloaded")):
                    time.sleep(2)
                    continue
                break  # try the next model
    raise last_error


def render_chat():
    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.chat_message("assistant", avatar="✨"):
        st.markdown(GREETING)

    for m in st.session_state.messages:
        with st.chat_message(m["role"], avatar="✨" if m["role"] == "assistant" else None):
            st.markdown(m["content"])

    if not st.session_state.messages:
        cols = st.columns(len(SUGGESTIONS))
        for col, q in zip(cols, SUGGESTIONS):
            if col.button(q, use_container_width=True):
                st.session_state.pending_prompt = q
                st.rerun()

    prompt = st.chat_input("Ask about Sunidhi...") or st.session_state.pop("pending_prompt", None)
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    api_messages = st.session_state.messages[-20:]
    while api_messages and api_messages[0]["role"] != "user":
        api_messages = api_messages[1:]

    with st.chat_message("assistant", avatar="✨"):
        try:
            answer = st.write_stream(stream_reply(api_messages))
            st.session_state.messages.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.session_state.messages.pop()
            st.error(explain_error(e))


# ============================================================
# 9. PROJECTS PAGE
# ============================================================

def render_projects():
    projects = load_projects()
    if not projects:
        st.info("No projects yet. Open **Manage** to add your first one.")
        return

    cols = st.columns(2, gap="large")
    for i, p in enumerate(projects):
        with cols[i % 2]:
            with st.container(border=True):
                imgs = [str(BASE_DIR / r) for r in p.get("images", []) if (BASE_DIR / r).exists()]
                if imgs:
                    st.image(imgs[0])
                st.markdown(f'<div class="proj-title">{p["title"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="proj-date">{p.get("date", "")}</div>', unsafe_allow_html=True)
                st.write(p["description"])
                if len(imgs) > 1:
                    with st.expander(f"More photos ({len(imgs) - 1})"):
                        st.image(imgs[1:], width=240)


# ============================================================
# 10. MANAGE PAGE (password protected)
# ============================================================

def render_manage():
    admin_password = get_secret("ADMIN_PASSWORD")
    if not admin_password:
        st.warning("Add ADMIN_PASSWORD to Secrets to enable this section.")
        return

    if not st.session_state.get("admin_ok"):
        pw = st.text_input("Password", type="password")
        if pw and hmac.compare_digest(str(pw), str(admin_password)):
            st.session_state.admin_ok = True
            st.rerun()
        elif pw:
            st.error("Incorrect password.")
        return

    if github_enabled():
        st.caption("Saved projects are committed to GitHub. The live site restarts and shows them in about a minute.")
    else:
        st.warning(
            "GitHub saving is not set up, so projects added here disappear when the app restarts. "
            "Add GITHUB_TOKEN and GITHUB_REPO to Secrets to keep them."
        )

    st.subheader("Add a project")
    with st.form("add_project", clear_on_submit=True):
        title = st.text_input("Title")
        description = st.text_area("What did you build, and what was the result?", height=140)
        files = st.file_uploader("Pictures", type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
        submitted = st.form_submit_button("Save project", type="primary")

    if submitted:
        if not title.strip() or not description.strip():
            st.error("Add a title and a description.")
        else:
            with st.spinner("Saving..."):
                try:
                    add_project(title.strip(), description.strip(), files or [])
                    st.toast("Project saved")
                    st.rerun()
                except Exception as e:
                    st.error(f"Couldn't save the project: {e}")

    projects = load_projects()
    if projects:
        st.subheader("Your projects")
        for p in projects:
            c1, c2 = st.columns([5, 1])
            c1.write(f"**{p['title']}**  ·  {p.get('date', '')}")
            if c2.button("Delete", key=f"del_{p['id']}"):
                try:
                    delete_project(p["id"])
                    st.rerun()
                except Exception as e:
                    st.error(f"Couldn't delete: {e}")

    st.subheader("Diagnostics")
    if st.button("Test Gemini connection"):
        try:
            out = "".join(stream_reply([{"role": "user", "content": "Reply with the single word: ok"}]))
            st.success(f"Gemini responded: {out.strip()[:40]}")
        except Exception as e:
            st.error(explain_error(e))

    if st.button("Log out"):
        st.session_state.admin_ok = False
        st.rerun()


# ============================================================
# 11. ROUTER
# ============================================================

if page == "Chat":
    render_chat()
elif page == "Projects":
    render_projects()
else:
    render_manage()