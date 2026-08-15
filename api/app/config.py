from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All config comes from env vars (see .env.example). Field names map
    case-insensitively: database_url <- DATABASE_URL."""

    database_url: str = "postgresql+psycopg2://getloot:changeme@localhost:5432/getloot"
    image_dir: str = "./data/images"

    # "single" signs every request in as the owner and shows no login screen,
    # which is what a one-person install wants and what every existing install
    # keeps doing. "multi" turns on accounts.
    # Origins allowed to call this API from a browser, comma-separated.
    # Empty means same-origin only, which is what nginx serves in production
    # and what every existing install has effectively had. Set it when the UI
    # is served from somewhere else — a phone app, or a browser on another
    # machine pointed at this server.
    allowed_origins: str = ""

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
    # Open signup. Off, and deliberately: the default install of this is one
    # person's home server, where a stranger who finds it must not be able to
    # make themselves an account. A public service turns it on.
    # Which collections this install offers at all, comma-separated. Empty
    # means every one of them, which is what a self-hosted install wants and
    # what every existing install already has. A hosted service names a
    # subset — see app/modules.py.
    available_modules: str = ""
    open_signup: bool = False
    # New accounts allowed per hour from one address. See ratelimit.py.
    signup_limit: int = 20
    # Where this install is reachable, for the links inside emails. A verify
    # link has to be absolute and the API cannot infer the public address
    # behind a proxy without being told.
    public_url: str = "http://localhost:5173"
    # Mail. Without both of these nothing is sent and the link is logged
    # instead — see mailer.py. Self-hosters need neither.
    resend_api_key: str = ""
    mail_from: str = ""
    # Where the mail goes. Resend's own endpoint unless you point it at a
    # compatible relay of your own — or, in the test suite, at a dead port,
    # so that "this server can send mail" can be exercised without any packet
    # leaving the machine.
    mail_api_url: str = "https://api.resend.com/emails"

    igdb_client_id: str = ""
    igdb_client_secret: str = ""
    tmdb_api_key: str = ""
    rebrickable_api_key: str = ""
    comicvine_api_key: str = ""
    discogs_token: str = ""


settings = Settings()


def origin_list() -> list[str]:
    """`allowed_origins` as a list, always including the dev server.

    The Vite dev server is here rather than in the default value so that
    setting one origin does not silently stop `npm run dev` from working —
    forgetting it would look like the API breaking rather than a config
    change.
    """
    named = [o.strip().rstrip("/") for o in settings.allowed_origins.split(",") if o.strip()]
    return named + [o for o in DEV_ORIGINS if o not in named]


DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
