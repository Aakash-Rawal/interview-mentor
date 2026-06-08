"""Interview Mentor — local Streamlit app (runs alongside the CLI).

Three pages (sidebar nav):
  - Learn & Mock : chat with the Tutor, or run a scored mock interview
  - Resume Lab   : ATS analysis / resume tailoring / cover letters
  - Control Panel: health, status, and .env settings

All conversation/mock state lives in st.session_state so it survives Streamlit
reruns. Single-user/local; Phase 3 puts FastAPI + auth between UI and agents.

Run from the project root:  streamlit run ui/app.py
"""
import os
import sys
import tempfile
from pathlib import Path

# Make the project root importable (Streamlit puts ui/ on sys.path, not root).
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import anthropic
import streamlit as st

import config
from question_bank.questions import QUESTIONS

ENV_PATH = config.BASE_DIR / ".env"
EXPECTED_TABLES = ["users", "sessions", "messages", "scores", "resumes", "applications"]
USER_ID = "local-user"  # shared with the CLI so scores/sessions are unified
DOMAIN_LABELS = {"pe": "Production Engineering / SRE", "ne": "Network Engineering"}


# ----------------------------------------------------------------- .env I/O
def parse_env() -> dict:
    out = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def update_env(updates: dict) -> None:
    lines = ENV_PATH.read_text().splitlines() if ENV_PATH.exists() else []
    remaining = dict(updates)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in remaining:
            lines[i] = f"{key}={remaining.pop(key)}"
    for key, val in remaining.items():
        lines.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


def effective(key: str, fallback: str = "") -> str:
    return parse_env().get(key) or fallback


def mask(secret: str) -> str:
    if not secret:
        return ""
    return f"{secret[:7]}…{secret[-4:]}" if len(secret) > 12 else "set"


# ----------------------------------------------------------------- checks
def check_database():
    try:
        from db.connection import get_cursor
        with get_cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema='public'")
            present = {r["table_name"] for r in cur.fetchall()}
        missing = [t for t in EXPECTED_TABLES if t not in present]
        if missing:
            return False, f"connected, but missing tables: {', '.join(missing)}"
        return True, "connected; all 6 tables present"
    except Exception as e:
        return False, f"cannot connect: {e}"


def check_skills():
    missing = [rel for rel in config.SKILL_FILES.values()
               if not (config.SKILLS_DIR / rel).exists()]
    if missing:
        return False, f"missing: {', '.join(missing)}"
    return True, f"all {len(config.SKILL_FILES)} skill files present"


def validate_key(model: str):
    key = effective("ANTHROPIC_API_KEY")
    if not key or key == "sk-ant-...":
        return False, "no API key set"
    try:
        client = anthropic.Anthropic(api_key=key)
        m = client.models.retrieve(model)
        return True, f"key valid; model '{m.id}' reachable"
    except anthropic.AuthenticationError:
        return False, "key rejected (authentication error)"
    except anthropic.NotFoundError:
        return False, f"key valid, but model '{model}' not found"
    except Exception as e:
        return False, f"error: {e}"


def db_counts():
    try:
        from db.connection import get_cursor
        counts = {}
        with get_cursor() as cur:
            for t in EXPECTED_TABLES:
                cur.execute(f"SELECT count(*) AS n FROM {t}")
                counts[t] = cur.fetchone()["n"]
        return counts
    except Exception:
        return None


# ----------------------------------------------------------------- state
def init_state():
    if "orch" not in st.session_state:
        from agents.orchestrator import Orchestrator
        from context.shared_context import SharedContext
        st.session_state.orch = Orchestrator()
        st.session_state.ctx = SharedContext(user_id=USER_ID)
        st.session_state.last_score = None
        st.session_state.resume_result = None
        try:
            from db.models import ensure_user
            ensure_user(USER_ID)
        except Exception:
            pass  # DB optional; Control Panel surfaces the problem


def render_score(score: dict):
    if not score:
        return
    if "error" in score:
        st.error(f"Scoring problem: {score['error']}")
        return
    st.metric(f"{score.get('topic', 'mock')} — total", f"{score.get('total')}/10")
    for dim, d in score.get("dimensions", {}).items():
        st.markdown(f"**{dim}** — {d.get('score')}/10 · {d.get('note')}")
    if score.get("summary"):
        st.info(f"**Summary:** {score['summary']}")
    if score.get("top_fix"):
        st.success(f"**Top fix:** {score['top_fix']}")


