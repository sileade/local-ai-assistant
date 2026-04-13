#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Grafana Kiosk Setup for Mac Mini
# Displays AI Cluster — Full Monitoring dashboard on physical screen
# ═══════════════════════════════════════════════════════════════

set -e

GRAFANA_URL="https://grafana.sclg.io/d/ai-cluster-v2/ai-cluster-e28094-full-monitoring-4-nodes-7-gpus?orgId=1&kiosk&refresh=30s"
CHROME_APP="/Applications/Google Chrome.app"
CHROMIUM_APP="/Applications/Chromium.app"
PLIST_NAME="io.sclg.grafana-kiosk"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
KIOSK_SCRIPT="$HOME/bin/grafana-kiosk.sh"

echo "═══ Grafana Kiosk Setup ═══"

# Detect browser
if [ -d "$CHROME_APP" ]; then
    BROWSER="$CHROME_APP/Contents/MacOS/Google Chrome"
    BROWSER_NAME="Google Chrome"
elif [ -d "$CHROMIUM_APP" ]; then
    BROWSER="$CHROMIUM_APP/Contents/MacOS/Chromium"
    BROWSER_NAME="Chromium"
else
    echo "ERROR: Neither Google Chrome nor Chromium found."
    echo "Install Chrome: brew install --cask google-chrome"
    exit 1
fi

echo "Browser: $BROWSER_NAME"
echo "Dashboard: $GRAFANA_URL"

# Create kiosk launch script
mkdir -p "$HOME/bin"
cat > "$KIOSK_SCRIPT" << 'KIOSK_EOF'
#!/bin/bash
# Grafana Kiosk Launcher
# Waits for network, then opens Grafana in fullscreen kiosk mode

GRAFANA_URL="__GRAFANA_URL__"
BROWSER="__BROWSER__"

# Wait for network (max 60 seconds)
for i in $(seq 1 60); do
    if curl -s --max-time 3 -o /dev/null https://grafana.sclg.io; then
        break
    fi
    sleep 1
done

# Kill any existing kiosk Chrome instances
pkill -f "grafana-kiosk-profile" 2>/dev/null || true
sleep 2

# Launch Chrome in kiosk mode with separate profile
"$BROWSER" \
    --kiosk \
    --no-first-run \
    --no-default-browser-check \
    --disable-translate \
    --disable-infobars \
    --disable-session-crashed-bubble \
    --disable-features=TranslateUI \
    --autoplay-policy=no-user-gesture-required \
    --user-data-dir="$HOME/.config/grafana-kiosk-profile" \
    --window-position=0,0 \
    "$GRAFANA_URL" &

# Wait for window to appear, then make it fullscreen
sleep 5

# Use AppleScript to ensure fullscreen
osascript -e '
tell application "Google Chrome"
    activate
    delay 1
    tell application "System Events"
        keystroke "f" using {command down, control down}
    end tell
end tell
' 2>/dev/null || true
KIOSK_EOF

# Replace placeholders
sed -i '' "s|__GRAFANA_URL__|${GRAFANA_URL}|g" "$KIOSK_SCRIPT"
sed -i '' "s|__BROWSER__|${BROWSER}|g" "$KIOSK_SCRIPT"
chmod +x "$KIOSK_SCRIPT"

echo "Created: $KIOSK_SCRIPT"

# Create launchd plist for auto-start on login
cat > "$PLIST_PATH" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${KIOSK_SCRIPT}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>0</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/grafana-kiosk.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/grafana-kiosk-error.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
        <key>HOME</key>
        <string>${HOME}</string>
    </dict>
</dict>
</plist>
PLIST_EOF

echo "Created: $PLIST_PATH"

# Load the agent
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo ""
echo "═══ Setup Complete ═══"
echo ""
echo "Grafana kiosk will auto-start on login."
echo ""
echo "Commands:"
echo "  Start now:    bash $KIOSK_SCRIPT"
echo "  Stop:         pkill -f grafana-kiosk-profile"
echo "  Disable:      launchctl unload $PLIST_PATH"
echo "  Enable:       launchctl load $PLIST_PATH"
echo "  Logs:         tail -f ~/Library/Logs/grafana-kiosk.log"
echo ""
echo "Dashboard URL:"
echo "  $GRAFANA_URL"
