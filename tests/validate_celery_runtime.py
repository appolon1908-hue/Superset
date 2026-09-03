from __future__ import annotations

from superset.tasks.celery_app import app as celery_app
from superset.tasks.celery_app import flask_app


EXPECTED_IMPORTS = {
    "superset.sql_lab",
    "superset.tasks.scheduler",
    "superset.tasks.thumbnails",
    "superset.tasks.cache",
    "superset.tasks.slack",
}
REQUIRED_TASKS = {
    "sql_lab.get_sql_results",
    "reports.scheduler",
    "reports.prune_log",
}
EXPECTED_SCHEDULES = {
    "reports.scheduler",
    "reports.prune_log",
}


def main() -> None:
    with flask_app.app_context():
        configured_imports = set(celery_app.conf.imports or ())
        if configured_imports != EXPECTED_IMPORTS:
            raise SystemExit(
                "Superset Celery imports differ from the locked 6.1.0 set: "
                + ", ".join(sorted(configured_imports))
            )

        celery_app.loader.import_default_modules()
        missing_tasks = sorted(REQUIRED_TASKS.difference(celery_app.tasks))
        if missing_tasks:
            raise SystemExit(
                "missing required Superset Celery tasks: " + ", ".join(missing_tasks)
            )

        schedule = celery_app.conf.beat_schedule or {}
        if set(schedule) != EXPECTED_SCHEDULES:
            raise SystemExit(
                "Superset beat schedules differ from the locked 6.1.0 set: "
                + ", ".join(sorted(schedule))
            )
        for name in EXPECTED_SCHEDULES:
            if schedule[name].get("task") != name:
                raise SystemExit(f"beat schedule task identity mismatch: {name}")

    print("CODESTRA_SUPERSET_CELERY_RUNTIME_VALIDATION=PASS")


if __name__ == "__main__":
    main()
