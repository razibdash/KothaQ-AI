from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

EXPECTED_TABLES = {
    "organizations",
    "branches",
    "phone_numbers",
    "knowledge_items",
    "conversations",
    "call_turns",
    "unknown_questions",
    "leads",
    "handoffs",
}
REQUIRED_COLUMNS = {
    "organizations": {
        "id",
        "slug",
        "name",
        "default_language",
        "supported_languages",
        "timezone",
        "created_at",
        "updated_at",
    },
    "branches": {"id", "organization_id", "slug", "name"},
    "phone_numbers": {"id", "organization_id", "branch_id", "number_e164"},
    "knowledge_items": {
        "id",
        "organization_id",
        "branch_id",
        "question",
        "answer",
        "language",
        "tags",
        "status",
        "source_type",
        "source_reference",
        "created_at",
        "updated_at",
    },
    "conversations": {
        "id",
        "organization_id",
        "branch_id",
        "provider",
        "provider_call_id",
        "caller_phone_masked",
        "detected_language",
        "status",
        "started_at",
        "ended_at",
    },
    "call_turns": {
        "id",
        "conversation_id",
        "role",
        "input_text",
        "normalized_text",
        "output_text",
        "confidence",
        "intent",
        "created_at",
    },
    "unknown_questions": {
        "id",
        "organization_id",
        "conversation_id",
        "question_text",
        "normalized_text",
        "detected_language",
        "status",
        "suggested_answer",
        "created_at",
    },
    "leads": {
        "id",
        "organization_id",
        "conversation_id",
        "name",
        "phone_masked",
        "interest",
        "branch_id",
        "callback_time",
        "status",
        "created_at",
    },
    "handoffs": {
        "id",
        "organization_id",
        "conversation_id",
        "reason",
        "target_number_masked",
        "status",
        "created_at",
    },
}


def test_initial_migration_creates_required_tables(tmp_path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    database_path = tmp_path / "migration.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.attributes["database_url"] = database_url

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        columns_by_table = {
            table_name: {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for table_name in EXPECTED_TABLES
        }
    finally:
        engine.dispose()

    assert EXPECTED_TABLES <= table_names
    for table_name, required_columns in REQUIRED_COLUMNS.items():
        assert required_columns <= columns_by_table[table_name]
