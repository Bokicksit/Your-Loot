from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars (see .env.example). Field names map
    case-insensitively: database_url <- DATABASE_URL."""

    database_url: str = "postgresql+psycopg2://getloot:changeme@localhost:5432/getloot"
    image_dir: str = "./data/images"

    # "single" signs every request in as the owner and shows no login screen,
    # which is what a one-person install wants and what every existing install
    # keeps doing. "multi" turns on accounts.
    auth_mode: str = "single"
    # Cookie signing. Generated and stored on first start when left empty, so
    # nothing is required to self-host; set it if you run more than one API
    # container, since they have to agree.
    secret_key: str = ""
    # Off by default: plenty of these run on a LAN over plain http, and a
    # secure-only cookie would silently never be sent.
    session_https_only: bool = False

    # Integration credentials. Each is optional: without one, that module's
    # online search returns a 503 telling you which key is missing, and manual
    # entry keeps working. TCGdex, Open Library and MusicBrainz need no key.
    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    tmdb_api_key: str = ""
    rebrickable_api_key: str = ""
    comicvine_api_key: str = ""
    discogs_token: str = ""


settings = Settings()
