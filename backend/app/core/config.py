import os


class Settings:
    environment: str = os.getenv("ENVIRONMENT", "development")
    frontend_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("FRONTEND_URL", "http://localhost:3000").split(",")
        if origin.strip()
    ]
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://okala:okala_password@localhost:5432/okala_assessment",
    )
    agent_service_url: str = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001")


settings = Settings()