# ----------------------------------------------------------------- pages
def page_chat():
    ctx = st.session_state.ctx
    orch = st.session_state.orch
    interviewer = orch.interviewer

    st.subheader("Learn & Mock")
    c1, c2, c3 = st.columns(3)
    domains = list(config.DOMAINS.keys())
    dom = c1.selectbox("Domain", domains, index=domains.index(ctx.current_domain),
                       format_func=lambda d: config.DOMAINS[d], disabled=interviewer.active)
    if dom != ctx.current_domain and not interviewer.active:
        ctx.current_domain = dom
        ctx.current_topic = config.TOPICS[dom][0]
    topics = config.TOPICS[ctx.current_domain]
    cur_topic = ctx.current_topic if ctx.current_topic in topics else topics[0]
    topic = c2.selectbox("Topic", topics, index=topics.index(cur_topic),
                         disabled=interviewer.active)
    if not interviewer.active:
        ctx.current_topic = topic
    mode = c3.radio("Mode", ["Learn", "Mock"], horizontal=True, disabled=interviewer.active)

    st.divider()

    if mode == "Learn" and not interviewer.active:
        for m in ctx.session_history:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
        if prompt := st.chat_input(f"Ask the tutor about {topic.replace('_', ' ')}…"):
            with st.chat_message("user"):
                st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("Thinking…"):
                    reply = orch.tutor.respond(ctx, prompt)
                st.markdown(reply)
        return

    # ---- Mock mode ----
    if not interviewer.active:
        st.info("Start a mock on the selected topic. Answer turn by turn, then "
                "finish to get a scored rubric.")
        hints = st.checkbox("Hints on", value=False)
        if st.button("▶ Start mock", type="primary"):
            interviewer.start_mock(ctx, ctx.current_topic, hints=hints)
            st.session_state.last_score = None
            st.rerun()
        if st.session_state.last_score:
            st.divider()
            st.caption("Last mock result:")
            render_score(st.session_state.last_score)
        return

    # active mock
    st.warning(f"Mock in progress — {DOMAIN_LABELS.get(ctx.current_domain)} / {interviewer.topic}")
    if st.button("■ Finish & score", type="primary"):
        with st.spinner("Scoring…"):
            st.session_state.last_score = interviewer.finish_mock(ctx)
        st.rerun()
    for m in interviewer.transcript:
        with st.chat_message("assistant" if m["role"] == "assistant" else "user"):
            st.markdown(m["content"])
    if prompt := st.chat_input("Your answer…"):
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Interviewer…"):
                reply = interviewer.turn(ctx, prompt)
            st.markdown(reply)


def render_ats(rep: dict):
    if "error" in rep:
        st.error(f"Analysis problem: {rep['error']}")
        return
    st.metric("ATS match score", f"{rep.get('ats_score')}%")
    st.markdown("**Hard requirements**")
    icon = {"met": "✅", "weak": "🟡", "missing": "⬜"}
    for req in rep.get("hard_requirements", []):
        st.markdown(f"{icon.get(req.get('status'), '❔')} {req.get('requirement')} "
                    f"*( {req.get('status')} )*")
    if rep.get("keywords_missing"):
        st.markdown(f"**Keywords to add:** {', '.join(rep['keywords_missing'])}")
    if rep.get("preferred_quals_missing"):
        st.markdown(f"**Preferred quals missing:** {', '.join(rep['preferred_quals_missing'])}")
    if rep.get("verdict"):
        st.info(rep["verdict"])


def page_resume():
    ctx = st.session_state.ctx
    orch = st.session_state.orch
    st.subheader("Resume Lab")

    src = st.radio("Resume source", ["Paste", "Upload file"], horizontal=True)
    resume_text = ""
    if src == "Paste":
        resume_text = st.text_area("Your resume", value=ctx.base_resume_text or "", height=200)
    else:
        up = st.file_uploader("Resume (.pdf / .docx / .txt)", type=["pdf", "docx", "txt"])
        if up is not None:
            from agents.resume_agent import parse_resume_file
            suffix = os.path.splitext(up.name)[1]
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            try:
                tmp.write(up.getbuffer())
                tmp.close()
                resume_text = parse_resume_file(tmp.name)
                st.success(f"Parsed {up.name} — {len(resume_text)} characters")
            except Exception as e:
                st.error(f"Could not parse: {e}")
            finally:
                os.unlink(tmp.name)

    jd_text = st.text_area("Job description", value=ctx.active_jd or "", height=200)
    mode = st.radio("Mode", ["Analyze (ATS)", "Tailor resume", "Cover letter"], horizontal=True)
    tone = st.text_input("Tone", value="confident and professional") \
        if mode == "Cover letter" else None

    if st.button("Run", type="primary"):
        if not resume_text.strip() or not jd_text.strip():
            st.warning("Need both a resume and a job description.")
        else:
            with st.spinner("Working…"):
                if mode.startswith("Analyze"):
                    st.session_state.resume_result = ("analyze",
                                                      orch.run_resume(ctx, "analyze", resume_text, jd_text))
                elif mode.startswith("Tailor"):
                    st.session_state.resume_result = ("tailor",
                                                      orch.run_resume(ctx, "tailor", resume_text, jd_text))
                else:
                    st.session_state.resume_result = ("cover_letter",
                                                      orch.run_resume(ctx, "cover_letter", resume_text, jd_text, tone))

    result = st.session_state.resume_result
    if result:
        kind, payload = result
        st.divider()
        if kind == "analyze":
            render_ats(payload)
        elif kind == "tailor":
            st.text_area("Tailored resume", payload, height=400)
            st.download_button("⬇ Download .txt", payload, file_name="tailored_resume.txt")
        else:
            st.text_area("Cover letter", payload, height=320)
            st.download_button("⬇ Download .txt", payload, file_name="cover_letter.txt")


