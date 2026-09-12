import os
import sys
from pathlib import Path

# Keep test writes away from the real learner's data, and never need a real key to import.
os.environ.setdefault("INTERVIEW_MENTOR_USER_ID", "pytest-user")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-dummy-for-tests")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def purge_user(user_id: str) -> None:
    """Delete every row a test learner owns, in foreign-key-safe order.

    Shared by the module fixtures so the suite does not depend on file order: any
    module that leaves a resume or a job plan behind would otherwise break the
    `users` delete in another module's teardown.
    """
    from db.connection import get_cursor
    with get_cursor(commit=True) as cur:
        cur.execute("DELETE FROM conversation_messages WHERE conversation_id IN "
                    "(SELECT id FROM conversations WHERE user_id = %s)", (user_id,))
        for table in ("conversations", "mocks"):
            cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM focus_areas WHERE target_id IN "
                    "(SELECT id FROM job_targets WHERE user_id = %s)", (user_id,))
        for table in ("job_targets", "applications", "resumes"):
            cur.execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
