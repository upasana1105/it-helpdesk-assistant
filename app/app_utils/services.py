"""Service initializations and configuration helpers."""
import os
from typing import Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "demo-project")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3.6-flash")



# Model Armor settings
MODEL_ARMOR_PROJECT_ID = os.getenv("MODEL_ARMOR_PROJECT_ID", PROJECT_ID)
MODEL_ARMOR_LOCATION = os.getenv("MODEL_ARMOR_LOCATION", "us")
MODEL_ARMOR_TEMPLATE_ID = os.getenv("MODEL_ARMOR_TEMPLATE_ID")
MODEL_ARMOR_STRICT_MODE = os.getenv("MODEL_ARMOR_STRICT_MODE", "false").lower() == "true"


def get_model_name() -> str:
    """Return model name for agent generation."""
    return MODEL_NAME


def get_gcp_project() -> str:
    """Return configured GCP project ID."""
    return PROJECT_ID


def get_gcp_location() -> str:
    """Return configured GCP region location."""
    return LOCATION
