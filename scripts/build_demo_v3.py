"""GuardX Final Demo V3 builder — Real SenseNova AI.

Story (final seconds):
   0-7    cinematic intro (built)
   7-19   command center        (rec 0-12)
  19-37   vision / YOLO         (rec 12-30)
  37-55   security event        (rec 30-48)
  55-69   RAG / policies        (rec 48-62)
  69-85   LangGraph workflow    (rec 62-78)
  85-103  HERO: real SenseNova analysis (built from the REAL API response)
 103-117  persistence           (rec 78-92)
 117-131  reprocess             (rec 92-106)
 131-139  n8n / health          (rec 106-114)
 139-147  hero slow zoom        (rec 114-122)
 147-155  credits (built)

The HERO scene renders the GENUINE SenseNova report (severity, summary,
reasoning, citations, incident id) saved at /tmp/guardx_v3_incident.json.
Nothing is invented: every value on screen comes from the real response.

Output: demo/GuardX-Final-Demo-V3.mp4
Clean take: demo/GuardX-Clean-Recording-V3.mp4
"""
import json
import os
import subprocess
import sys
import textwrap

FRAMES = "/tmp/guardx_frames_v3"
EVENTS_LOG = "/tmp/guardx_v3_events.jsonl"
TMP = "/tmp/guardx_v3_build"
OUTDIR = os.path.expanduser("~/workspace/guardx/demo")
FINAL = os.path.join(OUTDIR, "GuardX-Final-Demo-V3.mp4")
CLEAN = os.path.join(OUTDIR, "GuardX-Clean-Recording-V3.mp4")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
TTS = "/opt/hatch/bin/tts"
VOICE = "avocado_v2:MAI_03"

INTRO_DUR = 7.0
HERO_DUR = 18.0
CREDITS_DUR = 8.0
REC_OFFSET = 7.0

# real report (never fabricated)
INFO = json.load(open("/tmp/guardx_v3_incident.json"))
REP = INFO["report"]
REAL_SEVERITY = REP["severity"]
REAL_SUMMARY = REP["summary"]
REAL_REASONING = REP["reasoning"]
REAL_CITATIONS = REP["cited_policy_chunk_ids"]
REAL_ACTION = REP["recommended_action"]
REAL_IID = INFO["incident_id"][:8]

# find a real zone_enter during the recording for the incident moment.
# Event timestamps are script-relative; recording_start marks rec t=0.
INCIDENT_T = REC_OFFSET + 21.8  # fallback
try:
    with open(EVENTS_LOG) as f:
        evs = [json.loads(line) for line in f]
    rec0 = next(e["t"] for e in evs if e.get("kind") == "recording_start")
    for e in evs:
        rel = e["t"] - rec0
        if e.get("kind") == "zone_enter" and 12 <= rel <= 30:
            INCIDENT_T = REC_OFFSET + rel
            print(f"real zone_enter at rec t={rel:.2f}s -> final {INCIDENT_T:.1f}s")
            break
except (FileNotFoundError, StopIteration):
    print("events log / recording_start not found; using fallback incident time")

