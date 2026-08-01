"""
Cadence - Application Settings
Centralized configuration using pydantic-settings
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # Neo4j
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "cadence_dev_password"

    # IBM watsonx.ai
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"

    # Model Configuration
    granite_model_id: str = "ibm/granite-13b-chat-v2"
    extraction_temperature: float = 0.1
    extraction_max_tokens: int = 2048

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # Approval Gate
    auto_approve_threshold: float = 0.7
    approval_timeout_hours: int = 24

    # Agent Configuration
    scheduler_interval_minutes: int = 30
    followup_interval_minutes: int = 60
    escalation_interval_minutes: int = 120
    escalation_stale_hours: int = 48

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
