import streamlit as st
from google import genai
from google.genai import types
import PyPDF2
import os

# ============================================================
# 1. RESOLVE FILE PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

IMAGE_PATH = os.path.join(BASE_DIR, "profile.jpg")
PDF_PATH = os.path.join(BASE_DIR, "Sunidhi_Portfolio.pdf")


# ============================================================
# 2. PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Sunidhi AI",
    page_icon="✨",
    layout="wide"
)


# ============================================================
# 3. CUSTOM CSS
# ============================================================

st.markdown("""
<style>

    /* Main App Background */
    .stApp {
        background-color: #FFFFFF !important;
        font-family: 'Google Sans', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #F0F4F9 !important;
        padding-top: 2rem;
    }

    /* Sidebar Profile Picture */
    [data-testid="stSidebar"] img {
        border-radius: 50%;
        max-width: 180px;
        margin: 0 auto;
        display: block;
    }

    /* Sidebar Text */
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p {
        color: #1F1F1F !important;
    }

    /* Sidebar Links */
    .sidebar-link {
        color: #0A56D1 !important;
        text-decoration: none;
        font-weight: 500;
    }

    .sidebar-link:hover {
        text-decoration: underline;
    }

    /* Main Title */
    .gemini-title {
        font-size: 2.2rem;
        font-weight: 500;
        color: #1F1F1F;
        padding-bottom: 2rem;
    }

    /* Chat Messages */
    .stChatMessage {
        background-color: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* User Message */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even) {
        background-color: #F0F4F9 !important;
        border-radius: 24px;
        padding: 12px 24px !important;
        margin: 15px 0 15px auto !important;
        max-width: 80%;
        color: #1F1F1F;
        display: block;
        width: fit-content;
    }

    /* AI Message */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(odd) {
        background-color: transparent !important;
        padding: 10px 0px 30px 0px !important;
        margin: 0 !important;
        max-width: 100%;
        color: #1F1F1F;
    }

    /* Hide User Avatar */
    .stChatMessage[data-testid="stChatMessage"]:nth-child(even)
    div[data-testid="stChatMessageAvatar"] {
        display: none;
    }

    /* Chat Input */
    [data-testid="stChatInput"] {
        border-radius: 30px !important;
        background-color: #F0F4F9 !important;
        border: none !important;
    }

    [data-testid="stChatInput"] textarea {
        color: #1F1F1F !important;
    }

</style>
""", unsafe_allow_html=True)


# ============================================================
# 4. CONNECT TO GEMINI
# ============================================================

try:
    client = genai.Client(
        api_key=st.secrets["GEMINI_API_KEY"]
    )
except Exception as e:
    st.error("Could not connect to Gemini. Please check your GEMINI_API_KEY.")
    st.stop()


# ============================================================
# 5. EXTRACT PDF CONTENT
# ============================================================

@st.cache_data
def extract_portfolio_data():

    text = ""

    if not os.path.exists(PDF_PATH):
        return (
            "Database document not found. "
            "Please ensure Sunidhi_Portfolio.pdf is uploaded."
        )

    try:
        with open(PDF_PATH, "rb") as file:

            reader = PyPDF2.PdfReader(file)

            for page in reader.pages:

                page_text = page.extract_text()

                if page_text:
                    text += page_text + "\n"

        return text

    except Exception as e:

        return f"Error reading PDF: {e}"


portfolio_data = extract_portfolio_data()


# ============================================================
# 6. LEFT SIDEBAR
# ============================================================