# (final_start, final_end, hud_text, narration)
BEATS = [
    (0.0, 7.0, None,
     "Security threats strike in seconds. GuardX detects, understands, and responds to incidents in real time."),
    (7.0, 19.0, "SECURITY COMMAND CENTER",
     "GuardX unifies computer vision, retrieval-augmented generation, workflow orchestration, and live monitoring into a single security platform."),
    (19.0, 37.0, "VISION ENGINE \u00b7 YOLO DETECTION \u00b7 TRACKING ACTIVE",
     "YOLO detects every person in the camera feed, and tracking maintains identity across frames. The restricted server-room zone is armed and watching."),
    (37.0, 55.0, "SECURITY EVENT \u00b7 ZONE ENTER",
     "The moment a person enters the restricted zone, the zone engine generates a security event \u2014 with camera, zone, track identity, and confidence."),
    (55.0, 69.0, "RAG POLICY RETRIEVAL \u00b7 LANGCHAIN",
     "GuardX never asks the AI to decide blindly. It first retrieves the relevant security policy from the organization\u2019s knowledge base, using retrieval-augmented generation."),
    (69.0, 85.0, "LANGGRAPH WORKFLOW",
     "LangGraph orchestrates the incident workflow: the event is validated, policy is retrieved, AI analysis runs, and the decision is validated before anything is stored."),
    (85.0, 103.0, "REAL AI ANALYSIS \u00b7 SENSENOVA",
     "Now the incident is analyzed by SenseNova, using the retrieved security policy as context. The model returns a structured decision with severity, policy-grounded reasoning, and supporting citations. This is a genuine response from the SenseNova API."),
    (103.0, 117.0, "PERSISTENCE \u00b7 POSTGRESQL",
     "The validated incident and its AI report are persisted in PostgreSQL \u2014 the system\u2019s source of truth for investigation and audit."),
    (117.0, 131.0, "REPROCESS \u00b7 NO DUPLICATES",
     "Existing incidents can be reprocessed through the workflow in place. The analysis refreshes without creating a duplicate record."),
    (131.0, 139.0, "N8N AUTOMATION \u00b7 OPTIONAL \u00b7 DISABLED",
     "An optional n8n layer can forward incidents to external systems. It is disabled here, and GuardX reports that honestly."),
    (139.0, 147.0, "GUARDX \u00b7 REAL-TIME DETECTION \u00b7 POLICY-GROUNDED AI",
     "GuardX. Real-time detection, policy-grounded AI, complete evidence."),
    (147.0, 155.0, None,
     "GuardX was developed by the three of us. Kifayat Irfan. Abdur Razak. Abdur Rehman."),
]

# (dip boundaries now handled by per-segment fades before concat)


def run(cmd, **kw):
    print("+", " ".join(cmd[0:3]), "...", flush=True)
    subprocess.run(cmd, check=True, **kw)


def ffprobe_dur(path):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", path], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def tts(text, out):
    run([TTS, "speak", "--voice", VOICE, "--output", out, "--text", text],
        capture_output=subprocess.DEVNULL)


def render_hero_card(path):
    """Render the REAL SenseNova response as a 1920x1080 analysis card."""
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "#04070c")
    d = ImageDraw.Draw(img)
    # subtle grid
    for x in range(0, W, 120):
        d.line([(x, 0), (x, H)], fill="#0b1622", width=1)
    for y in range(0, H, 120):
        d.line([(0, y), (W, y)], fill="#0b1622", width=1)

    f_title = ImageFont.truetype(FONT_B, 64)
    f_sub = ImageFont.truetype(FONT, 30)
    f_sec = ImageFont.truetype(FONT_B, 30)
    f_body = ImageFont.truetype(FONT, 26)
    f_small = ImageFont.truetype(FONT, 22)

    y = 70
    d.text((96, y), "AI ANALYSIS", font=f_title, fill="#22d3ee"); y += 84
    d.text((96, y), "SENSENOVA  \u00b7  sensenova-6.8-flash-lite",
           font=f_sub, fill="#94a3b8"); y += 44
    d.text((96, y), "\u25cf REAL API RESPONSE \u2014 NOT A MOCKUP",
           font=f_sub, fill="#4ade80"); y += 70

    # severity (real)
    sev_color = {"HIGH": "#f87171", "MEDIUM": "#fbbf24",
                 "LOW": "#4ade80"}.get(REAL_SEVERITY, "#e2e8f0")
    d.text((96, y), "SEVERITY", font=f_sec, fill="#64748b")
    d.text((330, y - 8), REAL_SEVERITY, font=ImageFont.truetype(FONT_B, 44),
           fill=sev_color); y += 76

    # summary (real, wrapped)
    d.text((96, y), "SUMMARY", font=f_sec, fill="#64748b"); y += 44
    for line in textwrap.wrap(REAL_SUMMARY, width=88)[:3]:
        d.text((96, y), line, font=f_body, fill="#e2e8f0"); y += 38
    y += 18

    # citations (real)
    d.text((96, y), "POLICY CITATIONS", font=f_sec, fill="#64748b"); y += 44
    for cid in REAL_CITATIONS:
        d.text((96, y), "\u25b8 " + cid, font=f_body, fill="#7dd3fc"); y += 38
    y += 18

    # reasoning excerpt (real, wrapped, truncated to fit)
    d.text((96, y), "POLICY-GROUNDED REASONING", font=f_sec, fill="#64748b"); y += 44
    lines = []
    for para in REAL_REASONING.split("\n"):
        lines += textwrap.wrap(para, width=88)
    for line in lines[:5]:
        d.text((96, y), line, font=f_body, fill="#cbd5e1"); y += 36
    if len(lines) > 5:
        d.text((96, y), "[\u2026]", font=f_body, fill="#64748b"); y += 36

    d.text((96, H - 80), f"incident {REAL_IID} \u00b7 GuardX incident pipeline",
           font=f_small, fill="#475569")
    img.save(path)
    print(f"  hero card rendered (real severity={REAL_SEVERITY}, "
          f"{len(REAL_CITATIONS)} citations)")


