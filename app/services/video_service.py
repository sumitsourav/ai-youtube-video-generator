import os
import subprocess
import tempfile

from app.config import VIDEO_NAME

WIDTH = 720
HEIGHT = 1280
FPS = 24
FADE_SECONDS = 1

# Documentary pacing is a cut every few seconds. The old render divided the
# audio evenly across whatever clips were fetched, which left a single shot on
# screen for 30-45 seconds and read as a slideshow. The cap keeps a 5-minute
# video from turning into 75 ffmpeg inputs - past ~40 the filter graph costs
# more to build than the extra cuts are worth.
MIN_SHOT_SECONDS = 4.0
MAX_SHOTS = 40

# Push-in applied to archival stills, per output frame. Slow on purpose: the
# point is to keep a photograph from reading as a frozen frame, not to draw
# attention to the move.
KEN_BURNS_SPEED = 0.0006
KEN_BURNS_MAX_ZOOM = 1.18

# One grade over every clip. Stock footage is pulled from unrelated shoots -
# a floodlit pitch next to desaturated archive next to a bright forest - and
# without a shared curve the cuts read as a folder of downloads rather than
# one piece. Deliberately subtle: cool the shadows, warm the highlights, pull
# saturation back slightly.
COLOR_GRADE = (
    "eq=contrast=1.07:saturation=0.93,"
    "colorbalance=rs=-0.02:bs=0.04:rh=0.03:bh=-0.02"
)

# A bed under narration, not competing with it. -20dB before the mix's own
# amplitude halving puts the music well beneath the voice without vanishing
# in quiet passages.
MUSIC_VOLUME_DB = -20

# CRF 30 + slow preset cuts output size by ~66% vs libx264's untuned defaults
# (CRF 23, medium preset), measured on a 20s 720x1280 test clip (2.58MB vs
# 7.53MB). Quality cost is small but real: SSIM 0.963 vs a near-lossless
# (CRF 18) reference, vs 0.986 for the CRF 23 default - a difference that
# doesn't read as visible in motion video at this resolution, not a zero-loss
# swap. Matters directly for B2 cost: smaller files mean less storage and,
# more importantly, less egress per view against B2's free-tier download cap.
VIDEO_CRF = "30"
VIDEO_PRESET = "slow"
AUDIO_BITRATE = "96k"
MAX_CAPTION_CHARS = 18
CAPTION_STYLE = (
    "FontName=DejaVu Sans,Bold=1,FontSize=24,PrimaryColour=&H00FFFFFF,"
    "OutlineColour=&H00000000,BorderStyle=1,Outline=3,Shadow=0,"
    "Alignment=2,MarginV=100"
)

# Lines ffmpeg's `-progress` output uses for its own periodic stats - not
# useful as error diagnostics, so they're filtered out of the buffer kept
# for the failure message.
_PROGRESS_FIELD_PREFIXES = (
    "frame=", "fps=", "stream_", "bitrate=", "total_size=",
    "out_time_us=", "out_time_ms=", "out_time=", "dup_frames=",
    "drop_frames=", "speed=", "progress=",
)


