<p align="center"><img src="docs/icon.png" alt="Radio LoLa" width="160"></p>

# Radio LoLa

**Another radio for the [Reachy Mini Wireless](https://huggingface.co/docs/reachy_mini) robot, controlled with an Android-APP and its antennas.**

One antenna tunes through the stations, with radio noise between them, just like the dial of an old radio. The
other antenna sets the volume. The radio runs as an app directly on the robot, and a small Android app (German and
English) starts and stops it, picks stations, sets the volume and manages the station list. You only need a computer
once, to install the radio on the robot.

> Radio LoLa is a hobby project. It is not affiliated with Pollen Robotics or Hugging Face.

## Features

- **Antenna controls:** the robot's right antenna (on the left seen from the front) tunes stations, the left one
  (on the right seen from the front) sets the volume. Between stations you hear noise; at the edges of a station the
  sound fades smoothly between station and noise.
- **Phone app:** start and stop the radio, see which station is playing, tap a station, set the volume, mute.
  Picking a station or a volume on the phone **turns the robot's antenna** to the matching position, so the antennas
  always agree with the phone and you can keep turning them by hand.
- **Station list:** add stations (by stream address; the name usually comes from the station itself) and remove
  them, up to 8. The list is kept on the robot and survives updates.
- **Careful with the hardware:** only one antenna moves at a time. If one antenna points towards the middle and the
  other one would have to go there too, the first one parks at the top for a moment, so they cannot collide. When the
  radio stops, both antennas go home and the motors are switched on again.
- **Runs on the robot:** the radio is a regular Reachy Mini app, started and stopped by the robot's daemon. No
  computer needs to stay on.

## What you need

- A Reachy Mini **Wireless** in your Wi-Fi.
- An Android phone (Android 7 or newer) in the same Wi-Fi.
- Once, for installing: a computer (Windows, macOS or Linux) in the same Wi-Fi.

## 1. Install the radio on the robot

Needed once, and again whenever you want a newer version.

1. Switch on the robot and wait about a minute.
2. Open a terminal on your computer:
   - **Windows:** press the Windows key, type `PowerShell`, click **Windows PowerShell**.
   - **macOS:** **Finder** → **Applications** → **Utilities** → **Terminal**.
3. Type the following and press **Enter**:

   ```
   ssh pollen@reachy-mini.local
   ```

   If you get “Could not resolve hostname”, use the robot's IP address instead of `reachy-mini.local`, e.g.
   `ssh pollen@192.168.178.50`. You find the IP in your router's list of devices.
4. The very first time you are asked “Are you sure you want to continue connecting (yes/no)?”: type `yes`,
   press **Enter**.
5. At “password:” type `root` (nothing appears while typing, that is normal) and press **Enter**. This is the default
   password from Pollen's documentation; if you changed it, use yours.
6. Copy this line, paste it into the window (Windows: **right-click**; macOS: **⌘ + V**) and press **Enter**:

   ```
   curl -fsSL https://github.com/Moe-Joe86/Radio-LoLa/releases/latest/download/install.sh | bash
   ```

7. Wait for **“Radio LoLa: DONE”**. This usually takes less than a minute; the very first time it can take up to about
   ten minutes if the robot still has to create its app environment. If it says “the daemon does not list it yet”,
   switch the robot off and on once.
8. Type `exit`, press **Enter** and close the window.

The install follows Pollen's “Offline / manual deployment for a Wireless unit” in
[Building & Publishing Apps](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/SDK/apps.md): the app
is installed into the robot's app environment `/venvs/apps_venv`, where the daemon finds it by itself.

## 2. Install the Android app

Open this link on your phone:

**https://github.com/Moe-Joe86/Radio-LoLa/releases/latest/download/Radio-LoLa.apk**

The first time, Android asks whether your browser may install apps: tap **Settings**, allow it (“Allow from this
source” or “Install unknown apps”), go back and tap **Install**. A newer APK installs over the old one the same way.

At the bottom of the app is the robot's address, `reachy-mini.local` by default. Some phones cannot find this name;
then the app keeps showing “Robot not reachable”. In that case enter the robot's IP address instead. The app
remembers it. The language switch (**DE** / **EN**) is at the top right.

## 3. Use it

1. Switch on the robot and open the app. It shows whether the robot is reachable.
2. Tap **Start radio**. The robot wakes up, the antennas go to their start position, then the radio plays.
3. Turn the antennas by hand, or use the phone:
   - **Volume antenna:** up is quiet; turning it counter-clockwise (seen from the front) makes it louder.
   - **Tuning antenna:** each station has its own field on the circle, with noise in between.
   - **Phone:** tap a station or release the volume slider, and the robot turns the matching antenna there.
     **Mute** only silences the sound and does not move an antenna.
4. Tap **Stop radio**. The antennas go home one after the other and the motors are switched on again.

The volume slider, the station buttons and **Add**/**Delete** work while the radio is playing. When the radio is
off, the app shows the last known station list greyed out.

Only one Reachy Mini app can run at a time. If another app is running, the phone app says so; stop it first.

## Managing stations

- **Add:** tap **Add**, enter the stream address (the direct link to the audio stream, starting with `http://` or
  `https://`; `.m3u` and `.pls` playlists work too) and optionally a name. The robot connects to the stream once to
  check it. If you leave the name empty, it takes the name the station sends along (`icy-name`), otherwise the
  address' host name. MP3 streams are the safest choice. Up to 8 stations.
- **Delete:** tap **Delete**, choose the station and confirm. The last station cannot be removed.
- After a change, all fields on the tuning antenna shift a little. The robot then turns the antenna back to the
  station that was playing, so you keep hearing it.

The list lives on the robot in `~/.config/radio_lola/stations.json` and is not touched by updates. The stations in
[`robot_app/radio_lola/settings.toml`](robot_app/radio_lola/settings.toml) are only the starting list for the very
first start. Default stations: WDR 2, 1LIVE, WDR 3, WDR 4 and WDR 5 (German public radio).

## Other settings

[`robot_app/radio_lola/settings.toml`](robot_app/radio_lola/settings.toml) also holds the highest volume, the usable
angle and counting direction of the tuning antenna, and the width of the crossfade between station and noise. To
change them, edit the file in your own fork, let the GitHub workflow build a release, and install from your fork
(replace `Moe-Joe86` in the `curl` line and in `robot_app/install.sh`).

## How it works

```
Phone app ──HTTP──▶ daemon on the robot (port 8000): start / stop the app, status
          ──HTTP──▶ Radio LoLa app on the robot (port 8042): stations, volume, mute, add / delete
                      │
                      ├─ reads both antennas every 64 ms, mixes station sound and noise, plays it
                      └─ a second thread turns an antenna when the phone asks for it
```

- **The daemon** is Pollen's control program. It starts with the robot and runs all the time. It starts an app as a
  separate program and stops it with a signal; Radio LoLa then brings the antennas home and ends.
- **The radio does not start by itself** when the robot is switched on; you start it from the phone. The daemon
  can start one app automatically on wake-up (“startup app”, see Pollen's docs), but this project does not set that.
- **Sound:** each station is received with GStreamer (included with the robot's software), converted to 16 kHz mono,
  mixed with white noise according to the tuning antenna, and played through the robot's speaker.
- **Logs:** the radio writes no files of its own. Its messages go to the daemon's log. On the robot:
  `sudo journalctl -u reachy-mini-daemon --since "1 hour ago"`.

## Project layout

| Folder | Contents |
|---|---|
| `robot_app/` | the Reachy Mini app (structure from Pollen's `reachy-mini-app-assistant`) and `install.sh` |
| `robot_app/radio_lola/` | `main.py` (app), `tuning.py` (stations, noise, volume), `antennas.py` (safe moves), `stream.py` (receiving), `stations.py` (station list), `control.py` (phone interface), `settings.py` / `settings.toml` |
| `tests/` | Python tests without hardware; a stand-in for the SDK in `tests/conftest.py` |
| `android/` | the Android app (Kotlin, one screen, no extra libraries) |
| `.github/workflows/release.yml` | tests on every push; on `main` also builds a release with the APK and the robot package |

## Development

```
uv run pytest          # Python tests, no robot needed
uv run ruff check .    # lint
cd android && ./gradlew testReleaseUnitTest assembleRelease   # Android tests and APK (needs the Android SDK)
```

Every push to `main` builds a new release; the links above always point to the newest one.

## License

[MIT](LICENSE) © Moe-Joe86
