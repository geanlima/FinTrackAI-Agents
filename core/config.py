import os

from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str | None = os.environ.get("ANTHROPIC_API_KEY")
SERPER_API_KEY: str | None = os.environ.get("SERPER_API_KEY")
POSTGRES_URL: str | None = os.environ.get("POSTGRES_URL")

MODEL_SUPERVISOR: str = "claude-haiku-4-5-20251001"
MODEL_AGENTS: str = "claude-haiku-4-5-20251001"
