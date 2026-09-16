#!/usr/bin/env python3
"""Two screen modes: split stage (round) and pixel overlay (sit watch)."""

from __future__ import annotations

import time

import cv2
import numpy as np

from gestures import Motion
from loop import ALERT, AWAY, CLEAR, MONITOR, PLAY, READY, ROUND, SUMMARY, DeskGame, mmss
from pixel_ui import (
    AZURE,
    CHAIR,
    CHAIR_PAL,
    CYAN,
    GRAY,
    LIME,
    NAVY,
    NIGHT,
    ORANGE,
    RED,
    SILVER,
    SLATE,
    SPINE_BAD,
    SPINE_OK,
    SPINE_PAL_BAD,
    SPINE_PAL_OK,
    WHITE,
    YELLOW,
    PixelScreen,
    pixel_head,
    pixel_line,
    pixel_ring,
)
from pose_tracker import PoseResult
from scenes import AV_SH_Y, AV_X, GROUND, STAGE_H, Stage, accent_of

STICK = (
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (0, 11),
    (0, 12),
    (11, 23),
    (12, 24),
    (23, 24),
)

# live strip in panel coords (320x180 grid over a 1280x720 frame)
STRIP_Y = STAGE_H + 1
STRIP_H = 42
CAM_X = 4
CAM_W = 74
CAM_H = STRIP_H
POS_X = CAM_X + CAM_W + 4
POS_W = 44
INFO_X = POS_X + POS_W + 4


def _dist(a, b) -> float:
    if a is None or b is None:
        return 0.0
    return float(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)


def _face_width(raw, sh_span: float) -> float:
    l_ear, r_ear = raw(7, 0.15), raw(8, 0.15)
    if l_ear and r_ear:
        w = abs(r_ear[0] - l_ear[0])
        if w > 20:
            return float(w)
    l_eye, r_eye = raw(3, 0.15), raw(6, 0.15)
    if l_eye and r_eye:
        w = abs(r_eye[0] - l_eye[0]) / 0.44
        if w > 20:
            return float(w)
    if sh_span > 40:
        return float(sh_span * 0.46)
    return 90.0


