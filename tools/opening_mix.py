"""Sound edit for the rooftop stretch, scorecard and return to the arcade."""

import subprocess
import wave
from pathlib import Path

import numpy as np


RATE = 48_000
DURATION = 54.5
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


def _relay_motif(encoder, name, original_bpm, start, semitones=0):
    """Cut on a downbeat and fit this cartridge's melody to the relay's 120 BPM."""
    pitch = 2 ** (semitones / 12)
    filters = (
        f"atrim=start={start}:duration=10,aresample={RATE},"
        f"asetrate={round(RATE * pitch)},aresample={RATE},"
        f"atempo={120 / (original_bpm * pitch):.6f},highpass=f=125"
    )
    return _decode(encoder, GAME_AUDIO / f"{name}.mp3", filters)


def _piano_note(frequency):
    """Match the triangle oscillator and key envelope of the playable piano."""
    t = np.arange(round(.23 * RATE)) / RATE
    triangle = (2 / np.pi) * np.arcsin(np.sin(2 * np.pi * frequency * t))
    envelope = np.exp(np.interp(t, [0,.008,.22,.23], np.log([.001,.22,.001,.0001])))
    return (triangle * envelope).astype(np.float32)[:, None]


def mix_opening(encoder: str, soundtrack: Path, output: Path):
    """Write a stereo PCM WAV, locked to the picture edit in render_opening.py."""
    result = np.zeros((round(DURATION * RATE), 2), np.float32)
    warmup = _decode(encoder, soundtrack, "lowpass=f=1000")
    mission = _decode(encoder, soundtrack)
    # A quiet kick from the original opening theme ties all cartridge voices
    # together. Gate the sub-bass tail between beats to leave the melodies room.
    pulse = _decode(encoder, soundtrack, "highpass=f=48,lowpass=f=175")
    beat_phase = (np.arange(len(pulse)) / RATE - .055) % .5
    pulse = pulse * (.14 + .86 * np.exp(-19 * beat_phase)).astype(np.float32)[:, None]
    # The actual rooftop theme is 96 BPM. At 120 BPM a lamp lands every two beats
    # during the five-second hold, without changing the tune's pitch.
    rooftop = _decode(encoder, GAME_AUDIO / "wings.mp3", "atempo=1.25")
    lobby_track = GAME_AUDIO / "lobby.mp3"
    lobby = _decode(encoder, lobby_track)
    lobby_soft = _decode(encoder, lobby_track, "lowpass=f=1350")
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

    # Show the map, then let the robot's feet land on the actual desk.
    place(mission, 5.25, 1.50, take=8.052, db=-6.2, attack=.035, release=.23)
    place(count[::-1], 6.75, .23, take=.105, db=-4.0, pan=.21, release=.025)
    place(keys, 7.65, .085, take=3.048, speed=.80, db=-5.8, pan=.16)
    place(invite, 7.80, .62, take=.045, db=-4.0, pan=.17, release=.085)
    place(warmup, 8.75, 3.59, take=6.05, db=-7.8, attack=.17, release=.22)
    place(keys, 10.92, .092, take=3.048, db=-4.5, pan=-.12)
    place(count, 11.20, .11, take=.020, speed=.92, db=-9.4, pan=.12)

    # Once the arms are level, every *completed* second earns a lamp.
    place(rooftop, 12.50, 5.47, take=.004, db=-7.4, attack=.09, release=.26)
    for second in range(1, 6):
        place(count, 12.50 + second, .14, take=.012, db=-4.7, release=.038)
    place(clear, 17.62, .43, db=-3.5, release=.14)

    # Each checkpoint lasts seven beats. Open its own original melody over the
    # preceding one for half a beat, while the same low drum continues beneath.
    place(pulse, 17.50, 25.03, take=.052, db=-9, attack=.12, release=.24)
    # (cartridge, native BPM, musical downbeat in its source, transposition, dB)
    scenes = [
        ("flap", 132, 2.937, 0, -5.5),
        ("wave", 112, 3.205, 0, -5.2),
        ("lean", 145, 3.925, -2, -5.5),       # D minor into C minor
        ("piano", 92, 2.927, 2, -8.7),        # A minor behind the live C-major keys
        ("hands_up", 136, 1.534, 0, -5.5),
        ("turn", 104, 7.214, 0, -6.0),
        ("nod", 120, 3.997, 0, -5.6),
    ]
    for index, (name, bpm, downbeat, shift, level) in enumerate(scenes):
        at = 18 + index * 3.5
        motif = _relay_motif(encoder, name, bpm, downbeat, shift)
        place(motif, at, 3.75, db=level, attack=.25, release=.25)

    # Spot only the actions that tell the next part of the story. The piano's
    # four actual playable notes are exposed over its softer accompaniment.
    place(count, 20.30, .12, take=.016, speed=1.12, db=-7.7, pan=.10)
    place(invite, 24.00, .32, take=.06, speed=1.34, db=-7, pan=.25)
    place(count, 27.50, .13, take=.018, db=-7, pan=-.20)
    for at, frequency in zip((29.10,29.65,30.20,30.75), (261.63,329.63,392.,523.25)):
        place(_piano_note(frequency), at, db=3, attack=0, release=.008)
    place(count[::-1], 33.15, .17, take=.13, db=-5, pan=-.09)
    place(keys, 34.40, .14, take=3.045, speed=.78, db=-2.5, pan=-.08)
    place(_piano_note(392.), 36.32, db=-2.8, pan=-.44)
    place(_piano_note(523.25), 37.56, db=-2.8, pan=.44)
    place(keys, 42.23, .11, take=3.047, db=-3)
    place(mission, 42.50, 1.86, take=8.05, db=-6.4, attack=.07, release=.35)
    place(clear, 42.50, .86, db=-3.2, release=.18)

    # Hear his shoulders settle. A quiet resolving phrase accompanies the smile,
    # then leaves room for the identical reminder and his decision to rest.
    place(exhale, 45.08, db=-.8, pan=-.09, attack=.024, release=.09)
    place(warmup, 45.93, .72, take=20.04, db=-10.3, attack=.07, release=.24)
    place(reminder, 46.85, db=-2.2, pan=.18)
    place(keys, 48.70, .094, take=3.048, db=-4.7, pan=-.15, attack=.0008)

    # The scorecard and arcade share one uninterrupted lobby phrase, with one
    # quiet click for the invite, ending at the track's actual loop boundary.
    report_at, lobby_at = 49.35, 52.10
    lobby_source = len(lobby) / RATE - (DURATION - lobby_at)
    report_source = lobby_source - (lobby_at - report_at)
    blend = .38
    place(lobby_soft, report_at, lobby_at - report_at + blend, take=report_source,
          db=-12.0, attack=.21, release=blend)
    place(keys, 51.25, .12, take=.20, speed=1.14, db=-2, pan=.08, release=.027)
    place(lobby, lobby_at, DURATION - lobby_at, take=lobby_source,
          db=-10.2, attack=blend, release=.15)

    # Preserve the cue frames when limiting the narrow keyboard transients.
    command = [str(encoder), "-v", "error", "-y", "-f", "f32le", "-ar", str(RATE),
               "-ac", "2", "-i", "pipe:0", "-af",
               "volume=3.3dB,alimiter=limit=0.84:attack=3:release=45:level=0:latency=1,volume=-2.2dB",
               "-c:a", "pcm_s16le", str(output)]
    subprocess.run(command, input=result.astype("<f4").tobytes(), check=True)
