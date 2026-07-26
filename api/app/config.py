from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars (see .env.example). Field names map
    case-insensitively: database_url <- DATABASE_URL."""

    database_url: str = "postgresql+psycopg2://getloot:changeme@localhost:5432/getloot"
    image_dir: str = "./data/images"

    # phase-2 integration credentials (stubs for now)
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    tmdb_api_key: str = ""


settings = Settings()
