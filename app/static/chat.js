/* Interview Mentor — streaming chat glue. No framework, no build step. */
window.IM = (() => {
  const ERROR_MARKER = "\n\x1e ERROR: ";

  function render(el) {
    const raw = el.dataset.raw !== undefined ? el.dataset.raw : el.textContent;
    el.dataset.raw = raw;
    if (window.marked && window.DOMPurify) {
      el.innerHTML = DOMPurify.sanitize(marked.parse(raw, { breaks: true, gfm: true }));
      if (window.hljs) el.querySelectorAll("pre code").forEach((c) => hljs.highlightElement(c));
    } else {
      el.textContent = raw;              // CDN blocked: fall back to plain text
      el.style.whiteSpace = "pre-wrap";
    }
  }

  function renderAll(root = document) { root.querySelectorAll(".md").forEach(render); }

  function bubble(log, role) {
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    const b = document.createElement("div");
    b.className = "bubble md";
    wrap.appendChild(b);
    log.appendChild(wrap);
    return b;
  }

  function scroll(log) { log.scrollTop = log.scrollHeight; }

  async function streamInto(endpoint, text, target, log) {
    const body = new FormData();
    body.append("text", text);
    const res = await fetch(endpoint, { method: "POST", body });
    if (!res.ok) {
      let msg = `Request failed (${res.status})`;
      try { const j = await res.json(); if (j.detail) msg = j.detail; } catch (_) {}
      throw new Error(msg);
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let acc = "", last = 0;
    target.classList.add("cursor");
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      acc += decoder.decode(value, { stream: true });
      const now = performance.now();
      if (now - last > 80) {              // throttle re-render while streaming
        target.dataset.raw = acc.split(ERROR_MARKER)[0];
        render(target); scroll(log); last = now;
      }
    }
    target.classList.remove("cursor");
    const [reply, err] = acc.split(ERROR_MARKER);
    target.dataset.raw = reply;
    render(target); scroll(log);
    if (err !== undefined) throw new Error(err.trim());
    return reply;
  }

  function setupChat({ form, input, log, button, onFirstReply }) {
    const $form = document.querySelector(form), $input = document.querySelector(input),
          $log = document.querySelector(log), $btn = document.querySelector(button);
    const endpoint = $form.dataset.endpoint;
    let busy = false, replies = 0;
    scroll($log);

    async function send() {
      const text = $input.value.trim();
      if (!text || busy) return;
      busy = true; $btn.disabled = true; $input.disabled = true;
      $log.querySelector(".empty")?.remove();
      const u = bubble($log, "user"); u.dataset.raw = text; render(u);
      $input.value = "";
      const a = bubble($log, "assistant");
      scroll($log);
      try {
        await streamInto(endpoint, text, a, $log);
        replies += 1;
        if (replies === 1 && onFirstReply) onFirstReply();
      } catch (e) {
        if (!a.dataset.raw) a.parentElement.remove();
        const err = bubble($log, "assistant"); err.classList.add("error");
        err.textContent = e.message; scroll($log);
      } finally {
        busy = false; $btn.disabled = false; $input.disabled = false; $input.focus();
      }
    }

    $form.addEventListener("submit", (e) => { e.preventDefault(); send(); });
    $input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
    });
  }

  function setupFinish({ button, notice }) {
    const $btn = document.querySelector(button), $notice = document.querySelector(notice);
    $btn.addEventListener("click", async () => {
      if (!confirm("Finish this mock and get scored?")) return;
      $btn.disabled = true; $notice.hidden = false;
      try {
        const res = await fetch($btn.dataset.endpoint, { method: "POST" });
        const j = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(j.error || j.detail || `Scoring failed (${res.status})`);
        location.reload();
      } catch (e) {
        alert(e.message); $btn.disabled = false; $notice.hidden = true;
      }
    });
  }

  return { renderAll, setupChat, setupFinish };
})();
