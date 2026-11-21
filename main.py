"""Voice Changer - Kivy app with dashboard (Android + desktop).

Android: mic -> voice change -> speaker/headset via AudioRecord/AudioTrack.
Desktop: uses `sounddevice`. Set OUT_DEVICE to a virtual cable name/index
(e.g. "CABLE Input") to use the changed voice in Zoom/Discord/WhatsApp Desktop.
"""
import math
import os
import threading

import numpy as np
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.progressbar import ProgressBar
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.utils import platform

from voice_engine import BLOCK, EFFECTS, PRESETS, SAMPLE_RATE, VoiceChanger


class AndroidAudio:
    def __init__(self):
        from jnius import autoclass

        AudioRecord = autoclass("android.media.AudioRecord")
        AudioTrack = autoclass("android.media.AudioTrack")
        AudioFormat = autoclass("android.media.AudioFormat")
        AudioManager = autoclass("android.media.AudioManager")
        Source = autoclass("android.media.MediaRecorder$AudioSource")
        Array = autoclass("java.lang.reflect.Array")
        Short = autoclass("java.lang.Short")

        enc = AudioFormat.ENCODING_PCM_16BIT
        min_in = AudioRecord.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, enc)
        min_out = AudioTrack.getMinBufferSize(
            SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, enc)
        self.rec = AudioRecord(Source.VOICE_COMMUNICATION, SAMPLE_RATE,
                               AudioFormat.CHANNEL_IN_MONO, enc,
                               max(min_in, BLOCK * 4))
        self.track = AudioTrack(AudioManager.STREAM_MUSIC, SAMPLE_RATE,
                                AudioFormat.CHANNEL_OUT_MONO, enc,
                                max(min_out, BLOCK * 4),
                                AudioTrack.MODE_STREAM)
        self.buf = Array.newInstance(Short.TYPE, BLOCK)

    def start(self):
        self.rec.startRecording()
        self.track.play()

    def read(self):
        n = self.rec.read(self.buf, 0, BLOCK)
        if n <= 0:
            return None
        return np.array(list(self.buf), dtype=np.int16)[:n]

    def write(self, pcm):
        self.track.write(pcm.tolist(), 0, len(pcm))

    def stop(self):
        self.rec.stop()
        self.track.stop()
        self.rec.release()
        self.track.release()


class DesktopAudio:
    def __init__(self):
        import sounddevice as sd

        out = os.environ.get("OUT_DEVICE")
        if out is not None and out.isdigit():
            out = int(out)
        self.inp = sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                                  dtype="int16", blocksize=BLOCK)
        self.out = sd.OutputStream(samplerate=SAMPLE_RATE, channels=1,
                                   dtype="int16", blocksize=BLOCK, device=out)

    def start(self):
        self.inp.start()
        self.out.start()

    def read(self):
        data, _ = self.inp.read(BLOCK)
        return data[:, 0].copy()

    def write(self, pcm):
        self.out.write(pcm.reshape(-1, 1))

    def stop(self):
        self.inp.stop()
        self.out.stop()
        self.inp.close()
        self.out.close()


def semitones(ratio):
    return 12 * math.log2(ratio)


class VoiceApp(App):
    title = "Voice Changer"

    def build(self):
        self.vc = VoiceChanger("Deep")
        self.running = False
        root = BoxLayout(orientation="vertical", padding=20, spacing=10)

        root.add_widget(Label(text="Voice Changer Dashboard",
                              font_size="24sp", size_hint_y=None, height=60))

        self.status = Label(text="Status: stopped", size_hint_y=None, height=40)
        root.add_widget(self.status)

        root.add_widget(Label(text="Input level", size_hint_y=None, height=28))
        self.meter = ProgressBar(max=1.0, value=0.0, size_hint_y=None, height=24)
        root.add_widget(self.meter)

        root.add_widget(Label(text="Preset", size_hint_y=None, height=28))
        self.preset = Spinner(text="Deep", values=list(PRESETS),
                              size_hint_y=None, height=80)
        self.preset.bind(text=self.on_preset)
        root.add_widget(self.preset)

        self.pitch_label = Label(size_hint_y=None, height=28)
        root.add_widget(self.pitch_label)
        self.pitch = Slider(min=0.5, max=2.0, value=0.75,
                            size_hint_y=None, height=60)
        self.pitch.bind(value=self.on_pitch)
        root.add_widget(self.pitch)

        root.add_widget(Label(text="Effect", size_hint_y=None, height=28))
        self.fx = Spinner(text="None", values=EFFECTS,
                          size_hint_y=None, height=80)
        self.fx.bind(text=lambda _, v: self.vc.set_fx(v))
        root.add_widget(self.fx)

        self.gain_label = Label(size_hint_y=None, height=28)
        root.add_widget(self.gain_label)
        self.gain = Slider(min=0.5, max=3.0, value=1.0,
                           size_hint_y=None, height=60)
        self.gain.bind(value=self.on_gain)
        root.add_widget(self.gain)

        self.btn = Button(text="START", font_size="22sp")
        self.btn.bind(on_release=self.toggle)
        root.add_widget(self.btn)

        root.add_widget(Label(text="Use headphones to avoid echo/feedback.",
                              font_size="13sp", size_hint_y=None, height=30))

        self.on_preset(None, "Deep")
        self.on_gain(None, 1.0)
        Clock.schedule_interval(self.refresh, 0.1)
        return root

    # ---- UI callbacks ----
    def on_preset(self, _, name):
        self.vc.set_preset(name)
        ratio, fx = PRESETS[name]
        self.pitch.value = ratio
        self.fx.text = fx

    def on_pitch(self, _, value):
        self.vc.set_ratio(value)
        self.pitch_label.text = "Pitch: %+.1f semitones (x%.2f)" % (
            semitones(value), value)

    def on_gain(self, _, value):
        self.vc.gain = value
        self.gain_label.text = "Volume: x%.1f" % value

    def refresh(self, _dt):
        self.meter.value = min(1.0, self.vc.level * 4) if self.running else 0.0
        if not self.running and self.btn.text == "STOP":
            self.btn.text = "START"

    def on_start(self):
        if platform == "android":
            from android.permissions import Permission, request_permissions
            request_permissions([Permission.RECORD_AUDIO])

    def toggle(self, *_):
        if self.running:
            self.running = False
            self.btn.text = "START"
            self.status.text = "Status: stopped"
            return
        self.running = True
        self.btn.text = "STOP"
        self.status.text = "Status: running"
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        try:
            audio = AndroidAudio() if platform == "android" else DesktopAudio()
            audio.start()
            while self.running:
                pcm = audio.read()
                if pcm is None:
                    continue
                audio.write(self.vc.process(pcm))
            audio.stop()
        except Exception as e:  # show errors in UI instead of crashing
            self.running = False
            msg = "Status: error - " + str(e)
            Clock.schedule_once(lambda dt: setattr(self.status, "text", msg))


if __name__ == "__main__":
    VoiceApp().run()