def page_panel():
    st.subheader("Control Panel")
    health_tab, status_tab, settings_tab = st.tabs(["🩺 Health", "📊 Status", "⚙️ Settings"])

    with health_tab:
        model = effective("MODEL_NAME", config.MODEL_NAME)
        key = effective("ANTHROPIC_API_KEY")
        key_set = bool(key) and key != "sk-ant-..."
        (st.success if key_set else st.error)(
            f"API key: {'set (' + mask(key) + ')' if key_set else 'NOT set'}")
        db_ok, db_msg = check_database()
        (st.success if db_ok else st.error)(f"Database: {db_msg}")
        sk_ok, sk_msg = check_skills()
        (st.success if sk_ok else st.error)(f"Skill files: {sk_msg}")
        st.divider()
        st.write(f"Validate the key and model **{model}** (metadata call — no token cost):")
        if st.button("Validate API key & model"):
            ok, msg = validate_key(model)
            (st.success if ok else st.error)(msg)

    with status_tab:
        c1, c2 = st.columns(2)
        c1.metric("Model in use", effective("MODEL_NAME", config.MODEL_NAME))
        c2.metric("Active domains", str(len(config.DOMAINS)))
        for dkey, dlabel in config.DOMAINS.items():
            st.write(f"**{dlabel}** — topics: {', '.join(config.TOPICS[dkey])}")
        st.divider()
        st.markdown("**Question bank**")
        by_domain = {}
        for q in QUESTIONS:
            by_domain.setdefault(q["domain"], {})
            by_domain[q["domain"]][q["topic"]] = by_domain[q["domain"]].get(q["topic"], 0) + 1
        cols = st.columns(len(config.DOMAINS))
        for col, (dkey, dlabel) in zip(cols, config.DOMAINS.items()):
            col.metric(dlabel, sum(by_domain.get(dkey, {}).values()))
        st.caption(f"{len(QUESTIONS)} questions total (Phase 1 bank — vector DB in Phase 2).")
        st.divider()
        st.markdown("**Database**")
        counts = db_counts()
        if counts is None:
            st.warning("Database not reachable — see the Health tab.")
        else:
            cols = st.columns(len(counts))
            for col, (t, n) in zip(cols, counts.items()):
                col.metric(t, n)

    with settings_tab:
        st.caption("Saved to `.env`. Restart the UI/CLI for changes to take effect.")
        cur_key = effective("ANTHROPIC_API_KEY")
        with st.form("env_form"):
            model_in = st.text_input("MODEL_NAME",
                                     value=effective("MODEL_NAME", config.MODEL_NAME),
                                     help="e.g. claude-sonnet-4-6 (default) or claude-opus-4-8")
            key_in = st.text_input("ANTHROPIC_API_KEY", value="", type="password",
                                   placeholder=f"current: {mask(cur_key) or 'not set'} — blank keeps it")
            db_in = st.text_input("DATABASE_URL",
                                  value=effective("DATABASE_URL", config.DATABASE_URL))
            submitted = st.form_submit_button("Save to .env")
        if submitted:
            updates = {}
            if model_in.strip():
                updates["MODEL_NAME"] = model_in.strip()
            if db_in.strip():
                updates["DATABASE_URL"] = db_in.strip()
            if key_in.strip():
                updates["ANTHROPIC_API_KEY"] = key_in.strip()
            if updates:
                update_env(updates)
                st.success(f"Saved: {', '.join(updates)}. Restart the UI/CLI to apply.")
            else:
                st.info("Nothing to save.")


# ----------------------------------------------------------------- main
st.set_page_config(page_title="Interview Mentor", layout="wide")
init_state()

st.sidebar.title("Interview Mentor")
page = st.sidebar.radio("Go to", ["💬 Learn & Mock", "📄 Resume Lab", "🛠 Control Panel"])
st.sidebar.divider()
st.sidebar.caption(f"Model: {effective('MODEL_NAME', config.MODEL_NAME)}")
st.sidebar.caption(f"Domain: {DOMAIN_LABELS.get(st.session_state.ctx.current_domain)}")
st.sidebar.caption(f"User: {USER_ID}")

if page.endswith("Learn & Mock"):
    page_chat()
elif "Resume" in page:
    page_resume()
else:
    page_panel()
