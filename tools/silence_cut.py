#!/usr/bin/env python3
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SILENCE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
SILENCE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


def die(what, fix, machine, code=1):
    if machine:
        print(json.dumps({"state": "refused", "what": what, "fix": fix}, indent=2))
    else:
        print(f"\n  {what}\n    {fix}\n", file=sys.stderr)
    raise SystemExit(code)


def run(command):
    return subprocess.run(command, capture_output=True, text=True)


def duration_of(path):
    seen = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=nw=1:nk=1", str(path)])
    try:
        return float(seen.stdout.strip())
    except ValueError:
        return None


def silences(path, floor, shortest):
    seen = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path),
                "-af", f"silencedetect=noise={floor}dB:d={shortest}", "-f", "null", "-"])
    found, opened = [], None
    for line in seen.stderr.splitlines():
        start = SILENCE_START.search(line)
        end = SILENCE_END.search(line)
        if start:
            opened = float(start.group(1))
        elif end and opened is not None:
            found.append((opened, float(end.group(1))))
            opened = None
    return found


def keeps(quiet, total, pad):
    spoken, at = [], 0.0
    for start, end in quiet:
        start, end = start + pad, end - pad
        if start > at:
            spoken.append((at, start))
        at = max(at, end)
    if at < total:
        spoken.append((at, total))
    return [(a, b) for a, b in spoken if b - a > 0.05]


def cut(source, target, spoken, has_sound, has_video=True):
    return run(cut_command(source, target, spoken, has_sound, has_video))


def cut_command(source, target, spoken, has_sound, has_video):
    pieces = "".join(
        (f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS[v{i}];" if has_video else "") +
        (f"[0:a]atrim={a}:{b},asetpts=PTS-STARTPTS[a{i}];" if has_sound else "")
        for i, (a, b) in enumerate(spoken)
    )
    joins = "".join(
        (f"[v{i}]" if has_video else "") + (f"[a{i}]" if has_sound else "")
        for i in range(len(spoken))
    )
    v = 1 if has_video else 0
    a = 1 if has_sound else 0
    graph = f"{pieces}{joins}concat=n={len(spoken)}:v={v}:a={a}"
    if v:
        graph += "[v]"
    if a:
        graph += "[a]"
    command = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
               "-filter_complex", graph]
    if v:
        command += ["-map", "[v]"]
    if a:
        command += ["-map", "[a]"]
    return command + [str(target)]


def main():
    asked = argparse.ArgumentParser(
        prog="silence-cut",
        description="Cuts the silence out of a video and writes what is left.")
    asked.add_argument("source", help="the file to cut")
    asked.add_argument("target", help="where to write it")
    asked.add_argument("--quiet-below", type=float, default=-30.0,
                       help="dB under which sound counts as silence (default -30)")
    asked.add_argument("--longer-than", type=float, default=0.6,
                       help="seconds a silence must last to be cut (default 0.6)")
    asked.add_argument("--leave", type=float, default=0.05,
                       help="seconds of silence to leave on each side (default 0.05)")
    asked.add_argument("--json", action="store_true", help="answer as json")
    said = asked.parse_args()

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        die("ffmpeg is not on this machine", "install ffmpeg, silence-cut is a thin layer over it", said.json)

    source = Path(said.source)
    if not source.is_file():
        die(f"there is no file at {source}", "check the path and run it again", said.json)

    total = duration_of(source)
    if total is None:
        die(f"{source} is not something ffmpeg can read", "point it at a video or an audio file", said.json)

    has_sound = bool(run(["ffprobe", "-v", "error", "-select_streams", "a",
                          "-show_entries", "stream=index", "-of", "csv=p=0", str(source)]).stdout.strip())
    has_video = bool(run(["ffprobe", "-v", "error", "-select_streams", "v",
                          "-show_entries", "stream=index", "-of", "csv=p=0", str(source)]).stdout.strip())
    if not has_sound:
        die(f"{source} has no audio track", "there is no silence to find without sound", said.json)

    quiet = silences(source, said.quiet_below, said.longer_than)
    spoken = keeps(quiet, total, said.leave)
    if not spoken:
        die(f"{source} is silent from end to end", "nothing would be left, so nothing was written", said.json)
    if not quiet:
        die(f"{source} has no silence longer than {said.longer_than}s", "raise --longer-than or --quiet-below", said.json, code=2)

    wrote = cut(source, Path(said.target), spoken, has_sound, has_video)
    if wrote.returncode != 0:
        die(f"{said.target} could not be written", wrote.stderr.strip().splitlines()[-1] if wrote.stderr.strip() else "ffmpeg said nothing", said.json)

    kept = sum(b - a for a, b in spoken)
    answer = {"state": "cut", "from": round(total, 2), "to": round(kept, 2),
              "removed": round(total - kept, 2), "cuts": len(quiet), "target": said.target}
    if said.json:
        print(json.dumps(answer, indent=2))
    else:
        cuts = "one cut" if len(quiet) == 1 else f"{len(quiet)} cuts"
        print(f"\n  {total:.1f}s in, {kept:.1f}s out, {total - kept:.1f}s of silence gone in {cuts}")
        print(f"  {said.target}\n")


if __name__ == "__main__":
    main()