def _probe_duration(path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def _format_srt_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    whole = int(seconds)
    hours, remainder = divmod(whole, 3600)
    minutes, secs = divmod(remainder, 60)
    millis = int(round((seconds - whole) * 1000))
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _chunk_script(script_text: str, max_chars: int = MAX_CAPTION_CHARS):
    """Groups words into short caption-sized chunks rather than full
    sentences - matches the punchy, few-words-at-a-time captions typical of
    short-form video, and keeps each chunk narrow enough to read at a glance."""
    words = script_text.split()
    chunks = []
    current, current_len = [], 0
    for word in words:
        added_len = len(word) + (1 if current else 0)
        if current and current_len + added_len > max_chars:
            chunks.append(" ".join(current))
            current, current_len = [], 0
            added_len = len(word)
        current.append(word)
        current_len += added_len
    if current:
        chunks.append(" ".join(current))
    return chunks


def _detect_pause_points(audio_path: str) -> list:
    """Midpoint of each detected silence gap in the narration audio - real
    acoustic pauses the TTS engine inserted, mostly at punctuation. Used to
    correct caption timing, which would otherwise drift since spoken pace
    isn't purely proportional to character count."""
    result = subprocess.run(
        ["ffmpeg", "-i", audio_path, "-af", "silencedetect=noise=-30dB:d=0.2", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    starts, ends = [], []
    for line in result.stderr.splitlines():
        if "silence_start:" in line:
            starts.append(float(line.rsplit(":", 1)[1].strip()))
        elif "silence_end:" in line:
            ends.append(float(line.split("silence_end:")[1].split("|")[0].strip()))
    return sorted((s + e) / 2 for s, e in zip(starts, ends))


def _snap_to_pauses(boundaries, pause_points, tolerance=0.8, min_gap=0.3):
    """Moves each proportionally-estimated boundary onto a real detected
    pause when one exists close by, while keeping boundaries strictly
    increasing so chunks can't collapse onto the same pause point."""
    snapped = []
    prev_end = 0.0
    next_pause_idx = 0
    for boundary in boundaries:
        while next_pause_idx < len(pause_points) and pause_points[next_pause_idx] < prev_end + min_gap:
            next_pause_idx += 1

        candidate = boundary
        if next_pause_idx < len(pause_points):
            pause = pause_points[next_pause_idx]
            if abs(pause - boundary) <= tolerance and pause > prev_end + min_gap:
                candidate = pause
                next_pause_idx += 1

        candidate = max(candidate, prev_end + min_gap)
        snapped.append(candidate)
        prev_end = candidate
    return snapped


def _chunk_word_timings(word_timings, max_chars=MAX_CAPTION_CHARS):
    """Same grouping rule as _chunk_script, but over timed words instead of
    plain text, so each resulting chunk keeps the exact start time Polly
    reported for its first word."""
    chunks = []
    current, current_len = [], 0
    for timing in word_timings:
        added_len = len(timing["word"]) + (1 if current else 0)
        if current and current_len + added_len > max_chars:
            chunks.append(current)
            current, current_len = [], 0
            added_len = len(timing["word"])
        current.append(timing)
        current_len += added_len
    if current:
        chunks.append(current)
    return chunks


def _build_srt_from_word_timings(word_timings: list, duration: float) -> str:
    """Captions timed to the millisecond, from the same word marks Polly used
    to speak them - not an estimate corrected after the fact. A caption
    changes at the instant its first word is actually spoken, which is what
    makes word-by-word captions read as "popping" rather than drifting."""
    chunks = _chunk_word_timings(word_timings)
    lines = []
    for i, chunk in enumerate(chunks):
        text = " ".join(timing["word"] for timing in chunk)
        start = chunk[0]["start"]
        end = chunks[i + 1][0]["start"] if i + 1 < len(chunks) else duration
        end = max(end, start + 0.1)
        lines.append(f"{i + 1}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{text}\n")
    return "\n".join(lines)


def _build_srt(script_text: str, duration: float, pause_points=None, word_timings=None) -> str:
    if word_timings:
        return _build_srt_from_word_timings(word_timings, duration)

    # Fallback for engines that don't report word timing (gtts, pyttsx3,
    # elevenlabs): estimate each caption's share of the audio from its share
    # of the script's characters, then correct the estimate against real
    # acoustic pauses detected in the audio.
    chunks = _chunk_script(script_text)
    total_chars = sum(len(c) for c in chunks) or 1

    ends = []
    t = 0.0
    for chunk in chunks:
        t += len(chunk) / total_chars * duration
        ends.append(min(duration, t))

    if pause_points:
        ends = _snap_to_pauses(ends[:-1], pause_points) + ends[-1:]

    lines = []
    start = 0.0
    for i, (chunk, end) in enumerate(zip(chunks, ends), start=1):
        end = max(end, start + 0.1)
        lines.append(f"{i}\n{_format_srt_time(start)} --> {_format_srt_time(end)}\n{chunk}\n")
        start = end
    return "\n".join(lines)


def _escape_filter_path(path: str) -> str:
    # ffmpeg filter option values treat : and \ specially; local paths here
    # never contain these, but escape defensively rather than assume.
    return path.replace("\\", "\\\\").replace(":", "\\:")


def _ken_burns(duration):
    """A slow push into a still photograph.

    A still cut in beside moving footage reads as a glitch, so archival images
    get motion of their own. zoompan works on its output frames, so it's fed a
    frame count rather than seconds, and the source is scaled up first -
    zooming a small image judders because zoompan steps the crop in whole
    source pixels.
    """
    frames = max(1, int(round(duration * FPS)))
    # 1.5x rather than 2x: enough source detail that the zoom steps stay
    # sub-pixel, without making every still shot a 1440x2560 filter pass. The
    # box has two cores and the render is already the slowest step.
    width, height = int(WIDTH * 1.5), int(HEIGHT * 1.5)
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},"
        f"zoompan=z='min(zoom+{KEN_BURNS_SPEED},{KEN_BURNS_MAX_ZOOM})':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
        f"d={frames}:s={WIDTH}x{HEIGHT}:fps={FPS},"
        f"{COLOR_GRADE},format=yuv420p,setsar=1"
    )


def _nearest_clips(beats, index):
    candidates = [i for i, beat in enumerate(beats) if beat.get("clips")]
    if not candidates:
        return []
    return beats[min(candidates, key=lambda i: abs(i - index))]["clips"]


def _plan_shots(beats, audio_duration):
    """Lay the beats out on the timeline and split each into short shots.

    A beat's share of the running time is its share of the script's characters
    - the same model _build_srt uses for captions, so the footage and the words
    move together instead of drifting apart.
    """
    total_chars = sum(len(beat["text"]) for beat in beats) or 1
    shot_seconds = max(MIN_SHOT_SECONDS, audio_duration / MAX_SHOTS)

    shots = []
    elapsed = 0.0
    for index, beat in enumerate(beats):
        is_last = index == len(beats) - 1
        beat_end = audio_duration if is_last else elapsed + len(beat["text"]) / total_chars * audio_duration
        beat_duration = max(0.1, beat_end - elapsed)

        # A beat with no clips would leave a hole in the timeline, and -shortest
        # would then cut the video off at the hole rather than run to the end
        # of the narration. Borrow from the nearest beat that has something.
        stills = [image["path"] for image in beat.get("stills") or []]
        clips = stills or beat.get("clips") or _nearest_clips(beats, index)
        if not clips:
            elapsed = beat_end
            continue

        shot_count = max(1, round(beat_duration / shot_seconds))
        each = beat_duration / shot_count
        for shot_index in range(shot_count):
            clip = clips[shot_index % len(clips)]
            # Start further into the source each time a clip comes back round,
            # so a beat with one clip doesn't replay the same seconds.
            offset = (shot_index // len(clips)) * each
            shots.append(
                {
                    "path": clip,
                    "duration": each,
                    "offset": 0 if stills else offset,
                    "is_still": bool(stills),
                }
            )

        elapsed = beat_end

    return shots


def create_video(
    beats, audio_file, script_text, output_path=None, progress_callback=None,
    word_timings=None, music_path=None,
):
    output_path = output_path or VIDEO_NAME

    if not beats or not any(beat.get("clips") or beat.get("stills") for beat in beats):
        raise Exception("No videos fetched")

    audio_duration = _probe_duration(audio_file)
    shots = _plan_shots(beats, audio_duration)
    shot_count = len(shots)
    fade_out_start = max(0.0, audio_duration - FADE_SECONDS)

    # Silence detection is only needed to correct the character-count
    # estimate - pointless work when real word timings are already exact.
    pause_points = None if word_timings else _detect_pause_points(audio_file)

    srt_file = tempfile.NamedTemporaryFile(mode="w", suffix=".srt", delete=False, encoding="utf-8")
    try:
        srt_file.write(_build_srt(script_text, audio_duration, pause_points, word_timings))
        srt_file.close()

        cmd = ["ffmpeg", "-y", "-loglevel", "error"]
        for shot in shots:
            if shot["is_still"]:
                # Deliberately no -loop/-t: zoompan emits its `d` frames for
                # every frame it's given, so a looped input multiplies the
                # segment by however many frames arrived - a 4-second shot came
                # out 400 seconds long, and -shortest then truncated the video
                # to that one still. One frame in, d frames out, exact.
                cmd += ["-i", shot["path"]]
                continue
            # -stream_loop -1 loops the input indefinitely; the -t before -i caps
            # how much of it is actually read. Together they handle both "source
            # shorter than needed" (loops to fill) and "source longer than
            # needed" (just trimmed) without probing each clip's own duration.
            cmd += ["-stream_loop", "-1"]
            if shot["offset"]:
                cmd += ["-ss", f"{shot['offset']:.3f}"]
            cmd += ["-t", f"{shot['duration']:.3f}", "-i", shot["path"]]
        cmd += ["-i", audio_file]
        narration_idx = shot_count
        music_idx = None
        if music_path:
            music_idx = shot_count + 1
            # Loop like the footage does: a track shorter than the video
            # would otherwise just end partway through it.
            cmd += ["-stream_loop", "-1", "-t", f"{audio_duration:.3f}", "-i", music_path]

        filter_parts = []
        concat_inputs = ""
        for i, shot in enumerate(shots):
            # Hard cuts between shots: at a few seconds each, fading every one
            # in and out would spend most of the video dipped toward black.
            if shot["is_still"]:
                filter_parts.append(f"[{i}:v]{_ken_burns(shot['duration'])}[v{i}]")
            else:
                filter_parts.append(
                    f"[{i}:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
                    f"crop={WIDTH}:{HEIGHT},fps={FPS},{COLOR_GRADE},format=yuv420p,setsar=1[v{i}]"
                )
            concat_inputs += f"[v{i}]"
        filter_parts.append(f"{concat_inputs}concat=n={shot_count}:v=1:a=0[vconcat]")
        filter_parts.append(
            f"[vconcat]fade=t=in:st=0:d={FADE_SECONDS},"
            f"fade=t=out:st={fade_out_start:.3f}:d={FADE_SECONDS}[vfaded]"
        )
        filter_parts.append(
            f"[vfaded]subtitles={_escape_filter_path(srt_file.name)}:"
            f"original_size={WIDTH}x{HEIGHT}:force_style='{CAPTION_STYLE}'[vout]"
        )

        if music_idx is not None:
            # A flat volume cut, not dynamic ducking - simpler and reliable,
            # at a level low enough that narration stays intelligible under
            # it. amix halves each input's amplitude by default (duration=
            # first keeps the output at the narration's length rather than
            # the looped music's), so the cut is compensated back out after.
            filter_parts.append(
                f"[{music_idx}:a]volume={MUSIC_VOLUME_DB}dB,"
                f"afade=t=out:st={fade_out_start:.3f}:d={FADE_SECONDS}[music]"
            )
            filter_parts.append(
                f"[{narration_idx}:a][music]amix=inputs=2:duration=first,"
                f"volume=2[amixed]"
            )
        else:
            filter_parts.append(f"[{narration_idx}:a]anull[amixed]")

        # YouTube (and most platforms) target -14 LUFS integrated loudness and
        # turn down anything louder - a video mixed hotter than that gets
        # quietly renormalized on playback anyway, so there's no upside to
        # skipping this. TP -1.5 keeps peaks clear of clipping after that.
        filter_parts.append(f"[amixed]loudnorm=I=-14:TP=-1.5:LRA=11[aout]")

        cmd += [
            "-filter_complex", ";".join(filter_parts),
            "-map", "[vout]",
            "-map", "[aout]",
            "-c:v", "libx264",
            "-crf", VIDEO_CRF,
            "-preset", VIDEO_PRESET,
            "-c:a", "aac",
            "-b:a", AUDIO_BITRATE,
            "-shortest",
            "-progress", "pipe:1",
            output_path,
        ]

        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        assert process.stdout is not None

        last_pct = -1
        diagnostic_lines = []
        for line in process.stdout:
            line = line.rstrip("\n")
            if line.startswith("out_time_ms="):
                if progress_callback:
                    try:
                        out_time_ms = int(line.split("=", 1)[1])
                        pct = min(100, int(out_time_ms / 1_000_000 / audio_duration * 100))
                        if pct != last_pct:
                            last_pct = pct
                            progress_callback(pct)
                    except ValueError:
                        pass
            elif not line.startswith(_PROGRESS_FIELD_PREFIXES):
                diagnostic_lines.append(line)

        process.wait()

        if process.returncode != 0:
            detail = "\n".join(diagnostic_lines[-40:])
            raise RuntimeError(f"ffmpeg failed (exit {process.returncode}): {detail}")

        if progress_callback and last_pct != 100:
            progress_callback(100)

        return output_path, audio_duration
    finally:
        try:
            os.remove(srt_file.name)
        except OSError:
            pass
