"""Voice provider factory.

Extend this module when adding new adapters (LiveKit, SIP, OpenAI Realtime).
For now the only available provider is Twilio.
"""

from app.services.telephony.base import VoiceProvider
from app.services.telephony.twilio_adapter import TwilioVoiceAdapter

_twilio = TwilioVoiceAdapter()


def get_voice_provider() -> VoiceProvider:
    """Return the active voice provider adapter."""
    return _twilio  # type: ignore[return-value]
