#!/usr/bin/env bash
# Stop and remove the launchd agent and the Dock launcher.
set -euo pipefail
LABEL="com.interviewmentor.server"
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
rm -rf "$HOME/Applications/Interview Mentor.app"
echo "Removed $LABEL"
