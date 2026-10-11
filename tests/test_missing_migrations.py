from alembic import command


def test_for_missing_migrations(alembic_config):
    """Fails (CommandError) when the models differ from what the migrations produce, alerting
    your team that someone changed a model and forgot the migration."""
    command.check(alembic_config)


def test_migrations_can_be_reverted_and_reapplied(alembic_config):
    try:
        command.downgrade(alembic_config, "base")
        command.upgrade(alembic_config, "head")
    finally:
        command.upgrade(alembic_config, "head")
