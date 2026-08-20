// FastAPI answers a rejected field with `detail` as a *list* of error objects,
// not a string. Reading it as one gave every validation failure in the app the
// same message — "[object Object]" — which says nothing about which field was
// wrong or why. This names the field and quotes the reason.
export function errorMessage(body, res) {
  const d = body?.detail;
  if (typeof d === "string" && d) return d;
  if (Array.isArray(d) && d.length) {
    const said = d.slice(0, 3).map((e) => {
      // loc is ["body", "country"] — the tail is the field, and for a nested
      // model it's the last name rather than the whole path.
      const field = (e.loc || []).filter((p) => p !== "body" && typeof p === "string").pop();
      const msg = e.msg || "is not valid";
      return field ? `${field}: ${msg}` : msg;
    });
    if (d.length > said.length) said.push(`and ${d.length - said.length} more`);
    return said.join("; ");
  }
  return `${res.status} ${res.statusText}`;
}

// Where the API lives. Empty means "wherever this page came from", which is
// every browser install: nginx serves the UI and the API from one origin and
// the request never leaves it. A client that is not served by the API — a
// phone app, or a browser on another machine — sets this instead.
//
// Read from localStorage rather than baked in at build time so one build can
// point anywhere, which is the whole point of it being settable.
export const apiBase = () => localStorage.getItem("loot.apiBase") || "";
export const setApiBase = (url) => {
  const clean = (url || "").trim().replace(/\/+$/, "");
  if (clean) localStorage.setItem("loot.apiBase", clean);
  else localStorage.removeItem("loot.apiBase");
};

// A token, for when there is no cookie to hold — see /api/auth/tokens.
export const apiToken = () => localStorage.getItem("loot.apiToken") || "";
export const setApiToken = (t) => {
  if (t) localStorage.setItem("loot.apiToken", t);
  else localStorage.removeItem("loot.apiToken");
};

/** Absolute when a base is set, unchanged when it isn't. */
export const url = (path) => apiBase() + path;

/** Credentials for a cross-origin call: the cookie cannot travel, so a token
 *  goes in a header instead. Same-origin keeps using the cookie and adds
 *  nothing. */
function authHeaders() {
  const t = apiToken();
  return t ? { Authorization: `bearer ${t}` } : {};
}

