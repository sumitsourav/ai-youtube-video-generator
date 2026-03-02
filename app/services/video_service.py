from moviepy import (
    VideoFileClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip,
    vfx
)
from app.config import VIDEO_NAME


def create_video(video_files, audio_file, script_text):
    audio = AudioFileClip(audio_file)

    if not video_files:
        raise Exception("No videos fetched")

    clips = []
    duration_per_clip = audio.duration / len(video_files)

    for video_path in video_files:
        clip = VideoFileClip(video_path)

        # Safe Trimming: If video is shorter than needed, loop it; otherwise, trim to fit
        if clip.duration >= duration_per_clip:
            clip = clip.subclipped(0, duration_per_clip)
        else:
            # ✅ Repeat clip manually
            repeats = int(duration_per_clip // clip.duration) + 1
            clip = concatenate_videoclips([clip] * repeats)
            clip = clip.subclipped(0, duration_per_clip)

        # ✅ Apply resize & effects AFTER trimming
        clip = (
            clip
            .resized((1280, 720)) # ✅ landscape
            .with_effects([
                vfx.FadeIn(1),
                vfx.FadeOut(1)
            ])
        )
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    #video = video.resized((1280, 720))  # ✅ landscape output

    # subtitles
    # txt_clip = (
    #     TextClip(
    #         text=script_text,
    #         font="/System/Library/Fonts/Helvetica.ttc",
    #         font_size=40,
    #         color='white',
    #         size=(720, 1280),
    #         method='caption'
    #     )
    #     .with_duration(audio.duration)
    # )

    video = CompositeVideoClip([video])

    video = video.with_audio(audio)

    video.write_videofile(VIDEO_NAME, fps=24)

    return VIDEO_NAME