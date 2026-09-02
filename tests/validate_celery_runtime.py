from __future__ import annotations

from superset.tasks.celery_app import app as celery_app
from superset.tasks.celery_app import flask_app


REQUIRED_TASKS = {
    "sql_lab.get_sql_results",
    "reports.scheduler",
    "reports.prune_log",
    "version_history.prune_old_versions",
    "deletion_retention.purge_soft_deleted",
}
REQUIRED_SCHEDULES = {
    "reports.scheduler",
    "reports.prune_log",
    "version_history.prune_old_versions",
    "deletion_retention.purge_soft_deleted",
}


def main() -> None:
    with flask_app.app_context():
        celery_app.loader.import_default_modules()
        missing_tasks = sorted(REQUIRED_TASKS.difference(celery_app.tasks))
        if missing_tasks:
            raise SystemExit(
                "missing required Superset Celery tasks: " + ", ".join(missing_tasks)
            )

        schedule = celery_app.conf.beat_schedule or {}
        missing_schedules = sorted(REQUIRED_SCHEDULES.difference(schedule))
        if missing_schedules:
            raise SystemExit(
                "missing required Superset beat schedules: "
                + ", ".join(missing_schedules)
            )
        for name in REQUIRED_SCHEDULES:
            if schedule[name].get("task") != name:
                raise SystemExit(f"beat schedule task identity mismatch: {name}")

    print("CODESTRA_SUPERSET_CELERY_RUNTIME_VALIDATION=PASS")


if __name__ == "__main__":
    main()
