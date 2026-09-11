#!/usr/bin/env bash
# Install Interview Mentor as a macOS launchd user agent so it starts at login
# and stays running at http://127.0.0.1:8765. Safe to re-run: it replaces the
# existing agent. Also creates ~/Applications/Interview Mentor.app, a tiny
# launcher that just opens the URL (drag it to the Dock).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.interviewmentor.server"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG_DIR="$HOME/Library/Logs"
PORT="${APP_PORT:-8765}"
URL="http://127.0.0.1:$PORT"
PYTHON="$ROOT/.venv/bin/python"

[ -x "$PYTHON" ] || { echo "No virtualenv at $ROOT/.venv — run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"; exit 1; }
[ -f "$ROOT/.env" ] || { echo "No .env at $ROOT — copy .env.example and add your ANTHROPIC_API_KEY first"; exit 1; }

mkdir -p "$HOME/Library/LaunchAgents" "$LOG_DIR"
cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON</string>
    <string>-m</string><string>uvicorn</string>
    <string>app.main:app</string>
    <string>--host</string><string>127.0.0.1</string>
    <string>--port</string><string>$PORT</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>PYTHONUNBUFFERED</key><string>1</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>ThrottleInterval</key><integer>5</integer>
  <key>StandardOutPath</key><string>$LOG_DIR/interview-mentor.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/interview-mentor.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "Installed $LABEL (log: $LOG_DIR/interview-mentor.log)"

# Wait for the server, then open it.
for _ in $(seq 1 30); do
  if curl -fsS "$URL/api/health" >/dev/null 2>&1; then break; fi
  sleep 1
done

# Dock launcher: an AppleScript app that opens the URL in the default browser.
APP_DIR="$HOME/Applications"
mkdir -p "$APP_DIR"
if command -v osacompile >/dev/null; then
  osacompile -o "$APP_DIR/Interview Mentor.app" -e "do shell script \"open $URL\"" >/dev/null 2>&1 \
    && echo "Created '$APP_DIR/Interview Mentor.app' — drag it to the Dock." || true
fi

echo "Open: $URL"
open "$URL" 2>/dev/null || true
