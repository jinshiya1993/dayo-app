"""Speech-to-text for Dayo's voice features.

One job: take an audio recording from the browser and return the words in
it. Gemini 2.5 Flash accepts audio natively, so this needs no separate
speech service, no new vendor, and no new API key — it reuses the Gemini
access the rest of the app already has.

transcribe() is the whole public surface. It is deliberately thin: it does
not interpret intent or decide actions. The transcript goes to the chat
agent (for voice chat) or the onboarding extractor — the same brains that
already handle typed text. Voice is just another way in.
"""

import base64
import logging

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)

# Browsers record in a handful of formats: Chrome/Firefox give webm/opus,
# Safari gives mp4/aac. Gemini accepts all of these — we just pass the
# mime type the browser reported straight through.
SUPPORTED_AUDIO_TYPES = {
    'audio/webm', 'audio/ogg', 'audio/mp4', 'audio/mpeg',
    'audio/wav', 'audio/x-wav', 'audio/aac', 'audio/flac',
}

# Guard rails on a single clip. Onboarding answers and kitchen questions are
# short; anything past a minute or two is almost certainly a mistake (a
# recording left running), and we would rather reject it than bill for it.
MAX_AUDIO_BYTES = 8 * 1024 * 1024   # ~8 MB, comfortably over a 2-minute clip

_TRANSCRIBE_SYSTEM = (
    'You transcribe short spoken messages from a home cook using a meal '
    'planning app. Return ONLY the exact words spoken, as plain text — no '
    'quotation marks, no commentary, no translation. The speaker may use '
    'Indian or Arabic-accented English and may mention dish names, family '
    'names, and ingredients; spell dish and ingredient names the normal '
    'English way. If the audio is silent or has no discernible speech, '
    'return the single word NO_SPEECH.'
)


def _normalise_mime(raw):
    """Strip codec suffixes: 'audio/webm;codecs=opus' -> 'audio/webm'."""
    return (raw or '').split(';')[0].strip().lower()


def transcribe(audio_bytes, mime_type):
    """Return the spoken text, or '' when nothing was said.

    Raises ValueError for an unusable clip (empty, too big, wrong type) so
    the view can answer 400 rather than spend a Gemini call on it.
    """
    if not audio_bytes:
        raise ValueError('empty audio')
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise ValueError('audio too long — keep it under about two minutes')
    mime = _normalise_mime(mime_type)
    if mime not in SUPPORTED_AUDIO_TYPES:
        raise ValueError('unsupported audio type: %s' % (mime_type or 'none'))

    llm = ChatGoogleGenerativeAI(
        model='gemini-2.5-flash',
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.0,          # transcription is not a creative task
        max_output_tokens=512,
        thinking_budget=0,
        transport='rest',
    )
    message = HumanMessage(content=[
        {'type': 'text', 'text': 'Transcribe this recording.'},
        {
            'type': 'media',
            'mime_type': mime,
            'data': base64.b64encode(audio_bytes).decode('ascii'),
        },
    ])
    response = llm.invoke([SystemMessage(content=_TRANSCRIBE_SYSTEM), message])
    text = (response.content or '').strip()
    if text == 'NO_SPEECH' or not text:
        return ''
    return text
