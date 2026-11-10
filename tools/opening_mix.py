"""Sound edit for the 22.5-second rooftop stretch. All timecodes are in seconds."""

import subprocess
import wave
from pathlib import Path

import numpy as np


RATE = 48_000
DURATION = 22.5
FOLEY = Path(__file__).resolve().parent / "opening_art"
GAME_AUDIO = Path(__file__).resolve().parents[1] / "examples/06_shadow_puppet/web/audio"


def _decode(encoder, path, filters=None):
    command = [str(encoder), "-v", "error", "-i", str(path)]
    if filters:
        command.extend(["-af", filters])
    command.extend(["-ar", str(RATE), "-ac", "2", "-f", "f32le", "pipe:1"])
    data = subprocess.run(command, check=True, stdout=subprocess.PIPE).stdout
    return np.frombuffer(data, dtype="<f4").reshape(-1, 2)


def _foley(name):
    with wave.open(str(FOLEY / f"opening-{name}.wav"), "rb") as track:
        if (track.getframerate(), track.getnchannels(), track.getsampwidth()) != (RATE, 1, 2):
            raise ValueError(f"Invalid foley format for {name}")
        pcm = np.frombuffer(track.readframes(track.getnframes()), dtype="<i2")
    return pcm.astype(np.float32)[:, None] / 32768


def mix_opening(encoder: str, soundtrack: Path, output: Path):
    """Write a stereo PCM WAV, locked to the picture edit in render_opening.py."""
    result = np.zeros((round(DURATION * RATE), 2), np.float32)
    warmup = _decode(encoder, soundtrack, "lowpass=f=1000")
    # The actual rooftop theme is 96 BPM. At 120 BPM a lamp lands every two beats
    # during the five-second hold, without changing the tune's pitch.
    rooftop = _decode(encoder, GAME_AUDIO / "wings.mp3", "atempo=1.25")
    invite = _decode(encoder, GAME_AUDIO / "start.mp3")
    count = _decode(encoder, GAME_AUDIO / "hit.mp3")
    clear = _decode(encoder, GAME_AUDIO / "reward.mp3")
    keys = _foley("typing")
    reminder = _foley("notice")
    inhale = _foley("inhale")
    exhale = _foley("exhale")

    def place(track, at, length=None, *, take=0, db=0, speed=1, pan=0, attack=.002, release=.022):
        """Cut one source onto the stereo timeline with short click-free edges."""
        first = round(at * RATE)
        available = (len(track) / RATE - take) / speed
        count = min(round(min(available, length if length is not None else available) * RATE),
                    len(result) - first)
        if count <= 0:
            return
        start = round(take * RATE)
        if speed == 1:
            clip = track[start:start+count].copy()
        else:
            times = start + np.arange(count) * speed
            samples = np.arange(len(track))
            clip = np.stack([np.interp(times, samples, channel) for channel in track.T], axis=1)
        count = len(clip)
        for seconds, leading in ((attack, True), (release, False)):
            n = min(count, round(seconds * RATE))
            if n:
                ramp = .5 - .5 * np.cos(np.linspace(0, np.pi, n))
                if leading:
                    clip[:n] *= ramp[:, None]
                else:
                    clip[-n:] *= ramp[::-1, None]
        # Preserve the centre level; desk props move only slightly across stereo.
        balance = np.sqrt([1 - pan, 1 + pan])
        result[first:first+count] += clip * balance * 10**(db/20)

    # The same desktop alert interrupts him twice. At first he keeps typing.
    place(keys, 0, .95, take=.054, db=6.5, pan=-.16, release=.024)
    place(reminder, 1.00, db=-2.2, pan=.18)
    place(keys, 1.16, 1.31, take=1.35, db=5.4, pan=-.16, release=.060)
    place(keys, 2.54, .15, take=1.648, speed=.90, db=-1.0, pan=-.16)
    # Let the slumped posture register before he catches his breath.
    place(inhale, 4.10, .60, db=-2.0, pan=-.09, attack=.018, release=.080)

    # The CRT wakes; the soft desk tap and the robot's invitation are separate.
    place(count[::-1], 5.25, .23, take=.105, db=-4.0, pan=.21, release=.025)
    place(keys, 6.15, .085, take=3.048, speed=.80, db=-5.8, pan=.16)
    place(invite, 6.30, .62, take=.045, db=-4.0, pan=.17, release=.085)
    place(warmup, 7.50, 3.36, take=6.05, db=-7.8, attack=.17, release=.22)
    place(count, 8.75, .11, take=.020, speed=.92, db=-9.4, pan=.12)
    place(count, 9.55, .11, take=.020, speed=.92, db=-9.4, pan=-.08)

    # Arms are level at 11.00. Each full second earns one light, including the
    # fifth. Leave a little room for its tick before the game's success sound.
    place(rooftop, 11.00, 5.00, take=.004, db=-7.4, attack=.09, release=.11)
    for second in range(1, 6):
        place(count, 11.00 + second, .14, take=.012, db=-4.7, release=.038)
    place(clear, 16.12, .60, db=-2.0, release=.15)

    # Hear his shoulders settle. A quiet resolving phrase accompanies the smile,
    # then leaves room for the identical reminder and his decision to rest.
    place(exhale, 17.15, db=-.8, pan=-.09, attack=.024, release=.09)
    place(warmup, 18.04, .80, take=20.04, db=-10.3, attack=.07, release=.24)
    place(reminder, 19.35, db=-2.2, pan=.18)
    place(keys, 21.20, .094, take=3.048, db=-4.7, pan=-.15, attack=.0008)
    place(warmup, 21.31, 1.16, take=22.05, db=-8.0, attack=.075, release=.45)

    # Preserve the cue frames when limiting the narrow keyboard transients.
    command = [str(encoder), "-v", "error", "-y", "-f", "f32le", "-ar", str(RATE),
               "-ac", "2", "-i", "pipe:0", "-af",
               "volume=3.3dB,alimiter=limit=0.84:attack=3:release=45:level=0:latency=1,volume=-2.2dB",
               "-c:a", "pcm_s16le", str(output)]
    subprocess.run(command, input=result.astype("<f4").tobytes(), check=True)
