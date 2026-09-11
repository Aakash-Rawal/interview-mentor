import os
import sys
from pathlib import Path

# Keep test writes away from the real learner's data, and never need a real key to import.
os.environ.setdefault("INTERVIEW_MENTOR_USER_ID", "pytest-user")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-dummy-for-tests")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
