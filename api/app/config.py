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
    # Which collections this install charges for. Empty means none, which is
    # what self-hosting means — see app/plans.py.
    paid_modules: str = ""

    # What a free account gets where somebody else is paying for the server.
    # Zero means no limit, which is every self-hosted install — see
    # app/limits.py. A hosted service sets them; the software stays complete
    # for anybody who runs it themselves.
    free_card_limit: int = 0    # copies of cards owned
    free_dex_limit: int = 0     # how far up the Pokédex the binder goes
    free_binder_limit: int = 0  # binders besides the Pokédex
    open_signup: bool = False
    # Public profiles at /u/<name>, and the shelves people choose to show on
    # them. Off by default, which is the honest answer for the install this
    # ships as: a home server nobody outside the house can reach has nothing
    # to publish to, and offering a "public page" that resolves for one person
    # would be a worse feature than not having one.
    #
    # It is one switch with two consequences on purpose. Where profiles are on
    # they replace the downloadable share — a link is simply better than a
    # file when there is a server to answer it. Where they are off the file is
    # the only thing that could ever have worked.
    public_profiles: bool = False
    # New accounts allowed per hour from one address. See ratelimit.py.
    signup_limit: int = 20
    # Searches sent to a third party per minute, per account. See ratelimit.py.
    lookup_limit: int = 60
    # How many proxies stand between the internet and this API, so the rate
    # limiter knows which part of X-Forwarded-For it may believe. That header
    # is a list anyone can start: a caller writes whatever they like, and each
    # proxy appends the address it actually saw. Only the entries the proxies
    # added are worth anything, so the count has to be told rather than
    # guessed. One matches every compose file here — nginx in front of an API
    # whose port is never published. Put Cloudflare, a tunnel or another
    # load balancer in front of that and it becomes two. Zero means the API
    # is exposed directly and the header is ignored entirely.
    trusted_proxies: int = 1
    # Take the caller's address from Cloudflare's CF-Connecting-IP instead of
    # counting hops. For paths where counting cannot work: something between
    # Cloudflare and here discards X-Forwarded-For and starts a new one, so
    # the caller is not in the chain at any depth and every visitor collapses
    # onto a single address. /api/admin/forwarding says whether that is you.
    #
    # Only safe where nothing can reach this API except through Cloudflare.
    # Anybody able to knock on the origin directly can write this header
    # themselves, which is the very hole `trusted_proxies` exists to close.
    trust_cf_connecting_ip: bool = False
    # Let "send my collection to another Your Loot" point at a private
    # address. Off, because a URL somebody types is otherwise a way to make
    # this server post to things on its own network; on, for a home where the
    # other install is a second machine on the LAN.
    sync_allow_private: bool = False
    # Where this install is reachable, for the links inside emails. A verify
    # link has to be absolute and the API cannot infer the public address
    # behind a proxy without being told.
    public_url: str = "http://localhost:5173"
    # Mail. Without both of these nothing is sent and the link is logged
    # instead — see mailer.py. Self-hosters need neither.
    resend_api_key: str = ""
    mail_from: str = ""
    # Payments. Without the first two nothing about billing exists — every
    # route 404s — which is every self-hosted install. The webhook secret is
    # separate because a webhook that cannot be verified must be refused
    # rather than trusted: it is a public URL that grants paid plans.
    stripe_secret_key: str = ""
    stripe_price_id: str = ""
    stripe_webhook_secret: str = ""
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
    # A registered Discogs application's credentials — the proper form for a
    # service, where the personal token above is the right one for a person's
    # own server. Either works; the key/secret pair wins when both are set.
    discogs_key: str = ""
    discogs_secret: str = ""


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