def main() -> int:
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(OUTDIR, exist_ok=True)

    # ---------- 1. narration ----------
    segs = []
    for i, (s, e, _hud, nar) in enumerate(BEATS):
        out = f"{TMP}/vo_{i:02d}.mp3"
        tts(nar, out)
        dur = ffprobe_dur(out)
        slot = e - s
        tag = "OK " if dur <= slot * 0.97 else "OVER"
        print(f"  vo {i:02d}: {dur:.1f}s / {slot:.1f}s  [{tag}]", flush=True)
        segs.append((out, s, dur))

    # ---------- 2. base assembly ----------
    base = f"{TMP}/v3_base.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-framerate", "6",
         "-i", f"{FRAMES}/frame_%05d.jpg",
         "-vf", "scale=1920:1080,fps=30",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", base])
    rec_dur = ffprobe_dur(base)
    print(f"  base: {rec_dur:.1f}s", flush=True)
    run(["cp", base, CLEAN])
    print(f"  clean take preserved: {CLEAN}", flush=True)

    def cut(name, ss, t):
        out = f"{TMP}/{name}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-i", base,
             "-ss", str(ss), "-t", str(t),
             "-vf", f"fade=t=in:st=0:d=0.35,fade=t=out:st={t - 0.35:.2f}:d=0.35",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-pix_fmt", "yuv420p", out])
        return out

    body1 = cut("body1", 0, 78)      # rec 0-78  -> final 7-85
    body2 = cut("body2", 78, 14)     # rec 78-92 -> final 103-117
    body3 = cut("body3", 92, 14)     # rec 92-106 -> final 117-131
    body4 = cut("body4", 106, 8)     # rec 106-114 -> final 131-139
    hero = cut("hero", 114, 8)       # rec 114-122 -> final 139-147

    hero_z = f"{TMP}/hero_zoom.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", hero,
         "-vf", "zoompan=z='min(1+0.0013*in\\,1.32)':"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                "d=1:s=1920x1080:fps=30,"
                "fade=t=in:st=0:d=0.35,fade=t=out:st=7.65:d=0.35",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", hero_z])

    # ---------- 3. intro card ----------
    intro = f"{TMP}/intro.mp4"
    i1, i2, i3 = f"{TMP}/i1.txt", f"{TMP}/i2.txt", f"{TMP}/i3.txt"
    open(i1, "w").write("GUARDX")
    open(i2, "w").write("AI AUTONOMOUS SECURITY AGENT")
    open(i3, "w").write("REAL-TIME DETECTION \u00b7 REAL AI ANALYSIS")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"color=c=#04070c:s=1920x1080:d={INTRO_DUR}:r=30",
         "-vf",
         f"drawgrid=w=120:h=120:t=1:c=#0e2233@0.35,"
         f"drawtext=fontfile={FONT}:textfile={i1}:fontsize=110:fontcolor=#22d3ee:"
         f"x=(w-text_w)/2:y=(h-text_h)/2-70:"
         f"alpha='if(lt(t,0.4),0,if(lt(t,1.6),(t-0.4)/1.2,1))',"
         f"drawtext=fontfile={FONT}:textfile={i2}:fontsize=34:fontcolor=#cbd5e1:"
         f"x=(w-text_w)/2:y=(h-text_h)/2+60:"
         f"alpha='if(lt(t,1.8),0,if(lt(t,3.0),(t-1.8)/1.2,1))',"
         f"drawtext=fontfile={FONT}:textfile={i3}:fontsize=28:fontcolor=#4ade80:"
         f"x=(w-text_w)/2:y=(h-text_h)/2+120:"
         f"alpha='if(lt(t,3.2),0,if(lt(t,4.4),(t-3.2)/1.2,1))',"
         f"fade=t=in:st=0:d=0.5,fade=t=out:st=6.0:d=1.0",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", intro])

    # ---------- 4. HERO SenseNova scene (built from the REAL response) ----------
    hero_png = f"{TMP}/hero_card.png"
    render_hero_card(hero_png)
    hero_vid = f"{TMP}/hero_ai.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", hero_png,
         "-vf", "zoompan=z='min(1+0.0006*in\\,1.05)':"
                "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={int(HERO_DUR * 30)}:s=1920x1080:fps=30,"
                f"fade=t=in:st=0:d=0.6,fade=t=out:st={HERO_DUR - 0.8:.1f}:d=0.8",
         "-t", str(HERO_DUR),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", hero_vid])

    # ---------- 5. credits card ----------
    credits = f"{TMP}/credits.mp4"
    c1, c2, c3, c4 = (f"{TMP}/c1.txt", f"{TMP}/c2.txt",
                      f"{TMP}/c3.txt", f"{TMP}/c4.txt")
    open(c1, "w").write("GUARDX")
    open(c2, "w").write("AI Autonomous Security Agent for Real-Time Incident Detection and Response")
    open(c3, "w").write("Developed by\n\nKifayat Irfan\nAbdur Razzaq\nAbdur Rehman")
    open(c4, "w").write("Built by the three of us.")
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", f"color=c=#04070c:s=1920x1080:d={CREDITS_DUR}:r=30",
         "-vf",
         f"drawgrid=w=120:h=120:t=1:c=#0e2233@0.35,"
         f"drawtext=fontfile={FONT}:textfile={c1}:fontsize=96:fontcolor=#22d3ee:"
         f"x=(w-text_w)/2:y=300:"
         f"alpha='if(lt(t,0.3),0,if(lt(t,1.3),(t-0.3),1))',"
         f"drawtext=fontfile={FONT}:textfile={c2}:fontsize=28:fontcolor=#94a3b8:"
         f"x=(w-text_w)/2:y=430:"
         f"alpha='if(lt(t,1.0),0,if(lt(t,2.0),(t-1.0),1))',"
         f"drawtext=fontfile={FONT}:textfile={c3}:fontsize=40:fontcolor=#e2e8f0:"
         f"x=(w-text_w)/2:y=520:line_spacing=20:"
         f"alpha='if(lt(t,1.8),0,if(lt(t,3.0),(t-1.8)/1.2,1))',"
         f"drawtext=fontfile={FONT}:textfile={c4}:fontsize=30:fontcolor=#22d3ee:"
         f"x=(w-text_w)/2:y=880:"
         f"alpha='if(lt(t,3.4),0,if(lt(t,4.4),(t-3.4),1))',"
         f"fade=t=out:st={CREDITS_DUR - 1.0:.1f}:d=1.0",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", credits])

    # ---------- 6. concat ----------
    with open(f"{TMP}/vcat.txt", "w") as f:
        for p in (intro, body1, hero_vid, body2, body3, body4, hero_z, credits):
            f.write(f"file '{p}'\n")
    vcat = f"{TMP}/vcat.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
         "-i", f"{TMP}/vcat.txt", "-c", "copy", vcat])
    total = ffprobe_dur(vcat)
    print(f"  concat: {total:.1f}s", flush=True)

    # ---------- 7. HUD + incident moment (no global fade chain) ----------
    # Dip-to-black transitions are applied per-segment before concat
    # (many chained fade filters black out the video in this ffmpeg build).
    filt = []
    for i, (s, e, hud, _n) in enumerate(BEATS):
        if not hud or i == 0 or i == len(BEATS) - 1:
            continue
        tf = f"{TMP}/hud_{i:02d}.txt"
        open(tf, "w").write(hud)
        show = min(4.2, (e - s) - 0.6)
        filt.append(
            f"drawtext=fontfile={FONT}:textfile={tf}:fontsize=22:"
            f"fontcolor=#7dd3fc:borderw=1:bordercolor=black:"
            f"x=72:y=h-110:box=1:boxcolor=#04070c@0.72:boxborderw=12:"
            f"alpha='if(lt(t,{s + 0.6:.2f}),0,if(lt(t,{s + 1.4:.2f}),"
            f"(t-{s + 0.6:.2f})/0.8,1))':"
            f"enable='between(t\\,{s + 0.6:.2f}\\,{s + 0.6 + show:.2f})'"
        )
    m1, m2 = f"{TMP}/m1.txt", f"{TMP}/m2.txt"
    open(m1, "w").write("SECURITY EVENT DETECTED")
    open(m2, "w").write("RESTRICTED ZONE ENTRY")
    ms, me = INCIDENT_T - 0.5, INCIDENT_T + 2.5
    filt.append(
        f"drawbox=x=(w-620)/2:y=440:w=620:h=120:c=#04070c@0.80:t=fill:"
        f"enable='between(t\\,{ms:.2f}\\,{me:.2f})',"
        f"drawbox=x=(w-620)/2:y=440:w=6:h=120:c=#f87171:t=fill:"
        f"enable='between(t\\,{ms:.2f}\\,{me:.2f})',"
        f"drawtext=fontfile={FONT}:textfile={m1}:fontsize=38:fontcolor=#fca5a5:"
        f"x=(w-text_w)/2:y=462:enable='between(t\\,{ms:.2f}\\,{me:.2f})',"
        f"drawtext=fontfile={FONT}:textfile={m2}:fontsize=24:fontcolor=#e2e8f0:"
        f"x=(w-text_w)/2:y=514:enable='between(t\\,{ms:.2f}\\,{me:.2f})'"
    )
    vhud = f"{TMP}/vhud.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", vcat,
         "-vf", ",".join(filt),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", vhud])

    # ---------- 8. audio ----------
    inputs, fca = [], []
    for i, (a, s, _d) in enumerate(segs):
        inputs += ["-i", a]
        fca.append(f"[{i}:a]aresample=44100,adelay={int(s * 1000)}|"
                   f"{int(s * 1000)},apad[va{i}]")
    n = len(segs)
    inputs += ["-f", "lavfi", "-i", f"anoisesrc=color=brown:duration={total}:seed=7"]
    fca.append(f"[{n}:a]aresample=44100,lowpass=f=400,volume=0.045[amb]")
    inputs += ["-f", "lavfi", "-i", f"sine=frequency=55:duration={INTRO_DUR}"]
    fca.append(f"[{n + 1}:a]aresample=44100,volume=0.05,"
               f"afade=t=out:st=5.5:d=1.5[drone]")
    inputs += ["-f", "lavfi", "-i", "sine=frequency=740:duration=0.14",
               "-f", "lavfi", "-i", "sine=frequency=1108:duration=0.22"]
    fca.append(
        f"[{n + 2}:a]aresample=44100,volume=0.22,afade=t=out:st=0.08:d=0.06[b1];"
        f"[{n + 3}:a]aresample=44100,volume=0.18,"
        f"adelay=140|140,afade=t=out:st=0.30:d=0.06[b2];"
        f"[b1][b2]amix=inputs=2:normalize=0,"
        f"adelay={int(INCIDENT_T * 1000)}|{int(INCIDENT_T * 1000)},apad[blip]")
    mix = "".join(f"[va{i}]" for i in range(n)) + "[amb][drone][blip]"
    fca.append(f"{mix}amix=inputs={n + 3}:normalize=0,"
               f"volume=1.0,loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    mixed = f"{TMP}/mixed.m4a"
    run(["ffmpeg", "-y", "-v", "error"] + inputs +
        ["-filter_complex", ";".join(fca), "-map", "[aout]",
         "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.2f}", mixed])

    # ---------- 9. mux ----------
    run(["ffmpeg", "-y", "-v", "error", "-i", vhud, "-i", mixed,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
         "-movflags", "+faststart", "-shortest", FINAL])
    dur = ffprobe_dur(FINAL)
    sz = os.path.getsize(FINAL)
    print(f"FINAL: {FINAL}  {dur:.1f}s  {sz / 1e6:.1f} MB", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
