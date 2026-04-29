import os

import anthropic
import streamlit as st

from chat_tools import TOOLS, execute_tool
from sidebar import render_filters

st.set_page_config(page_title="Ask About Your Clients", page_icon="💬", layout="wide")
st.title("💬 Ask About Your Clients")
st.caption(
    "Ask natural-language questions about clients, trips, destinations, or revenue. "
    "Claude will query your live Salesforce data to answer."
)

# ── Load data ─────────────────────────────────────────────────────────────────
_, df_all, trip_clients = render_filters()

# ── Anthropic client ──────────────────────────────────────────────────────────
def _get_api_key() -> str:
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.getenv("ANTHROPIC_API_KEY", "")


api_key = _get_api_key()
if not api_key:
    st.error(
        "No Anthropic API key found. Add `ANTHROPIC_API_KEY` to `.streamlit/secrets.toml` "
        "or your `.env` file."
    )
    st.stop()

client = anthropic.Anthropic(api_key=api_key)

SYSTEM_PROMPT = """You are a smart travel business analyst assistant for Company Crossing, \
a luxury travel company. You have access to the company's live Salesforce data via tools. \
Always use the tools to fetch real data before answering — never guess or make up figures. \
If you are unsure of the exact client name, use search_clients first. \
Present answers clearly and concisely, using markdown formatting. \
Today's date is {today}."""

# ── Session state ─────────────────────────────────────────────────────────────
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# ── Render history ────────────────────────────────────────────────────────────
for msg in st.session_state.chat_messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── Input ─────────────────────────────────────────────────────────────────────
prompt = st.chat_input("Ask anything about your clients or business…")

if prompt:
    # Show user message immediately
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Build message history for the API (exclude system prompt — passed separately)
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.chat_messages
    ]

    with st.chat_message("assistant"):
        with st.status("Thinking…", expanded=False) as status:
            from datetime import date as _date

            system = SYSTEM_PROMPT.format(today=_date.today().strftime("%d %b %Y"))

            # ── Agentic tool-use loop ─────────────────────────────────────────
            while True:
                response = client.messages.create(
                    model="claude-opus-4-7",
                    max_tokens=4096,
                    system=[
                        {
                            "type": "text",
                            "text": system,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                    tools=TOOLS,
                    messages=api_messages,
                )

                # Collect any tool calls from this response turn
                tool_calls = [b for b in response.content if b.type == "tool_use"]

                if not tool_calls:
                    # No more tool use — we have the final answer
                    break

                # Show which tools are running
                tool_names = ", ".join(t.name for t in tool_calls)
                status.update(label=f"Running: {tool_names}…")

                # Append assistant turn (with tool_use blocks) to history
                api_messages.append({"role": "assistant", "content": response.content})

                # Execute each tool and build tool_result blocks
                tool_results = []
                for tc in tool_calls:
                    result_text = execute_tool(
                        tc.name, tc.input, df_all, trip_clients
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": result_text,
                        }
                    )

                # Append tool results as a user turn
                api_messages.append({"role": "user", "content": tool_results})

            status.update(label="Done", state="complete", expanded=False)

        # Extract and display the final text answer
        final_text = next(
            (b.text for b in response.content if hasattr(b, "text")), ""
        )
        st.markdown(final_text)

    # Save assistant answer to session history (plain text only)
    st.session_state.chat_messages.append(
        {"role": "assistant", "content": final_text}
    )

# ── Clear button ──────────────────────────────────────────────────────────────
if st.session_state.chat_messages:
    if st.button("Clear conversation", type="secondary"):
        st.session_state.chat_messages = []
        st.rerun()
