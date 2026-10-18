#!/bin/bash
# Installiert oder aktualisiert Radio LoLa auf dem Reachy Mini Wireless.
# Aufruf auf dem Roboter (nach „ssh pollen@reachy-mini.local“):
#   curl -fsSL https://github.com/Moe-Joe86/Radio-LoLa/releases/latest/download/installieren.sh | bash
#
# Weg aus Pollens Doku („Offline / manual deployment for a Wireless unit“): Apps liegen in /venvs/apps_venv.
# Das Paket wird ohne Abhängigkeiten installiert, weil reachy-mini (mit numpy und GStreamer) dort schon liegt.
set -euo pipefail

# Die drei Werte lassen sich nur zum Testen ändern.
PAKET="${RADIO_PAKET:-https://github.com/Moe-Joe86/Radio-LoLa/releases/latest/download/radio_lola-0.1.0-py3-none-any.whl}"
APPS="${RADIO_APPS:-/venvs/apps_venv}"
DAEMON="${RADIO_DAEMON:-/venvs/mini_daemon}"

installieren() {  # installieren <python> <paket…>
    local python="$1"; shift
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$python" "$@"
    elif [ -x /opt/uv/uv ]; then
        /opt/uv/uv pip install --python "$python" "$@"
    else
        "$python" -m pip install "$@"
    fi
}

if [ ! -x "$APPS/bin/python" ]; then
    # So legt auch der Daemon die App-Umgebung an, wenn man die erste App aus dem App-Store installiert.
    echo "Radio LoLa: lege die App-Umgebung $APPS an …"
    "$DAEMON/bin/python" -m venv "$APPS"
    VERSION=$("$DAEMON/bin/python" -c "from importlib.metadata import version; print(version('reachy_mini'))")
    installieren "$APPS/bin/python" "reachy-mini==$VERSION"
fi

echo "Radio LoLa: lade und installiere die App …"
installieren "$APPS/bin/python" --no-deps --force-reinstall "$PAKET"

"$APPS/bin/python" -c "from radio_lola.main import RadioLola; from radio_lola.einstellungen import laden; laden()"
LISTE=$(curl -fsS http://localhost:8000/api/apps/list-available/installed || true)
if grep -q '"radio_lola"' <<<"$LISTE"; then
    echo "Radio LoLa: FERTIG. Der Daemon kennt die App. Jetzt in der Handy-App auf „Radio starten“ drücken."
else
    echo "Radio LoLa: installiert, aber der Daemon listet sie noch nicht. Roboter einmal aus- und einschalten."
fi
