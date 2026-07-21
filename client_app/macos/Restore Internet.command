#!/bin/bash
# Restore Internet — failsafe residual VPN clear + remove product app (macOS)
# Double-click in Finder (or run in Terminal). Display name: "Restore Internet"
set -euo pipefail

echo "================================================================"
echo "===  BIG WARNING — READ BEFORE RUNNING RESTORE INTERNET  ==="
echo "================================================================"
echo "Running Restore Internet will ERASE ALL parts of Restore Privacy"
echo "from this device (app, tunnel residual, shortcuts, product secrets)."
echo "You may NOT be able to automatically re-download your subscription"
echo "app afterward. Contact russell.gray.sneddon@gmail.com to obtain a"
echo "new download link."
echo "================================================================"
echo ""
echo "=== Restore Internet (macOS) ==="
echo "Stopping product VPN residual and removing Restore Privacy app..."

# Best-effort: tear down product VPN configurations (requires user approval on some macOS)
if command -v scutil >/dev/null 2>&1; then
  # List and remove NE VPN configs named for the product when possible
  scutil --nc list 2>/dev/null | grep -i 'restore\|privacy' || true
fi

# Stop running product
pkill -f 'restore_privacy_client' 2>/dev/null || true
pkill -f 'Restore Privacy' 2>/dev/null || true
sleep 0.5 || true

# Remove common install locations
for APP in \
  "/Applications/restore_privacy_client.app" \
  "$HOME/Applications/restore_privacy_client.app" \
  "$HOME/Desktop/restore_privacy_client.app"
 do
  if [[ -d "$APP" ]]; then
    echo "Removing $APP"
    rm -rf "$APP" || true
  fi
done

# Remove app next to this script (unzipped package layout)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -d "$SCRIPT_DIR/restore_privacy_client.app" ]]; then
  rm -rf "$SCRIPT_DIR/restore_privacy_client.app" || true
fi
# If this .command lives inside the .app package tree, remove parent .app after exit
if [[ "$SCRIPT_DIR" == *".app/"* ]]; then
  APP_ROOT="${SCRIPT_DIR%%.app/*}.app"
  nohup bash -c "sleep 1; rm -rf $(printf %q "$APP_ROOT")" >/dev/null 2>&1 &
fi

# Product secrets
rm -rf "$HOME/.restore-privacy" 2>/dev/null || true
# App Group leftovers (best-effort)
rm -rf "$HOME/Library/Group Containers/group.com.restoreprivacy.shared" 2>/dev/null || true
rm -rf "$HOME/Library/Containers/com.restoreprivacy.restorePrivacyClient" 2>/dev/null || true

echo ""
echo "Restore Internet complete."
echo "- If a VPN profile remains: System Settings → Network → VPN & Filters → remove Restore Privacy."
echo "- Reinstall the macOS package to use the product again."
echo ""
read -r -p "Press Enter to close..." _ || true
exit 0
