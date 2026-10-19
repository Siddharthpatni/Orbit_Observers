"""Render intro.html to media/orbit_observers_intro.mp4 (deterministic: one screenshot per frame, then ffmpeg).

Usage (from the repo root, with playwright and a Chromium available):
  python media/intro/render.py            # all 300 frames + audio + mux
Set CHROMIUM=/path/to/chrome-headless-shell if Playwright's own browser is not installed.
"""
import json, os, subprocess, tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "orbit_observers_intro.mp4"
work = Path(tempfile.mkdtemp(prefix="oo_intro_"))
with sync_playwright() as p:
    kw = {"executable_path": os.environ["CHROMIUM"]} if os.environ.get("CHROMIUM") else {}
    b = p.chromium.launch(**kw); pg = b.new_page(viewport={"width": 1920, "height": 1080})
    pg.goto((HERE / "intro.html").as_uri()); pg.wait_for_function("window.READY===true")
    json.dump(pg.evaluate("window.HIT_T"), open(work / "hit.json", "w"))
    for i in range(300):
        pg.evaluate(f"setT({i/30})"); pg.screenshot(path=str(work / f"f{i:04d}.png"))
    b.close()
subprocess.run(["python", str(HERE / "make_audio.py"), str(work / "hit.json"), str(work / "a.wav")], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "30", "-i", str(work / "f%04d.png"), "-i", str(work / "a.wav"),
                "-af", "loudnorm=I=-16:TP=-1.5:LRA=7", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", "-preset", "slow",
                "-c:a", "aac", "-b:a", "192k", "-t", "10", "-movflags", "+faststart", str(OUT)], check=True)
print("wrote", OUT)
