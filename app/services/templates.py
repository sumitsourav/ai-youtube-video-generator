# app/services/templates.py

"""Video styles the user picks between.

Each one varies three things that actually change the result: how the script
is written, what kind of footage its beats ask for, and which voice reads it.
Everything else in the pipeline is shared.

Archival stills are documentary-only on purpose. A photograph of the real
person is the whole point when the narration is about that person, and
actively wrong when the narration is a joke or a story about no one in
particular.
"""

DEFAULT_TEMPLATE = "documentary"


TEMPLATES = {
    "documentary": {
        "label": "Documentary",
        "description": "Factual, cinematic narration built on real detail",
        "voice": "Gregory",
        "music_mood": "cinematic",
        "use_archival": True,
        "narration": """
Write it as documentary narration.
- Open with the single most surprising, specific, or little-known fact - not scene-setting
- Concrete detail throughout: real names, numbers, dates, places, events
- One throughline, not disconnected inspirational statements
- Include at least one fact most people wouldn't know
- Confident and measured; avoid clichés like "the human spirit", "against all odds"
""",
        "visuals": """
- Real places, objects and actions the narration refers to
""",
    },
    "comedy": {
        "label": "Comedy",
        "description": "Wry, observational narration with punchlines",
        "voice": "Danielle",
        "music_mood": "quirky",
        "use_archival": False,
        "narration": """
Write it as a comic monologue - one narrator being funny about the subject, not a sketch with characters.
- Observational humour rooted in things that are actually true about the subject
- Build to punchlines and let them land; don't explain the joke afterwards
- Escalate: each beat a little more absurd than the last, while staying recognisable
- Conversational and quick, contractions welcome, occasional direct address to the viewer
- Funny because the observation is sharp, not because it announces that it's funny - no "hilariously", no exclamation marks
""",
        "visuals": """
- Everyday, slightly mundane scenes - the humour comes from the narration playing against ordinary footage
""",
    },
    "short_film": {
        "label": "Short film",
        "description": "A narrated story with a character and an arc",
        "voice": "Ruth",
        "music_mood": "ambient",
        "use_archival": False,
        "narration": """
Write it as a narrated short story with a beginning, a turn and an ending.
- One central character, named, wanting something specific
- Present tense, close on that character's point of view
- Show the turn through what happens, not by announcing that things changed
- Sensory and particular: what the character sees, hears and does
- End on an image rather than a moral
""",
        "visuals": """
- Atmospheric, unpeopled scenes that carry mood: weather, light, interiors, streets
""",
    },
    # Deliberately not "Cartoon". The narration style is easy; the visuals are
    # not. Stock libraries return live action for "animation" queries no matter
    # how the phrase is worded, and cel-shading real footage through ffmpeg's
    # filters looks like an over-processed photo rather than a drawing. Real
    # animation needs a source the pipeline doesn't have, so this promises the
    # half that works: the storytelling voice, over bright real footage.
    "kids": {
        "label": "Kids' story",
        "description": "Playful, wide-eyed narration over bright, simple visuals",
        "voice": "Patrick",
        "music_mood": "happy",
        "use_archival": False,
        "narration": """
Write it as a playful story told to a curious child.
- Bright, simple language a child would follow, without talking down to them
- Wonder rather than instruction: things are enormous, ancient, impossibly fast
- A clear through-line with a satisfying ending
- Short sentences with bounce to them
""",
        "visuals": """
- Bright, friendly, uncluttered subjects: animals, nature, colourful objects, wide daylight scenes
""",
    },
}


def get_template(name):
    return TEMPLATES.get(name) or TEMPLATES[DEFAULT_TEMPLATE]


def template_choices():
    return [
        {"id": key, "label": value["label"], "description": value["description"]}
        for key, value in TEMPLATES.items()
    ]
