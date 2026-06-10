"""Voice provider protocol — the interface every telephony adapter must satisfy.

Future adapters (LiveKit, SIP, OpenAI Realtime) implement this protocol so that
route handlers remain provider-agnostic.
"""

from typing import Protocol


class VoiceProvider(Protocol):
    """Produce serialised voice responses for a specific telephony layer.

    Implementations return a ready-to-send response string (e.g. TwiML XML)
    and declare the HTTP ``content_type`` the caller should use.
    """

    content_type: str

    def greeting(
        self,
        org_name: str,
        org_slug: str,
        language_code: str,
        gather_action_url: str,
    ) -> str:
        """Incoming-call greeting followed by a prompt for the caller's question."""
        ...

    def answer(
        self,
        response_text: str,
        language_code: str,
        gather_action_url: str,
    ) -> str:
        """Speak the answer and offer to take a follow-up question."""
        ...

    def retry(
        self,
        language_code: str,
        gather_action_url: str,
    ) -> str:
        """Ask the caller to repeat when no speech was captured."""
        ...

    def handoff(
        self,
        language_code: str,
        handoff_phone: str | None,
    ) -> str:
        """Transfer to a human agent, or play an apology if no number is configured."""
        ...

    def caller_requests_handoff(self, speech_text: str) -> bool:
        """Return True when the caller's words explicitly request a human agent."""
        ...