def draw_stick(img, pose: PoseResult, color=LIME) -> None:
    if not pose.ok:
        return

    def raw(i, min_vis: float = 0.28):
        if i >= len(pose.xy) or pose.vis[i] < min_vis:
            return None
        x, y = pose.xy[i]
        return (int(round(float(x))), int(round(float(y))))

    nose = raw(0)
    sh_l, sh_r = raw(11), raw(12)
    face = _face_width(raw, _dist(sh_l, sh_r))

    def pt(i):
        p = raw(i)
        if p is None:
            return None
        if nose is not None and i in (11, 12, 13, 14, 23, 24) and p[1] < nose[1] - int(face * 0.7):
            return None
        return p

    l_sh, r_sh = pt(11), pt(12)
    sh_span = _dist(l_sh, r_sh) if l_sh and r_sh else 0.0
    have_torso = bool(l_sh and r_sh and face * 1.1 < sh_span < face * 7.0)
    scale = sh_span * 1.15 if have_torso else face * 3.4

    if have_torso:
        for a, b in STICK:
            pa, pb = pt(a), pt(b)
            if pa is None or pb is None or _dist(pa, pb) > scale * 2.3:
                continue
            pixel_line(img, pa, pb, NIGHT, thick=2)
            pixel_line(img, pa, pb, color, thick=1)
        mid = ((l_sh[0] + r_sh[0]) // 2, (l_sh[1] + r_sh[1]) // 2)
        l_hip, r_hip = pt(23), pt(24)
        tail = None
        if l_hip and r_hip:
            hip = ((l_hip[0] + r_hip[0]) // 2, (l_hip[1] + r_hip[1]) // 2)
            if _dist(mid, hip) < scale * 2.0:
                tail = hip
        if tail is None:
            tail = (mid[0], mid[1] + int(scale * 0.85))
        pixel_line(img, mid, tail, NIGHT, thick=2)
        pixel_line(img, mid, tail, color, thick=1)
        for i in (11, 12, 13, 14, 15, 16):
            p = pt(i)
            if p:
                pixel_head(img, p, max(8, int(face * 0.12)), color)

    if nose is not None:
        r = max(20, int(0.62 * face))
        pixel_ring(img, nose, r + 8, NIGHT, thick=2)
        pixel_ring(img, nose, r, color, thick=2)


def draw_hands(img, hands, color=CYAN) -> None:
    if hands is None or not getattr(hands, "hands", None):
        return
    from hand_tracker import BONES

    for hand in hands.hands:
        for a, b in BONES:
            pa = (int(hand.xy[a][0]), int(hand.xy[a][1]))
            pb = (int(hand.xy[b][0]), int(hand.xy[b][1]))
            pixel_line(img, pa, pb, NIGHT, thick=2)
            pixel_line(img, pa, pb, color, thick=1)
        for t in (4, 8, 12, 16, 20):
            p = (int(hand.xy[t][0]), int(hand.xy[t][1]))
            pixel_head(img, p, 10, YELLOW)


def _hp_color(hp: int):
    if hp >= 55:
        return LIME
    if hp >= 25:
        return YELLOW
    return RED


def _posture_panel(scr: PixelScreen, posture: dict, x: int, y: int, w: int = 40, h: int = 74) -> None:
    score = float(posture.get("score", 100.0))
    tracked = bool(posture.get("tracked"))
    bad = bool(posture.get("bad"))
    accent = LIME if score >= 78 else (YELLOW if score >= 60 else RED)
    if not tracked:
        accent = SLATE
    scr.window(x, y, w, h, accent, NAVY, 255)
    scr.text(x + 5, y + 2, "坐姿", accent, 12)
    scr.pf(x + 5, y + 14, f"{int(score):03d}" if tracked else "---", WHITE, 2)
    label = posture.get("title") or ("挺直" if tracked else "等检测")
    if h >= 60:
        scr.seg_bar(x + 4, y + 30, w - 8, 5, score / 100.0 if tracked else 0.0, accent, seg=3)
        art = SPINE_BAD if bad else SPINE_OK
        pal = SPINE_PAL_BAD if bad else SPINE_PAL_OK
        scr.sprite(x + 6, y + 40, art, pal)
        scr.sprite(x + 20, y + 41, CHAIR, CHAIR_PAL)
        scr.text(x + 4, y + 54, label, WHITE if tracked else SILVER, 11)
    else:
        scr.seg_bar(x + 4, y + 26, w - 8, 5, score / 100.0 if tracked else 0.0, accent, seg=3)
        scr.text(x + 4, y + 32, label, WHITE if tracked else SILVER, 10)


def _bench(scr: PixelScreen, game: DeskGame, fps: float, pose_ms: float, npu: dict, y: int) -> None:
    scr.window(2, y, scr.lw - 4, 14, SLATE, NIGHT, 255)
    th = npu.get("thermal") or {}
    if npu.get("ok") and npu.get("ms"):
        npu_s = f"NPU {npu['ms']:.1f}MS {1000.0 / max(npu['ms'], 0.1):.0f}/S"
    elif npu.get("err"):
        npu_s = "NPU OFF"
    else:
        npu_s = "NPU .."
    parts = [f"FPS {fps:04.1f}", f"POSE {pose_ms:03.0f}MS", npu_s]
    if "nspss-0" in th:
        parts.append(f"NSP {th['nspss-0']:.0f}C")
    if "cpuss-0" in th:
        parts.append(f"CPU {th['cpuss-0']:.0f}C")
    scr.pf(6, y + 4, "  ".join(parts), CYAN, 1)
    right = f"SIT {int(game.sit_day // 60):03d}M  RUN {game.rounds:02d}  WIN {game.streak:02d}"
    scr.pf(scr.lw - 6 - scr.pf_width(right), y + 4, right, SILVER, 1)


def _center_card(scr: PixelScreen, title: str, sub: str, accent, y: int = 82, w: int = 196) -> None:
    x = (scr.lw - w) // 2
    scr.window(x, y, w, 46, accent, NIGHT, 255)
    scr.text(x + 10, y + 5, title, accent, 24)
    scr.text(x + 10, y + 30, sub, WHITE, 12)


def _toast(scr: PixelScreen, game: DeskGame, y: int = 36) -> None:
    if game.toast_t <= 0 or not game.toast:
        return
    w = 200
    x = (scr.lw - w) // 2
    scr.window(x, y, w, 18, CYAN, NIGHT, 255)
    scr.text(x + 8, y + 3, game.toast, CYAN, 13)


def ready_card(scr: PixelScreen, act: dict, idx: int, total: int, t: float) -> None:
    accent = accent_of(act["scene"])
    w, hgt = 220, 78
    x = (scr.lw - w) // 2
    y = 22
    scr.window(x, y, w, hgt, accent, NIGHT, 255)
    scr.pf(x + 8, y + 7, f"ACT {idx + 1}/{total}", accent, 1)
    scr.pf(x + w - 46, y + 7, act["en"], accent, 1)
    scr.text(x + 10, y + 20, act["name"], accent, 26)
    scr.text(x + 10, y + 46, act["tip"], WHITE, 11)
    scr.text(x + 10, y + 60, f"挑战：{act.get('goal', '')}", accent, 12)
    left = max(0.0, 2.0 - t)
    scr.pf(x + w - 24, y + hgt - 22, str(min(int(left) + 1, 3)), WHITE, 2)
    scr.bar(x + 8, y + hgt - 8, w - 38, 4, 1.0 - left / 2.0, accent)


def clear_card(scr: PixelScreen, result, t: float) -> None:
    accent = LIME if result.cleared else RED
    w, hgt = 176, 54
    x = (scr.lw - w) // 2
    y = 34
    scr.window(x, y, w, hgt, accent, NIGHT, 255)
    if result.cleared:
        scr.text(x + 10, y + 6, f"{result.act['name']} 过关", accent, 22)
        scr.pf(x + 10, y + 34, f"{result.grade}  +{result.points}  {result.seconds:.1f}S", WHITE, 1)
    else:
        scr.text(x + 10, y + 6, f"{result.act['name']} 没过", accent, 22)
        scr.pf(x + 10, y + 34, "TIME UP", WHITE, 1)
    scr.bar(x + 8, y + hgt - 7, w - 16, 3, min(1.0, t / 1.7), accent)


def summary_card(scr: PixelScreen, game: DeskGame, posture: dict) -> None:
    w, hgt = 300, 112
    x = (scr.lw - w) // 2
    y = 3
    scr.window(x, y, w, hgt, YELLOW, NIGHT, 255)
    scr.text(x + 8, y + 2, "本回合总结", YELLOW, 20)
    scr.pf(x + 92, y + 6, f"+{game.round_score:04d}", LIME, 1)
    scr.pf(x + 140, y + 6, f"CLEAR {game.done_n}/{len(game.acts)}", CYAN, 1)
    rows = game.results[:6]
    ry = y + 22
    step = 13 if len(rows) > 5 else 15
    for i, r in enumerate(rows):
        yy = ry + i * step
        col = LIME if r.cleared else RED
        scr.text(x + 8, yy, r.act["name"], WHITE, 11)
        scr.pf(x + 46, yy + 1, r.grade, col, 1)
        scr.pf(x + 58, yy + 1, f"{min(r.seconds, 99.9):04.1f}S", SILVER, 1)
        scr.seg_bar(x + 92, yy + 1, 40, 6, 1.0 if r.cleared else 0.0, col, seg=4)
        scr.pf(x + 136, yy + 1, f"+{r.points:03d}", WHITE if r.cleared else SLATE, 1)
    bx = x + 178
    scr.rect(bx - 6, y + 20, 1, hgt - 30, SLATE)
    scr.text(bx, y + 19, "坐姿评分", SILVER, 11)
    pg = posture.get("grade", "-")
    scr.pf(bx, y + 31, pg, LIME if pg in ("S", "A") else YELLOW, 2)
    scr.pf(bx + 18, y + 36, f"{posture.get('avg', 0):.0f} / 100", WHITE, 1)
    scr.seg_bar(bx, y + 50, 76, 6, float(posture.get("avg", 0)) / 100.0, LIME, seg=4)
    bad = int(float(posture.get("bad_total", 0)) // 60)
    scr.text(bx, y + 58, f"驼背累计 {bad} 分钟", SILVER, 11)
    scr.text(bx, y + 70, "今日", SILVER, 11)
    scr.pf(bx + 26, y + 72, f"SIT{int(game.sit_day // 60):03d}M  RUN{game.rounds:02d}", SILVER, 1)
    scr.pf(bx, y + 84, f"WIN{game.streak:02d}  BEST COMBO {game.best_combo:02d}", SILVER, 1)
    scr.text(x + 8, y + hgt - 14, "久坐已清零  举手直接回去干活", WHITE, 11)


def _wipe(scr: PixelScreen, trans: float) -> None:
    if trans <= 0:
        return
    k = min(1.0, trans / 0.55)
    bars = 9
    bh = scr.lh // bars + 1
    span = int(scr.lw * k)
    for i in range(bars):
        x = 0 if i % 2 == 0 else scr.lw - span
        scr.rect(x, i * bh, span, bh, NIGHT, 255)


def _live_strip(scr: PixelScreen, out, frame, game: DeskGame, posture: dict, fps, pose_ms, npu) -> None:
    """Bottom band: the real camera thumbnail plus the readouts."""
    h, w = out.shape[:2]
    s = scr.s
    cx0, cy0 = CAM_X * s, STRIP_Y * s
    cw, ch = CAM_W * s, CAM_H * s
    if cy0 + ch <= h and cx0 + cw <= w:
        out[cy0 : cy0 + ch, cx0 : cx0 + cw] = cv2.resize(frame, (cw, ch), interpolation=cv2.INTER_AREA)
    scr.frame(CAM_X - 1, STRIP_Y - 1, CAM_W + 2, CAM_H + 2, YELLOW, 1)
    scr.pf(CAM_X + 2, STRIP_Y + 2, "LIVE", LIME, 1)
    scr.pf(CAM_X + 2, STRIP_Y + CAM_H - 9, "POSE + HAND", CYAN, 1)

    _posture_panel(scr, posture, POS_X, STRIP_Y, POS_W, STRIP_H)

    iw = scr.lw - INFO_X - 4
    scr.window(INFO_X, STRIP_Y, iw, STRIP_H, accent_of(game.scene), NAVY, 255)
    left = game.round_left
    hot = left < 20
    scr.text(INFO_X + 5, STRIP_Y + 2, "回合倒计时", WHITE, 12)
    scr.pf(INFO_X + 58, STRIP_Y + 4, mmss(left), RED if hot else LIME, 2)
    scr.seg_bar(INFO_X + 5, STRIP_Y + 20, iw - 12, 7, left / 120.0, RED if hot else LIME, seg=5)
    scr.pips(INFO_X + 6, STRIP_Y + 32, len(game.acts), len(game.results), game.act_i)
    px = INFO_X + 10 + 6 * len(game.acts)
    scr.pf(px, STRIP_Y + 31, f"{game.score:05d}  COMBO {game.combo:02d}", CYAN, 1)
    _bench(scr, game, fps, pose_ms, npu, scr.lh - 15)


def draw_screen(
    img,
    game: DeskGame,
    stage: Stage,
    puppet,
    motion: Motion,
    pose: PoseResult,
    fps: float,
    pose_ms: float,
    npu: dict,
    posture: dict,
    hands=None,
):
    """Returns the frame to publish (may be a new canvas in split mode)."""
    h, w = img.shape[:2]
    blink = int(time.time() * 2) % 2 == 0

    if game.phase in (ROUND, SUMMARY):
        out = np.zeros_like(img)
        scr = PixelScreen(h, w)
        if game.phase == ROUND:
            stage.draw_bg(scr)
            ax = AV_X + int(stage.avatar_dx)
            ay = AV_SH_Y + int(stage.avatar_dy)
            puppet.face = "happy" if stage.done else ("tired" if getattr(stage, "falling", False) else "idle")
            if stage.scene == "piano":
                # sit behind the keyboard; shoulders just above the fallboard
                ay = GROUND - 52
                puppet.draw(scr, ax, ay, accent_of(game.scene), style="piano")
                stage.draw_piano_keys(scr)
                puppet.draw_piano_arms(scr, ax, ay, stage.piano_hand_targets(scr))
            else:
                puppet.draw(
                    scr,
                    ax,
                    ay,
                    accent_of(game.scene),
                    style=stage.scene,
                    nod=motion.nod,
                    turn_dir=motion.turn_dir,
                )
                if stage.scene == "eagle":
                    stage.draw_wings(scr, ax, ay)
            stage.draw_fg(scr)
            if game.sub == READY:
                ready_card(scr, game.act, game.act_i, len(game.acts), game.t_state)
            elif game.sub == CLEAR and game.results:
                clear_card(scr, game.results[-1], game.t_state)
            _toast(scr, game, STAGE_H - 22)
            # stage props (mountains/clouds) must not bleed into the LIVE strip
            scr.p[STAGE_H:, :, :] = 0
        else:
            # text is painted after the panel layer, so the stage must be skipped
            # entirely rather than covered up
            scr.rect(0, 0, scr.lw, STAGE_H, NIGHT, 255)
            summary_card(scr, game, posture)
            scr.p[STAGE_H:, :, :] = 0
        _live_strip(scr, out, img, game, posture, fps, pose_ms, npu)
        _wipe(scr, game.trans)
        scr.blit(out)
        return out

    # sit-watch modes: pixel chrome straight on the live picture
    scr = PixelScreen(h, w)
    hp = game.hp
    scr.window(2, 2, scr.lw - 4, 30, YELLOW if game.phase != ALERT else RED, NIGHT, 255)
    scr.text(7, 4, "工位回血", YELLOW, 20)
    scr.pf(50, 7, f"{game.score:05d}", WHITE, 2)
    scr.text(97, 6, game.title, SILVER, 12)
    if game.phase == AWAY:
        scr.text(7, 19, f"人不在工位  计时暂停  今日已坐{mmss(game.sit_day)}", SILVER, 12)
        scr.seg_bar(150, 6, 96, 8, 0.0, SLATE)
    elif game.phase == ALERT:
        scr.text(7, 19, f"已坐{mmss(game.sit_s)}  超时{mmss(game.overtime)}  该回血了", ORANGE, 12)
        scr.seg_bar(150, 6, 96, 8, hp / 100.0, RED)
        scr.pf(250, 7, f"HP{hp:03d}", RED, 1)
    else:
        if posture.get("bad"):
            scr.text(7, 19, f"已坐{mmss(game.sit_s)}  坐姿扣血中  约{mmss(game.remain)}", ORANGE, 12)
        else:
            scr.text(7, 19, f"已坐{mmss(game.sit_s)}  还有{mmss(game.remain)}回血", WHITE, 12)
        scr.seg_bar(150, 6, 96, 8, hp / 100.0, _hp_color(hp))
        scr.pf(250, 7, f"HP{hp:03d}", _hp_color(hp), 1)

    _posture_panel(scr, posture, scr.lw - 44, 44)

    if game.phase == ALERT:
        _center_card(
            scr,
            "该起来活动了" if blink else "已经坐很久了",
            "展翅 或 举手  开始 2 分钟挑战",
            RED if blink else ORANGE,
        )
    elif game.phase == AWAY:
        _center_card(scr, "坐回镜头前", "头、肩、手入画就开始计时", SILVER)
    elif not posture.get("tracked"):
        _center_card(scr, "再后靠一点", "肩膀和手也要进画面", WHITE, y=84, w=186)
    elif posture.get("nudge_hold", 0) > 0 and posture.get("advice"):
        _center_card(scr, posture.get("nudge") or "坐姿走形了", posture["advice"], ORANGE, y=84, w=206)

    _toast(scr, game)
    _bench(scr, game, fps, pose_ms, npu, scr.lh - 16)
    _wipe(scr, game.trans)
    scr.blit(img)
    return img