// Thin fetch wrapper. Same-origin by default — nginx (prod) or vite (dev)
// proxies /api — and absolute once a base URL is set.
async function request(path, options = {}) {
  const res = await fetch(url(path), {
    // the cookie only travels cross-origin if it is asked for, and only then
    // when the server names this origin
    credentials: "include",
    ...options,
    // last, so a caller cannot drop the auth header by passing its own
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    // A session that expired mid-use. Every screen would otherwise show its
    // own error for the same cause; reloading puts the sign-in gate up, which
    // is the actual answer.
    window.location.reload();
    throw new Error("Signed out");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(errorMessage(body, res));
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  authMe: () => request("/api/auth/me"),
  authLogin: (body) =>
    request("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
  authSetup: (body) =>
    request("/api/auth/setup", { method: "POST", body: JSON.stringify(body) }),
  authLogout: () => request("/api/auth/logout", { method: "POST" }),
  // Only answered when the server offers open signup — see OPEN_SIGNUP. On a
  // self-hosted install every one of these is a 404, which is why the UI asks
  // /me first rather than showing a link that leads nowhere.
  authSignup: (body) =>
    request("/api/auth/signup", { method: "POST", body: JSON.stringify(body) }),
  authVerify: (token) =>
    request("/api/auth/verify", { method: "POST", body: JSON.stringify({ token }) }),
  authResendVerification: () =>
    request("/api/auth/verify/resend", { method: "POST" }),
  authForgot: (email) =>
    request("/api/auth/forgot", { method: "POST", body: JSON.stringify({ email }) }),
  authReset: (token, password) =>
    request("/api/auth/reset", {
      method: "POST",
      body: JSON.stringify({ token, password }),
    }),
  authDeleteMe: (password) =>
    request("/api/auth/me", { method: "DELETE", body: JSON.stringify({ password }) }),
  changePassword: (body) =>
    request("/api/auth/password", { method: "POST", body: JSON.stringify(body) }),
  // Billing. Every route but status 404s on an install with no Stripe keys,
  // which is every self-hosted one — status answers so the screen knows not
  // to draw anything.
  billingStatus: () => request("/api/billing/status"),
  billingCheckout: () => request("/api/billing/checkout", { method: "POST" }),
  billingPortal: () => request("/api/billing/portal", { method: "POST" }),

  // Admin-only; every one of these 403s for anybody else.
  adminStats: () => request("/api/admin/stats"),
  adminUsers: () => request("/api/admin/users"),
  adminSetPlan: (id, body) =>
    request(`/api/admin/users/${id}/plan`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  users: () => request("/api/auth/users"),
  inviteUser: (body) =>
    request("/api/auth/users", { method: "POST", body: JSON.stringify(body) }),
  deleteUser: (id) => request(`/api/auth/users/${id}`, { method: "DELETE" }),
  cards: (params = {}) =>
    request(`/api/cards?${new URLSearchParams(params)}`),
  cardSets: () => request("/api/cards/sets"),
  tcgdexSearch: (params) =>
    request(`/api/cards/tcgdex/search?${new URLSearchParams(params)}`),
  addFromTcgdex: (cardId) =>
    request(`/api/cards/tcgdex/${encodeURIComponent(cardId)}`, { method: "POST" }),
  addCard: (body) =>
    request("/api/cards", { method: "POST", body: JSON.stringify(body) }),
  deleteCard: (itemId) => request(`/api/cards/${itemId}`, { method: "DELETE" }),
  updateCard: (itemId, body) =>
    request(`/api/cards/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  fetchImage: (url) =>
    request("/api/images/fetch", { method: "POST", body: JSON.stringify({ url }) }),
  uploadImage: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    // no Content-Type header: the browser sets the multipart boundary
    const res = await fetch(url("/api/images"), {
      method: "POST",
      body: fd,
      credentials: "include",
      headers: authHeaders(),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      throw new Error(errorMessage(b, res));
    }
    return res.json();
  },
  cardFacets: (params = {}) =>
    request(`/api/cards/facets?${new URLSearchParams(params)}`),
  cardsSearch: (params) =>
    request(`/api/cards/search?${new URLSearchParams(params)}`),
  // Binders. The Pokédex is one of these too — it keeps its own endpoints
  // above because its slots are filled by choosing between the cards you own,
  // which the other kinds never have to do.
  binders: () => request("/api/binders"),
  binder: (id) => request(`/api/binders/${id}`),
  binderSets: () => request("/api/binders/sets/available"),
  profile: () => request("/api/profile"),
  saveProfile: (body) =>
    request("/api/profile", { method: "PUT", body: JSON.stringify(body) }),
  adminRepairCovers: () =>
    request("/api/admin/repair-covers", { method: "POST" }),
  adminSetComped: (userId, comped) =>
    request(`/api/admin/users/${userId}/comped`, {
      method: "PUT",
      body: JSON.stringify({ comped }),
    }),
  revokeScreenName: (userId) =>
    request(`/api/admin/users/${userId}/screen-name`, { method: "DELETE" }),
  createBinder: (body) =>
    request("/api/binders", { method: "POST", body: JSON.stringify(body) }),
  editBinder: (id, body) =>
    request(`/api/binders/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteBinder: (id) => request(`/api/binders/${id}`, { method: "DELETE" }),
  binderAddCards: (id, ownedIds) =>
    request(`/api/binders/${id}/cards`, {
      method: "POST",
      body: JSON.stringify({ owned_ids: ownedIds }),
    }),
  binderRemoveCard: (id, ownedId) =>
    request(`/api/binders/${id}/cards/${ownedId}`, { method: "DELETE" }),
  binderRemoveSlot: (id, slotId) =>
    request(`/api/binders/${id}/slots/${slotId}`, { method: "DELETE" }),
  binderAddBlank: (id) =>
    request(`/api/binders/${id}/slots/blank`, { method: "POST" }),
  reorderShelf: (binderIds) =>
    request("/api/binders/order", {
      method: "PUT",
      body: JSON.stringify({ binder_ids: binderIds }),
    }),
  binderReorder: (id, slotIds) =>
    request(`/api/binders/${id}/order`, {
      method: "PUT",
      body: JSON.stringify({ slot_ids: slotIds }),
    }),
  binderFillSlot: (id, key, body) =>
    request(`/api/binders/${id}/slots/${encodeURIComponent(key)}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  pokedex: () => request("/api/cards/pokedex"),
  dexHappy: (dexNo, happy) =>
    request(`/api/cards/pokedex/${dexNo}/happy`, {
      method: "PUT",
      body: JSON.stringify({ happy }),
    }),
  // asked before an add creates anything, so a second copy is a decision
  duplicates: (module, title) =>
    request(`/api/duplicates?${new URLSearchParams({ module, title })}`),
  wanted: (params = {}) =>
    request(`/api/wanted?${new URLSearchParams(params)}`),
  games: (params = {}) =>
    request(`/api/games?${new URLSearchParams(params)}`),
  platforms: () => request("/api/games/platforms"),
  platformsInUse: () => request("/api/games/platforms?in_use=true"),
  igdbSearch: (q) =>
    request(`/api/games/igdb/search?q=${encodeURIComponent(q)}`),
  // the seeded NA console-variant catalogue — local, keyless, instant
  hardwareCatalogue: (params) =>
    request(`/api/games/hardware/catalogue?${new URLSearchParams(params)}`),
  movies: (params = {}) =>
    request(`/api/movies?${new URLSearchParams(params)}`),
  movieFormats: () => request("/api/movies/formats"),
  addMovie: (body) =>
    request("/api/movies", { method: "POST", body: JSON.stringify(body) }),
  deleteMovie: (itemId) =>
    request(`/api/movies/${itemId}`, { method: "DELETE" }),
  updateMovie: (itemId, body) =>
    request(`/api/movies/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  tmdbSearch: (q) =>
    request(`/api/movies/tmdb/search?q=${encodeURIComponent(q)}`),
  barcodeLookup: (code) => request(`/api/lookup/barcode?code=${code}`),
  // requireImages=false when you are after the product rather than its
  // picture — plenty of real hardware listings carry no photo at all
  productSearch: (q, requireImages = true) =>
    request(
      `/api/lookup/products?${new URLSearchParams({ q, require_images: requireImages })}`
    ),
  // Retailer image hosts rot and some block hotlinking, so a chosen box-art
  // photo is copied to our own storage. TMDB/IGDB CDNs are stable and stay
  // hotlinked. Falls back to the original URL if the copy fails — a picture
  // that might break later beats no picture.
  /** Copy a remote image into our own storage before storing its URL.
   *
   *  Two different failures, two different answers. The source saying "no
   *  such image" means the URL is dead — storing it would write a broken
   *  frame into the collection permanently, which is how a shelf of records
   *  ended up with no pictures. Nothing gets stored. A network hiccup, by
   *  contrast, keeps the original URL: it may well load in the browser even
   *  when the server could not reach it just now. */
  localiseImage: async (url) => {
    // Commons is on this list for a second reason too: it rate-limits
    // server-side fetches hard (429), and the console catalogue's images
    // live there — hotlinking is how that dataset says they are meant to
    // be used.
    const stable = /image\.tmdb\.org|igdb\.com|wikimedia\.org/i;
    if (!url || !/^https?:/i.test(url) || stable.test(url)) return url;
    try {
      const { url: local } = await api.fetchImage(url);
      return local;
    } catch (e) {
      // 429 is "slow down", not "no such image" — dropping the URL over a
      // rate limit would turn a busy afternoon into a permanently missing
      // picture. Only the source's own "this does not exist" nulls it.
      return /source returned (?!429)4\d\d/.test(e.message || "") ? null : url;
    }
  },
  amiibo: (params = {}) => request(`/api/amiibo?${new URLSearchParams(params)}`),
  amiiboFacets: () => request("/api/amiibo/facets"),
  amiiboSearch: (params) =>
    request(`/api/amiibo/search?${new URLSearchParams(params)}`),
  addAmiibo: (body) =>
    request("/api/amiibo", { method: "POST", body: JSON.stringify(body) }),
  updateAmiibo: (itemId, body) =>
    request(`/api/amiibo/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteAmiibo: (itemId) => request(`/api/amiibo/${itemId}`, { method: "DELETE" }),
  books: (params = {}) => request(`/api/books?${new URLSearchParams(params)}`),
  bookFacets: () => request("/api/books/facets"),
  addBook: (body) =>
    request("/api/books", { method: "POST", body: JSON.stringify(body) }),
  updateBook: (itemId, body) =>
    request(`/api/books/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteBook: (itemId) => request(`/api/books/${itemId}`, { method: "DELETE" }),
  bookDescription: (olid) =>
    request(`/api/books/description?olid=${encodeURIComponent(olid)}`),
  openLibrarySearch: (params) =>
    request(`/api/books/search?${new URLSearchParams(params)}`),
  // Tags: one endpoint for every collection. `scope` is the collection as the
  // app shows it, so hardware asks for its own words rather than games'.
  tags: (scope, params = {}) =>
    request(`/api/tags?${new URLSearchParams({ scope, ...params })}`),
  setItemTags: (itemId, scope, names) =>
    request(`/api/tags/item/${itemId}`, {
      method: "PUT",
      body: JSON.stringify({ scope, names }),
    }),
  renameTag: (tagId, name) =>
    request(`/api/tags/${tagId}`, { method: "PATCH", body: JSON.stringify({ name }) }),
  deleteTag: (tagId) => request(`/api/tags/${tagId}`, { method: "DELETE" }),
  records: (params = {}) => request(`/api/records?${new URLSearchParams(params)}`),
  recordFacets: () => request("/api/records/facets"),
  addRecord: (body) =>
    request("/api/records", { method: "POST", body: JSON.stringify(body) }),
  updateRecord: (itemId, body) =>
    request(`/api/records/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRecord: (itemId) => request(`/api/records/${itemId}`, { method: "DELETE" }),
  recordTracklist: (releaseId) =>
    request(`/api/records/tracklist?release_id=${encodeURIComponent(releaseId)}`),
  musicBrainzSearch: (params) =>
    request(`/api/records/search?${new URLSearchParams(params)}`),
  lego: (params = {}) => request(`/api/lego?${new URLSearchParams(params)}`),
  legoFacets: () => request("/api/lego/facets"),
  addLego: (body) =>
    request("/api/lego", { method: "POST", body: JSON.stringify(body) }),
  updateLego: (itemId, body) =>
    request(`/api/lego/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteLego: (itemId) => request(`/api/lego/${itemId}`, { method: "DELETE" }),
  rebrickableSearch: (params) =>
    request(`/api/lego/search?${new URLSearchParams(params)}`),
  comics: (params = {}) => request(`/api/comics?${new URLSearchParams(params)}`),
  comicFacets: () => request("/api/comics/facets"),
  addComic: (body) =>
    request("/api/comics", { method: "POST", body: JSON.stringify(body) }),
  updateComic: (itemId, body) =>
    request(`/api/comics/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteComic: (itemId) => request(`/api/comics/${itemId}`, { method: "DELETE" }),
  gameBoxart: (params) =>
    request(`/api/games/boxart?${new URLSearchParams(params)}`),
  comicRuns: (series) =>
    request(`/api/comics/runs?series=${encodeURIComponent(series)}`),
  comicVineSearch: (params) =>
    request(`/api/comics/search?${new URLSearchParams(params)}`),
  backupUrl: "/api/backup",
  /** A share comes back as a file rather than JSON, and carries a count of the
   *  covers that could not be fetched — so it can't go through `request`,
   *  which reads the body as JSON and drops the headers. A plain <a download>
   *  can't do it either: that sends no Authorization header, so it would fail
   *  outright against a remote base URL. */
  share: async (scope, images = true) => {
    const res = await fetch(url(`/api/share/${scope}?images=${images}`), {
      credentials: "include",
      headers: authHeaders(),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(errorMessage(body, res));
    }
    const name = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") || "");
    return {
      blob: await res.blob(),
      failed: Number(res.headers.get("X-Share-Images-Failed") || 0),
      filename: name ? name[1] : `yourloot-${scope}.html`,
    };
  },
  // Your own collection, which everybody has and nothing gates.
  myBackupUrl: "/api/backup/mine",
  /** Same shape as restoreBackup below, and for the same reason: a file goes
   *  up as multipart, so `request` — which insists on JSON — cannot carry it. */
  restoreMine: async (file, confirm) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("confirm", confirm);
    const res = await fetch(url("/api/backup/mine"), {
      method: "POST",
      body: fd,
      credentials: "include",
      headers: authHeaders(),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      throw new Error(errorMessage(b, res));
    }
    return res.json();
  },
  restoreBackup: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    // no Content-Type header: the browser sets the multipart boundary
    const res = await fetch(url("/api/backup/restore"), {
      method: "POST",
      body: fd,
      credentials: "include",
      headers: authHeaders(),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      throw new Error(errorMessage(b, res));
    }
    return res.json();
  },
  settings: () => request("/api/settings"),
  saveSettings: (body) =>
    request("/api/settings", { method: "PUT", body: JSON.stringify(body) }),
  stats: () => request("/api/stats"),
  health: () => request("/api/health"),
  addGame: (body) =>
    request("/api/games", { method: "POST", body: JSON.stringify(body) }),
  deleteGame: (itemId) =>
    request(`/api/games/${itemId}`, { method: "DELETE" }),
  updateGame: (itemId, body) =>
    request(`/api/games/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  addOwned: (itemId, body = {}) =>
    request(`/api/items/${itemId}/owned`, { method: "POST", body: JSON.stringify(body) }),
  removeOwned: (itemId, ownedId) =>
    request(`/api/items/${itemId}/owned/${ownedId}`, { method: "DELETE" }),
  updateOwned: (itemId, ownedId, body) =>
    request(`/api/items/${itemId}/owned/${ownedId}`, { method: "PATCH", body: JSON.stringify(body) }),
  addWanted: (itemId, body = {}) =>
    request(`/api/items/${itemId}/wanted`, { method: "POST", body: JSON.stringify(body) }),
  removeWanted: (itemId) =>
    request(`/api/items/${itemId}/wanted`, { method: "DELETE" }),
};
