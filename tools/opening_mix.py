"""Sound edit for the 22.5-second keyboard rescue. All timecodes are in seconds."""

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
    theme = _decode(encoder, soundtrack)
    bass = _decode(encoder, soundtrack, "lowpass=f=420")
    build = _decode(encoder, GAME_AUDIO / "start.mp3")
    pickup = _decode(encoder, GAME_AUDIO / "hit.mp3")
    win = _decode(encoder, GAME_AUDIO / "reward.mp3")
    keys = _foley("typing")
    cap = _foley("keycap")
    ping = _foley("notice")
    slap = _foley("slap")
    breath_in = _foley("inhale")
    breath_out = _foley("exhale")

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

    # Typing becomes the opening rhythm. The wide pauses vanish as the cuts speed up;
    # the deep spacebar and the short game jingle land on BUILD OK.
    for at, take, length, speed in [(0,.053,.40,1), (.55,.46,.27,1.04),
                                    (.91,.78,.19,1.10), (1.19,1.36,.15,1.14),
                                    (1.40,2.33,.125,1.22), (1.59,2.92,.135,1.28)]:
        place(keys, at, length, take=take, speed=speed, db=2.0, pan=-.18, attack=.0007, release=.008)
    place(bass, .54, 1.17, take=2.05, db=-10, attack=.025, release=.02)
    place(keys, 1.74, .10, take=3.048, speed=.9, pan=-.12)
    place(build, 1.78, .61, take=.045, db=-3, release=.055)
    # The developer folds onto the desk, then the room is completely still.
    place(slap, 2.92, speed=.59, db=-5, pan=-.15, release=.055)
    place(keys, 2.96, .10, take=.64, speed=.78, db=-6, pan=-.14)

    # Use exactly the same notification on both "1 BUG" frames: the listener
    # recognises the second interruption before the developer answers it.
    place(ping, 4.00, db=-2.5, pan=.19)
    place(breath_in, 4.22, .54, db=-3, pan=-.10, attack=.022, release=.10)
    place(bass, 4.25, .54, take=12.04, speed=.58, db=-14, release=.11)
    place(pickup[::-1], 5.15, .22, take=.10, db=-3, pan=.30, release=.014)
    place(cap, 5.90, speed=.76, db=-4, pan=.20)
    place(keys, 6.17, .102, take=.201, db=1, pan=.16, release=.012)
    place(keys, 6.50, .095, take=1.651, speed=1.08, db=0, pan=.12, release=.014)
    # Drop everything before the stolen key pops out. The quiet second tick is
    # the same plastic part bouncing, a sound that will return at the end.
    place(cap, 7.23, db=.5, pan=.09, attack=.0004)
    place(cap, 7.335, speed=1.52, db=-10, pan=.20, attack=.0005)
    place(pickup, 7.75, .14, speed=1.13, db=-5, pan=-.12)
    place(bass, 8.44, 1.19, take=6.055, db=-6.5, attack=.02, release=.035)

    # On the road the full theme finally arrives. Its half-second pulse carries
    # the car into the desert; leave the catch and landing room of their own.
    place(theme, 9.65, 2.99, take=8.045, db=-5.7, attack=.012, release=.035)
    place(cap, 11.62, speed=1.34, db=.2, pan=.3, attack=.0005)
    place(theme, 12.65, 1.78, take=16.045, db=-5.6, attack=.010, release=.065)
    place(slap, 14.47, .12, speed=.84, db=-6, pan=-.15)
    place(cap, 15.05, speed=1.13, db=.2, pan=.03, attack=.0006)
    place(slap, 15.61, .18, speed=.72, db=-7, pan=-.08)
    place(breath_out, 15.77, .62, db=-2.7, pan=-.09, attack=.026, release=.08)
    place(cap, 16.45, speed=.83, db=-1.2, pan=-.1, attack=.0005)
    place(bass, 16.51, .81, take=20.045, db=-9, attack=.022, release=.18)

    place(ping, 17.86, db=-2.5, pan=.19)
    place(keys, 18.32, .14, take=.135, speed=.78, db=-6, pan=-.12)
    place(cap, 19.17, speed=1.42, db=-5.5, pan=.28)
    # Hold on the offer of a palm in silence. The high-five and "BRB" are two
    # different beats, followed by the backwards click of the original keycap.
    place(slap, 20.58, db=-.2, attack=.0005, release=.041)
    place(win, 20.82, .48, take=.22, db=-3.1, speed=1.13, release=.125)
    place(cap[::-1], 21.45, speed=.86, db=-1.0, pan=-.13, attack=.012, release=.002)
    place(cap, 21.67, speed=1.34, db=-8.5, pan=-.13, attack=.0005)

    # Keep the quiet breath audible on a laptop. Limit only the tallest plastic
    # transients, compensating the lookahead so the slap stays on its video frame.
    command = [str(encoder), "-v", "error", "-y", "-f", "f32le", "-ar", str(RATE),
               "-ac", "2", "-i", "pipe:0", "-af",
               "volume=3.3dB,alimiter=limit=0.84:attack=3:release=45:level=0:latency=1,volume=-2.2dB",
               "-c:a", "pcm_s16le", str(output)]
    subprocess.run(command, input=result.astype("<f4").tobytes(), check=True)
