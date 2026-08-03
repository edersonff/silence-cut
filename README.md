# silence-cut

Takes the dead air out of a recording. Point it at a video or an audio file and it writes the same
thing back with the gaps gone, keeping a breath on each side so the cuts do not sound clipped.

Written for the middle of a pipeline: it prints one line, or nothing at all with `--json`.

## Input

A media path as the first argument, and where to write it as the second.

## Output

The same media without its silences, at the path you passed second. Nothing else is touched: same
codec choice as ffmpeg would pick, video and audio stay in step.

## Run it

    tools/silence_cut.py talk.mp4 tight.mp4

    6.0s in, 4.1s out, 1.9s of silence gone in one cut
    tight.mp4

## What it needs

ffmpeg and ffprobe on PATH. Python 3.9 or newer. Nothing to install.

## Settings, and what they default to

    --quiet-below -30     dB under which sound counts as silence
    --longer-than 0.6     seconds a silence must last before it is worth cutting
    --leave 0.05          seconds of silence left on each side of a cut
    --json                answer as json, for a program reading this

The defaults are for speech recorded at a normal level. Music and room tone need `--quiet-below`
lower, around -45, or it will cut inside the sound.

## What breaks

Measured on ffmpeg 8.0, not guessed:

- File that is not there, exit 1.
- File ffmpeg cannot read, exit 1, says so instead of guessing.
- Video with no audio track, exit 1. There is no silence to find without sound.
- Recording that is silent end to end, exit 1, and nothing is written. Cutting it would leave zero.
- Recording with no silence longer than the threshold, **exit 2** and no output file. That is a
  separate code on purpose: nothing was wrong, there was simply nothing to cut, and a script that
  loops over a folder wants to tell those two apart.
- Very long files are re-encoded, not stream-copied, because the cut lands mid-frame. An hour of
  1080p takes minutes, not seconds.
