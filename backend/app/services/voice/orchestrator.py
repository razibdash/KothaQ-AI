"""Voice turn orchestrator — LangGraph StateGraph implementation.

The pipeline is expressed as a LangGraph ``StateGraph`` when ``langgraph`` is
installed (Python 3.12+, after the venv is rebuilt).  When the package is
absent the identical node functions are executed sequentially, so behaviour is
**exactly the same** in both modes and existing tests run unchanged.

Graph topology
--------------

  START
    │
  detect_language        ← choose response language from caller utterance
    │
  search_and_evaluate    ← semantic/fuzzy search + answer-policy check
    │
  style_response         ← format the verified answer or fallback text
    │
  capture_lead           ← intent detection + incremental field extraction
    │
  log_and_finalize       ← emit structured events, assemble final text
    │
  END

All node functions reference module-level service imports so that
``monkeypatch.setattr(orchestrator_module, "search_knowledge", ...)`` in
tests redirects calls correctly regardless of execution mode.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, NotRequired, TypedDict
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.services.ai.answer_policy import (
    AnswerPolicyCandidate,
    AnswerPolicyResult,
    evaluate_answer_policy,
)
from app.services.knowledge.search import (
    KnowledgeSearchResult,
    normalize_search_text,
    search_knowledge,
)
from app.services.language.language_router import choose_response_language, detect_language
from app.services.leads.capture import (
    LeadFields,
    apply_extraction,
    callback_question,
    extract_callback_time,
    is_lead_complete,
    next_lead_question,
)
from app.services.leads.intent import detect_lead_intent
from app.services.storage import TenantStorageService
from app.services.tenancy import OrganizationContext
from app.services.voice.response_style import (
    ResponseStyle,
    caller_requests_details,
    style_verified_answer,
    unknown_answer_fallback,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# LangGraph availability guard — graceful degradation on Python 3.14 / CI
# ---------------------------------------------------------------------------

try:
    from langgraph.graph import END, START, StateGraph

    _LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGGRAPH_AVAILABLE = False


# ---------------------------------------------------------------------------
# Shared state that flows through every node
# ---------------------------------------------------------------------------


class VoiceTurnState(TypedDict):
    """Single mutable dict threaded through every node in the voice graph.

    Inputs are set once at graph start and never mutated.
    Node outputs are merged into state as each node completes.
    ``session`` is not JSON-serialisable; checkpointing is not used.
    """

    # ── Inputs (immutable after graph start) ────────────────────────────────
    session: Any  # sqlalchemy.orm.Session
    organization: OrganizationContext
    caller_text: str
    call_id: str | None
    branch_id: UUID | None
    conversation_id: UUID | None
    response_style: str

    # ── Set by nodes (not present until that node completes) ─────────────────
    detected_language: NotRequired[str]
    search_result: NotRequired[KnowledgeSearchResult | None]
    normalized_text: NotRequired[str]
    policy: NotRequired[AnswerPolicyResult | None]
    response_text: NotRequired[str]
    lead_follow_up: NotRequired[str | None]
    should_handoff: NotRequired[bool]


# ---------------------------------------------------------------------------
# Node: detect_language
# ---------------------------------------------------------------------------


def _node_detect_language(state: VoiceTurnState) -> dict:
    organization = state["organization"]
    language = choose_response_language(
        state["caller_text"],
        organization.default_language,
        organization.supported_languages,
    )
    log_event(
        logger,
        logging.INFO,
        "language_detected",
        tenant_id=organization.tenant_id,
        call_id=state["call_id"],
        organization_slug=organization.slug,
        language=language,
    )
    return {"detected_language": language}


# ---------------------------------------------------------------------------
# Node: search_and_evaluate
# ---------------------------------------------------------------------------


def _node_search_and_evaluate(state: VoiceTurnState) -> dict:
    organization = state["organization"]
    caller_text = state["caller_text"]

    result = search_knowledge(
        state["session"],
        organization.id,
        caller_text,
        branch_id=state["branch_id"],
    )
    normalized_text = normalize_search_text(caller_text)
    candidate = AnswerPolicyCandidate(item=result.source_item, confidence=result.confidence)
    policy = evaluate_answer_policy(
        caller_text,
        normalized_text,
        organization.id,
        candidate,
        branch_id=state["branch_id"],
    )
    return {
        "search_result": result,
        "normalized_text": normalized_text,
        "policy": policy,
        "should_handoff": policy.should_handoff,
    }


# ---------------------------------------------------------------------------
# Node: style_response
# ---------------------------------------------------------------------------


def _node_style_response(state: VoiceTurnState) -> dict:
    policy: AnswerPolicyResult = state["policy"]
    language = state["detected_language"]
    style = state["response_style"]
    caller_text = state["caller_text"]

    if policy.answer_allowed:
        text = style_verified_answer(
            policy.response_text,
            language,
            style,
            include_details=caller_requests_details(caller_text),
        )
    else:
        text = unknown_answer_fallback(language, style)

    return {"response_text": text}


# ---------------------------------------------------------------------------
# Node: capture_lead
# ---------------------------------------------------------------------------


def _node_capture_lead(state: VoiceTurnState) -> dict:
    conversation_id = state.get("conversation_id")
    if conversation_id is None:
        return {"lead_follow_up": None}

    organization = state["organization"]
    caller_text = state["caller_text"]
    policy: AnswerPolicyResult = state["policy"]
    language = state["detected_language"]
    session = state["session"]
    call_id = state["call_id"]
    lead_follow_up: str | None = None

    storage = TenantStorageService(session, organization.id)
    active_lead = storage.get_active_lead(conversation_id)
    intent = detect_lead_intent(caller_text)

    if active_lead is not None and active_lead.status == "finalizing":
        callback_notes = extract_callback_time(caller_text)
        storage.finalize_lead(active_lead.id, callback_notes=callback_notes)
        log_event(
            logger,
            logging.INFO,
            "lead_finalized",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
        )

    elif active_lead is not None or intent is not None:
        current_fields = LeadFields(
            interest=active_lead.interest if active_lead else None,
            name=active_lead.name if active_lead else None,
            phone_masked=active_lead.phone_masked if active_lead else None,
        )
        effective_intent = intent or "general"
        updated_fields = apply_extraction(current_fields, caller_text, effective_intent)

        if updated_fields.interest is None and intent is not None:
            updated_fields = LeadFields(
                interest=intent,
                name=updated_fields.name,
                phone_masked=updated_fields.phone_masked,
            )

        upserted = storage.upsert_collecting_lead(
            conversation_id=conversation_id,
            interest=updated_fields.interest,
            name=updated_fields.name,
            phone_masked=updated_fields.phone_masked,
        )
        log_event(
            logger,
            logging.INFO,
            "lead_updated",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
            lead_id=str(upserted.id),
        )

        if is_lead_complete(updated_fields):
            callback_notes = extract_callback_time(caller_text)
            if callback_notes:
                storage.finalize_lead(upserted.id, callback_notes=callback_notes)
                log_event(
                    logger,
                    logging.INFO,
                    "lead_finalized",
                    tenant_id=organization.tenant_id,
                    call_id=call_id,
                    organization_slug=organization.slug,
                )
            else:
                storage.set_lead_status(upserted.id, "finalizing")
                if not policy.should_handoff:
                    lead_follow_up = callback_question(language)
        elif not policy.should_handoff:
            lead_follow_up = next_lead_question(updated_fields, language)

    return {"lead_follow_up": lead_follow_up}


# ---------------------------------------------------------------------------
# Node: log_and_finalize
# ---------------------------------------------------------------------------


def _node_log_and_finalize(state: VoiceTurnState) -> dict:
    organization = state["organization"]
    call_id = state["call_id"]
    policy: AnswerPolicyResult = state["policy"]
    caller_text = state["caller_text"]
    response_text = state["response_text"]
    lead_follow_up: str | None = state.get("lead_follow_up")
    conversation_id = state.get("conversation_id")
    normalized_text: str = state.get("normalized_text", "")
    language = state["detected_language"]

    final_response = f"{response_text} {lead_follow_up}" if lead_follow_up else response_text

    log_event(
        logger,
        logging.INFO,
        "answer_selected",
        tenant_id=organization.tenant_id,
        call_id=call_id,
        organization_slug=organization.slug,
        confidence=policy.confidence,
        source_id=policy.source_knowledge_item_id,
        requires_handoff=policy.should_handoff,
    )

    if policy.should_log_unknown:
        TenantStorageService(state["session"], organization.id).create_unknown_question(
            question_text=caller_text,
            conversation_id=conversation_id,
            normalized_text=normalized_text,
            detected_language=detect_language(caller_text),
        )
        log_event(
            logger,
            logging.WARNING,
            "unknown_question",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
            language=language,
            input_length=len(caller_text),
        )

    if policy.should_handoff:
        log_event(
            logger,
            logging.INFO,
            "handoff_requested",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
            reason=policy.reason,
        )

    return {"response_text": final_response}


# ---------------------------------------------------------------------------
# Graph builder (LangGraph path)
# ---------------------------------------------------------------------------

_PIPELINE = (
    _node_detect_language,
    _node_search_and_evaluate,
    _node_style_response,
    _node_capture_lead,
    _node_log_and_finalize,
)


@lru_cache(maxsize=1)
def _build_graph():
    """Compile the voice turn StateGraph once and cache it.

    Returns ``None`` when langgraph is not installed so the sequential runner
    takes over.  The graph is stateless — no checkpointer is attached — making
    it safe to share across requests.
    """
    if not _LANGGRAPH_AVAILABLE:
        return None  # pragma: no cover

    graph: StateGraph = StateGraph(VoiceTurnState)

    graph.add_node("detect_language", _node_detect_language)
    graph.add_node("search_and_evaluate", _node_search_and_evaluate)
    graph.add_node("style_response", _node_style_response)
    graph.add_node("capture_lead", _node_capture_lead)
    graph.add_node("log_and_finalize", _node_log_and_finalize)

    graph.add_edge(START, "detect_language")
    graph.add_edge("detect_language", "search_and_evaluate")
    graph.add_edge("search_and_evaluate", "style_response")
    graph.add_edge("style_response", "capture_lead")
    graph.add_edge("capture_lead", "log_and_finalize")
    graph.add_edge("log_and_finalize", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Sequential runner (fallback when langgraph is not installed)
# ---------------------------------------------------------------------------


def _run_sequential(state: VoiceTurnState) -> VoiceTurnState:
    """Run every node in order, merging each node's output dict into state."""
    current: dict = dict(state)
    for node_fn in _PIPELINE:
        current.update(node_fn(current))  # type: ignore[arg-type]
    return current  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public API — unchanged interface so voice webhooks need no edits
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VoiceTurnResult:
    """Return value of VoiceOrchestrator.handle_turn."""

    response_text: str
    should_handoff: bool
    detected_language: str