with st.sidebar:

    # Profile image
    if os.path.exists(IMAGE_PATH):

        st.image(
            IMAGE_PATH,
            width="stretch"
        )

    # Name
    st.markdown(
        """
        <h2 style='text-align: center; margin-top: 15px;'>
            Sunidhi Rusia
        </h2>
        """,
        unsafe_allow_html=True
    )

    # Title
    st.markdown(
        """
        <p style='text-align: center; font-size: 0.95rem;'>
            AI Architect & Data Engineer
        </p>
        """,
        unsafe_allow_html=True
    )

    # Links
    st.markdown(
        """
        <div style='text-align: center; margin-bottom: 20px;'>
            <a
                href="https://www.linkedin.com/in/sunidhi-rusia"
                target="_blank"
                class="sidebar-link"
            >
                LinkedIn
            </a>
            |
            <a
                href="mailto:sunidhirusia22@gmail.com"
                class="sidebar-link"
            >
                Email
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    # About Me
    st.markdown("### About Me")

    st.write(
        "M.S. in Business Analytics & AI at Stevens Institute of Technology. "
        "Specializing in ML, supply chain analytics, and enterprise AI orchestration."
    )

    # Technical Skills
    st.markdown("### Technical Skills")

    st.write(
        "**AI/ML:** Llama-3.3-70B, Azure OpenAI, Claude API, "
        "Prompt Engineering, NLP"
    )

    st.write(
        "**Data:** Python, SQL, Pandas, XGBoost, AWS S3, Supabase"
    )

    # Featured Projects
    with st.expander("Featured Projects"):

        st.markdown(
            "- **Athenica Generative AI:** Enterprise Llama-3 deployment."
        )

        st.markdown(
            "- **StartupHub:** Full-stack talent platform via Claude API."
        )

        st.markdown(
            "- **Agentic Coach:** Microsoft Copilot Studio system."
        )


# ============================================================
# 7. MAIN CHAT INTERFACE
# ============================================================

st.markdown(
    '<div class="gemini-title">✨ Hello, I\'m Sunidhi AI</div>',
    unsafe_allow_html=True
)


# ============================================================
# 8. SYSTEM INSTRUCTION
# ============================================================

SYSTEM_INSTRUCTION = f"""
You are Sunidhi AI, the interactive professional portfolio assistant
for Sunidhi Rusia.

Your primary source of truth is the following extracted data from
Sunidhi's official portfolio PDF:

<portfolio_database>
{portfolio_data}
</portfolio_database>

IMPORTANT RULES:

1. Answer questions accurately based ONLY on the information contained
   in the portfolio database above.

2. Do not invent experience, education, skills, projects, companies,
   job titles, achievements, dates, or technologies that are not
   present in the portfolio database.

3. Maintain a highly intelligent, concise, professional, and helpful
   tone.

4. If asked for contact details, provide:

   Email:
   sunidhirusia22@gmail.com

   LinkedIn:
   https://www.linkedin.com/in/sunidhi-rusia

5. Use Markdown formatting when useful:
   - Bullet points
   - Bold text
   - Short paragraphs
   - Clear sections

6. If the user asks something that is not covered by the portfolio,
   politely explain that your knowledge is limited to Sunidhi's
   professional portfolio.

7. Do not claim to know information that is not present in the
   portfolio database.

8. When discussing Sunidhi's skills or experience, prioritize the
   portfolio database over assumptions.

9. You are a portfolio assistant, not a general-purpose assistant.
"""


# ============================================================
# 9. CREATE GEMINI CHAT
# ============================================================

if "chat" not in st.session_state:

    st.session_state.chat = client.chats.create(
        model="gemini-3.8-flash",
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            temperature=0.4
        )
    )


# ============================================================
# 10. INITIALIZE DISPLAY HISTORY
# ============================================================

if "chat_history" not in st.session_state:

    st.session_state.chat_history = [
        {
            "role": "assistant",
            "text": (
                "I am trained on Sunidhi's complete portfolio, "
                "technical skills, projects, and coursework. "
                "What would you like to know?"
            )
        }
    ]


# ============================================================
# 11. DISPLAY PREVIOUS MESSAGES
# ============================================================

for message in st.session_state.chat_history:

    role = message["role"]

    avatar = "✨" if role == "assistant" else None

    with st.chat_message(
        role,
        avatar=avatar
    ):

        st.markdown(message["text"])


# ============================================================
# 12. CHAT INPUT
# ============================================================

prompt = st.chat_input(
    "Message Sunidhi AI..."
)


# ============================================================
# 13. PROCESS USER MESSAGE
# ============================================================

if prompt:

    # ------------------------------------------
    # Display user message
    # ------------------------------------------

    st.session_state.chat_history.append(
        {
            "role": "user",
            "text": prompt
        }
    )

    with st.chat_message(
        "user",
        avatar=None
    ):

        st.markdown(prompt)


    # ------------------------------------------
    # Generate Gemini response
    # ------------------------------------------

    with st.chat_message(
        "assistant",
        avatar="✨"
    ):

        try:

            response = st.session_state.chat.send_message(
                prompt
            )

            answer = response.text

            st.markdown(answer)

            # Save assistant response
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "text": answer
                }
            )

        except Exception as e:

            error_message = (
                "Sorry, I couldn't connect to Gemini right now. "
                "Please check your API key and Gemini configuration.\n\n"
                f"**Error:** `{str(e)}`"
            )

            st.error(error_message)

            # Remove user message from display history if request failed
            st.session_state.chat_history.pop()
