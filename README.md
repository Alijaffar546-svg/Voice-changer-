# Voice Changer (Python + Kivy)

Files: `voice_engine.py` (voice engine), `main.py` (app + dashboard), `buildozer.spec` (APK settings), `build.yml` (automatic APK build on GitHub).

## Dashboard features
- Presets: Normal, Deep, Very deep, High, Child, Robot, Alien, Cave
- Custom pitch slider (-12 to +12 semitones), effects (Robot, Alien, Echo), volume
- Live level meter and Start/Stop

## Get the installable APK (no PC tools needed)
1. Create a free account at github.com and a new repository.
2. Upload `main.py`, `voice_engine.py`, `buildozer.spec`.
3. Upload `build.yml` with the full name `.github/workflows/build.yml`.
4. Open the **Actions** tab. The build starts automatically and takes about 15-25 minutes.
5. Open the finished run, download **VoiceChanger-APK**, unzip it, and install the APK on your phone (allow "Install unknown apps").

## Run on PC
```
pip install kivy numpy sounddevice
python main.py
```
For PC calls (Zoom, Discord, WhatsApp Desktop), install a virtual audio cable (Windows: VB-Cable) and run:
```
OUT_DEVICE="CABLE Input" python main.py
```
Then choose "CABLE Output" as the microphone in the calling app.

## Important limitation (calls on Android)
Without root, Android does not let an app inject audio into a normal phone call or a WhatsApp call.
On a phone, the app listens to the mic and plays the changed voice through the speaker or headset.
For live voice change on calls, the PC + virtual cable method above is the reliable way.
Use headphones to avoid echo.
