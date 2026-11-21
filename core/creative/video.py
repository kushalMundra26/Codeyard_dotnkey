"""Storyboard → MP4 (free): composed frames + Ken Burns zoompan + crossfades + burned-in subtitles + Sarvam voiceover.
Higgsfield hero clip (paid, button-only): finished 9:16 static ad → Kling 2.5 Turbo image-to-video → VO + end card."""
from __future__ import annotations

import io
import subprocess
import wave
from pathlib import Path

import numpy as np
import requests

from ..providers import higgsfield, sarvam
from .compose import render_ad, render_frame

XF = 0.4  # crossfade seconds
FPS = 30


def ffmpeg_exe() -> str:
    import shutil
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run(args: list[str]) -> None:
    p = subprocess.run([ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr[-800:]}")


def wav_info(data: bytes) -> tuple[np.ndarray, int]:
    with wave.open(io.BytesIO(data)) as w:
        sr = w.getframerate()
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() == 2:
            a = a.reshape(-1, 2).mean(axis=1).astype(np.int16)
    return a, sr


def write_wav(path: Path, a: np.ndarray, sr: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(a.astype(np.int16).tobytes())


def render_storyboard_video(product: dict, script: dict, palette: list[str], out_dir: Path, lang: str = "en",
                            texts: dict | None = None, W: int = 720, H: int = 1280, speaker: str = "priya",
                            progress=None, engine_pref: list[str] | None = None) -> dict:
    """texts: optional {'on_screen': [...], 'voiceover': [...]} translated lines for regional versions."""
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = script["frames"]
    n = len(frames)
    on_screen = (texts or {}).get("on_screen") or [f["on_screen_text"] for f in frames]
    vo = (texts or {}).get("voiceover") or [f["voiceover"] for f in frames]
    planned = [max(1.8, float(f["t_end"]) - float(f["t_start"])) for f in frames]

    # 1) voiceover per frame (Sarvam Bulbul v3) → durations
    audio_segments, vo_engine = [], "none"
    sr = 24000
    if sarvam.available():
        try:
            for i, line in enumerate(vo):
                a, sr = wav_info(sarvam.tts(line, lang=lang, speaker=speaker))
                audio_segments.append(a)
                if progress:
                    progress(f"voiceover {i + 1}/{n}")
            vo_engine = "sarvam bulbul:v3"
        except Exception as e:
            audio_segments, vo_engine = [], f"none ({str(e)[:80]})"
    durs = []
    for i in range(n):
        d = planned[i]
        if audio_segments:
            d = max(d, len(audio_segments[i]) / sr + 0.5)
        durs.append(round(d + (XF if i < n - 1 else 0), 2))

    # 2) frames
    engines = []
    paths = []
    for i, f in enumerate(frames):
        fr = dict(f, on_screen_text=on_screen[i], cta="Shop now")
        r = render_frame(product, fr, palette, W, H, out_dir / f"frame_{lang}_{i}.jpg", i, n, lang=lang,
                         subtitle=vo[i], show_product=(i in (1, 2, n - 1)),
                         engine_pref=engine_pref or ["cloudflare", "template"])
        paths.append(r["path"])
        engines.append(r["engine"])
        if progress:
            progress(f"frame {i + 1}/{n}")

    # 3) audio timeline aligned to crossfade offsets
    offsets = [0.0]
    for i in range(1, n):
        offsets.append(offsets[-1] + durs[i - 1] - XF)
    total = offsets[-1] + durs[-1]
    audio_path = out_dir / f"vo_{lang}.wav"
    timeline = np.zeros(int(total * sr) + sr, dtype=np.int32)
    for i, a in enumerate(audio_segments):
        st = int((offsets[i] + 0.25) * sr)
        timeline[st:st + len(a)] += a[: max(0, len(timeline) - st)]
    write_wav(audio_path, np.clip(timeline, -32768, 32767), sr)

    # 4) Ken Burns + crossfades rendered in numpy, piped to ffmpeg as raw frames (zoompan is far slower)
    from PIL import Image
    stills = [Image.open(p).convert("RGB") for p in paths]
    out = out_dir / f"storyboard_{lang}_{W}x{H}.mp4"
    n_total = int(round(total * FPS))
    proc = subprocess.Popen([ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(audio_path), "-c:v", "libx264",
                             "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
                             "-shortest", "-movflags", "+faststart", str(out)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    def kb(i: int, t: float) -> np.ndarray:
        """Frame i at local time t: alternate slow zoom-in / zoom-out (max 8%) with a slight drift."""
        im = stills[i]
        prog = min(1.0, max(0.0, t / durs[i]))
        z = 1.0 + 0.08 * (prog if i % 2 == 0 else 1 - prog)
        cw, chh = W / z, H / z
        dx = (W - cw) * (0.5 + (0.15 if i % 3 == 0 else -0.15) * (prog - 0.5))
        dy = (H - chh) * 0.5
        return np.asarray(im.resize((W, H), Image.BILINEAR, box=(dx, dy, dx + cw, dy + chh)))

    try:
        for k in range(n_total):
            t = k / FPS
            i = max(j for j in range(n) if offsets[j] <= t + 1e-9)
            fr = kb(i, t - offsets[i]).astype(np.float32)
            if i + 1 < n and t >= offsets[i + 1] - 1e-9:
                pass
            # crossfade window: the next clip starts at offsets[i+1]; we are already in clip i+1 there,
            # so blend the PREVIOUS clip's tail when inside [offsets[i], offsets[i] + XF)
            if i > 0 and t < offsets[i] + XF:
                a = (t - offsets[i]) / XF
                prev = kb(i - 1, t - offsets[i - 1]).astype(np.float32)
                fr = prev * (1 - a) + fr * a
            proc.stdin.write(fr.astype(np.uint8).tobytes())
        proc.stdin.close()
        err = proc.stderr.read().decode()
        if proc.wait() != 0:
            raise RuntimeError(f"ffmpeg failed: {err[-600:]}")
    finally:
        if proc.poll() is None:
            proc.kill()
    return {"path": str(out), "duration": round(total, 1), "voiceover": vo_engine, "frame_engines": engines,
            "frames": paths, "lang": lang}


def hero_clip(product: dict, variant: dict, palette: list[str], out_dir: Path, vo_text: str, lang: str = "en",
              duration: int = 5, speaker: str = "priya") -> dict:
    """Paid: animate the finished 9:16 static ad with Higgsfield Kling 2.5 Turbo, then add VO + end card."""
    out_dir.mkdir(parents=True, exist_ok=True)
    still = render_ad(product, variant, "story", palette, out_dir / "hero_still.jpg", lang=lang)
    img_url = higgsfield.upload(Path(still["path"]).read_bytes(), "image/jpeg")
    prompt = ("Subtle cinematic motion: gentle camera push-in, soft light shimmer across the scene, fruit and water "
              "droplets move slightly, the product and all text stay perfectly still and legible.")
    vurl = higgsfield.image_to_video(img_url, prompt, duration=duration)
    raw = out_dir / "hero_raw.mp4"
    raw.write_bytes(requests.get(vurl, timeout=300).content)
    # VO + 1.5 s end card (the still) appended
    card = out_dir / "hero_card.mp4"
    _run(["-loop", "1", "-t", "1.5", "-i", still["path"], "-vf", "scale=1080:1920,format=yuv420p", "-r", "30",
          "-c:v", "libx264", str(card)])
    parts = [raw, card]
    lst = out_dir / "hero_list.txt"
    norm = []
    for i, p in enumerate(parts):
        q = out_dir / f"hero_norm_{i}.mp4"
        _run(["-i", str(p), "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
              "-an", "-c:v", "libx264", "-preset", "veryfast", str(q)])
        norm.append(q)
    lst.write_text("".join(f"file '{p.name}'\n" for p in norm))
    joined = out_dir / "hero_joined.mp4"
    _run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(joined)])
    out = out_dir / f"hero_{lang}.mp4"
    if sarvam.available():
        a, sr = wav_info(sarvam.tts(vo_text, lang=lang, speaker=speaker))
        wp = out_dir / "hero_vo.wav"
        write_wav(wp, a, sr)
        _run(["-i", str(joined), "-i", str(wp), "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)])
    else:
        joined.rename(out)
    return {"path": str(out), "source_video_url": vurl, "still": still["path"], "est_usd": higgsfield.estimate_i2v(duration)}
