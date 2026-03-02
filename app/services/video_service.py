from moviepy import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    TextClip,
    vfx
)
from app.config import VIDEO_NAME


def create_video(images, audio_file, script_text):
    audio = AudioFileClip(audio_file)

    clips = []
    duration_per_image = audio.duration / len(images)

    for img in images:
        clip = (
            ImageClip(img)
            .with_duration(duration_per_image)
            .resized(width=1280) # ✅ landscape
            .with_effects([
                vfx.FadeIn(1),
                vfx.FadeOut(1)
            ])
        )
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")
    video = video.resized((1280, 720))  # ✅ landscape output

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