"""CSV import service for tenant-scoped knowledge items."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from io import StringIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.knowledge_item import KnowledgeItem
from app.services.storage import TenantStorageService

REQUIRED_COLUMNS = {"question", "answer", "language"}
OPTIONAL_COLUMNS = {"branch_slug", "tags", "status", "source_reference"}
VALID_STATUSES = {"draft", "approved", "archived"}
CSV_SOURCE_TYPE = "csv_import"


@dataclass(frozen=True)
class KnowledgeCsvRowError:
    row_number: int
    field: str
    message: str


@dataclass
class KnowledgeCsvImportResult:
    imported_items: list[KnowledgeItem] = field(default_factory=list)
    errors: list[KnowledgeCsvRowError] = field(default_factory=list)

    @property
    def imported_count(self) -> int:
        return len(self.imported_items)

    @property
    def skipped_count(self) -> int:
        return len({error.row_number for error in self.errors})


@dataclass(frozen=True)
class _PreparedRow:
    row_number: int
    question: str
    answer: str
    language: str
    branch_id: UUID | None
    tags: list[str]
    status: str
    source_reference: str | None


def import_knowledge_items_from_csv(
    session: Session,
    organization_id: UUID,
    csv_text: str,
) -> KnowledgeCsvImportResult:
    """Import valid knowledge rows and report invalid rows without importing them."""
    reader = _build_reader(csv_text)
    _validate_headers(reader.fieldnames or [])

    branches_by_slug = _load_branches_by_slug(session, organization_id)
    existing_content_keys, existing_source_references = _load_duplicate_keys(
        session, organization_id
    )
    seen_content_keys: set[tuple[str, str, UUID | None]] = set()
    seen_source_references: set[str] = set()

    result = KnowledgeCsvImportResult()
    prepared_rows: list[_PreparedRow] = []

    for row_number, raw_row in enumerate(reader, start=2):
        row = _normalize_row(raw_row)
        errors = _validate_row(
            row_number=row_number,
            row=row,
            branches_by_slug=branches_by_slug,
            existing_content_keys=existing_content_keys,
            existing_source_references=existing_source_references,
            seen_content_keys=seen_content_keys,
            seen_source_references=seen_source_references,
        )
        if errors:
            result.errors.extend(errors)
            continue

        prepared_row = _prepare_row(row_number, row, branches_by_slug)
        prepared_rows.append(prepared_row)
        seen_content_keys.add(_content_key(prepared_row.question, prepared_row.language, prepared_row.branch_id))
        if prepared_row.source_reference is not None:
            seen_source_references.add(prepared_row.source_reference)

    storage = TenantStorageService(session, organization_id)
    for row in prepared_rows:
        result.imported_items.append(
            storage.create_knowledge_item(
                question=row.question,
                answer=row.answer,
                language=row.language,
                branch_id=row.branch_id,
                tags=row.tags,
                status=row.status,
                source_type=CSV_SOURCE_TYPE,
                source_reference=row.source_reference,
            )
        )

    return result


def _build_reader(csv_text: str) -> csv.DictReader:
    try:
        return csv.DictReader(StringIO(csv_text))
    except csv.Error as exc:
        raise ValueError(f"invalid CSV: {exc}") from exc


def _validate_headers(fieldnames: list[str]) -> None:
    normalized_fieldnames = {_normalize_header(fieldname) for fieldname in fieldnames}
    missing = REQUIRED_COLUMNS - normalized_fieldnames
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")


def _normalize_row(raw_row: dict[str, str | None]) -> dict[str, str]:
    return {
        _normalize_header(key): (value or "").strip()
        for key, value in raw_row.items()
        if key is not None
    }


def _normalize_header(header: str) -> str:
    return header.strip().lower().lstrip("\ufeff")


def _load_branches_by_slug(session: Session, organization_id: UUID) -> dict[str, Branch]:
    branches = session.scalars(
        select(Branch).where(Branch.organization_id == organization_id)
    )
    return {branch.slug: branch for branch in branches}


def _load_duplicate_keys(
    session: Session,
    organization_id: UUID,
) -> tuple[set[tuple[str, str, UUID | None]], set[str]]:
    items = session.scalars(
        select(KnowledgeItem).where(KnowledgeItem.organization_id == organization_id)
    )
    content_keys: set[tuple[str, str, UUID | None]] = set()
    source_references: set[str] = set()
    for item in items:
        content_keys.add(_content_key(item.question, item.language, item.branch_id))
        if item.source_type == CSV_SOURCE_TYPE and item.source_reference:
            source_references.add(item.source_reference)
    return content_keys, source_references


def _validate_row(
    *,
    row_number: int,
    row: dict[str, str],
    branches_by_slug: dict[str, Branch],
    existing_content_keys: set[tuple[str, str, UUID | None]],
    existing_source_references: set[str],
    seen_content_keys: set[tuple[str, str, UUID | None]],
    seen_source_references: set[str],
) -> list[KnowledgeCsvRowError]:
    errors: list[KnowledgeCsvRowError] = []
    for field_name in sorted(REQUIRED_COLUMNS):
        if not row.get(field_name):
            errors.append(
                KnowledgeCsvRowError(row_number, field_name, "field is required")
            )

    branch_slug = row.get("branch_slug", "")
    if branch_slug and branch_slug not in branches_by_slug:
        errors.append(
            KnowledgeCsvRowError(
                row_number,
                "branch_slug",
                "branch was not found for this organization",
            )
        )

    status = (row.get("status") or "draft").lower()
    if status not in VALID_STATUSES:
        errors.append(
            KnowledgeCsvRowError(
                row_number,
                "status",
                f"status must be one of: {', '.join(sorted(VALID_STATUSES))}",
            )
        )

    source_reference = row.get("source_reference", "")
    if len(source_reference) > 500:
        errors.append(
            KnowledgeCsvRowError(
                row_number,
                "source_reference",
                "source_reference must be 500 characters or fewer",
            )
        )

    language = row.get("language", "")
    if len(language) > 20:
        errors.append(
            KnowledgeCsvRowError(
                row_number,
                "language",
                "language must be 20 characters or fewer",
            )
        )

    question = row.get("question", "")
    if len(question) > 2000:
        errors.append(
            KnowledgeCsvRowError(
                row_number,
                "question",
                "question must be 2000 characters or fewer",
            )
        )

    answer = row.get("answer", "")
    if len(answer) > 10000:
        errors.append(
            KnowledgeCsvRowError(
                row_number,
                "answer",
                "answer must be 10000 characters or fewer",
            )
        )

    if errors:
        return errors

    branch_id = branches_by_slug[branch_slug].id if branch_slug else None
    content_key = _content_key(question, language, branch_id)
    if content_key in existing_content_keys or content_key in seen_content_keys:
        errors.append(
            KnowledgeCsvRowError(
                row_number,
                "question",
                "duplicate question/language/branch for this organization",
            )
        )

    if source_reference:
        if (
            source_reference in existing_source_references
            or source_reference in seen_source_references
        ):
            errors.append(
                KnowledgeCsvRowError(
                    row_number,
                    "source_reference",
                    "duplicate source_reference for this organization",
                )
            )

    return errors


def _prepare_row(
    row_number: int,
    row: dict[str, str],
    branches_by_slug: dict[str, Branch],
) -> _PreparedRow:
    branch_slug = row.get("branch_slug", "")
    return _PreparedRow(
        row_number=row_number,
        question=row["question"],
        answer=row["answer"],
        language=row["language"],
        branch_id=branches_by_slug[branch_slug].id if branch_slug else None,
        tags=_parse_tags(row.get("tags", "")),
        status=(row.get("status") or "draft").lower(),
        source_reference=row.get("source_reference") or None,
    )


def _content_key(question: str, language: str, branch_id: UUID | None) -> tuple[str, str, UUID | None]:
    return (" ".join(question.lower().split()), language.strip().lower(), branch_id)


def _parse_tags(raw_tags: str) -> list[str]:
    if not raw_tags:
        return []
    separator = ";" if ";" in raw_tags else ","
    return [tag.strip() for tag in raw_tags.split(separator) if tag.strip()]
