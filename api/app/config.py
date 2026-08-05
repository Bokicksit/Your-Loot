from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars (see .env.example). Field names map
    case-insensitively: database_url <- DATABASE_URL."""

    database_url: str = "postgresql+psycopg2://getloot:changeme@localhost:5432/getloot"
    image_dir: str = "./data/images"

    # Integration credentials. Each is optional: without one, that module's
    # online search returns a 503 telling you which key is missing, and manual
    # entry keeps working. TCGdex, Open Library and MusicBrainz need no key.
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    tmdb_api_key: str = ""
    rebrickable_api_key: str = ""
    comicvine_api_key: str = ""


settings = Settings()