class VoiceOrchestrator:
    def __init__(self, session: Session) -> None:
        self.session = session

    def handle_turn(
        self,
        organization: OrganizationContext,
        caller_text: str,
        *,
        call_id: str | None = None,
        branch_id: UUID | None = None,
        conversation_id: UUID | None = None,
        response_style: ResponseStyle = "student_friendly",
    ) -> VoiceTurnResult:
        """Handle one tenant-scoped caller turn and return a structured voice reply.

        Logs ``user_input_received`` before entering the graph so it is always
        emitted even when a node raises.  All remaining events are emitted
        inside nodes so the log order is deterministic.
        """
        log_event(
            logger,
            logging.INFO,
            "user_input_received",
            tenant_id=organization.tenant_id,
            call_id=call_id,
            organization_slug=organization.slug,
            input_length=len(caller_text),
        )

        initial_state: VoiceTurnState = {
            "session": self.session,
            "organization": organization,
            "caller_text": caller_text,
            "call_id": call_id,
            "branch_id": branch_id,
            "conversation_id": conversation_id,
            "response_style": response_style,
        }

        try:
            compiled_graph = _build_graph()
            if compiled_graph is not None:
                final_state = compiled_graph.invoke(initial_state)
            else:
                final_state = _run_sequential(initial_state)
        except Exception as exc:
            log_event(
                logger,
                logging.ERROR,
                "voice_turn_error",
                tenant_id=organization.tenant_id,
                call_id=call_id,
                organization_slug=organization.slug,
                error_type=type(exc).__name__,
                operation="handle_turn",
            )
            raise

        return VoiceTurnResult(
            response_text=final_state["response_text"],
            should_handoff=final_state["should_handoff"],
            detected_language=final_state["detected_language"],
        )
