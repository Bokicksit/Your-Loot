// Thin fetch wrapper. Same-origin paths — nginx (prod) or vite (dev) proxies /api.
async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `${res.status} ${res.statusText}`);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
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
    const res = await fetch("/api/images", { method: "POST", body: fd });
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      throw new Error(b.detail || `${res.status} ${res.statusText}`);
    }
    return res.json();
  },
  cardFacets: (params = {}) =>
    request(`/api/cards/facets?${new URLSearchParams(params)}`),
  cardsSearch: (params) =>
    request(`/api/cards/search?${new URLSearchParams(params)}`),
  pokedex: () => request("/api/cards/pokedex"),
  dexHappy: (dexNo, happy) =>
    request(`/api/cards/pokedex/${dexNo}/happy`, {
      method: "PUT",
      body: JSON.stringify({ happy }),
    }),
  wanted: () => request("/api/wanted"),
  games: (params = {}) =>
    request(`/api/games?${new URLSearchParams(params)}`),
  platforms: () => request("/api/games/platforms"),
  platformsInUse: () => request("/api/games/platforms?in_use=true"),
  igdbSearch: (q) =>
    request(`/api/games/igdb/search?q=${encodeURIComponent(q)}`),
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
  // Retailer image hosts rot and some block hotlinking, so a chosen box-art
  // photo is copied to our own storage. TMDB/IGDB CDNs are stable and stay
  // hotlinked. Falls back to the original URL if the copy fails — a picture
  // that might break later beats no picture.
  localiseImage: async (url) => {
    const stable = /image\.tmdb\.org|igdb\.com/i;
    if (!url || !/^https?:/i.test(url) || stable.test(url)) return url;
    try {
      const { url: local } = await api.fetchImage(url);
      return local;
    } catch {
      return url;
    }
  },
  books: (params = {}) => request(`/api/books?${new URLSearchParams(params)}`),
  bookFacets: () => request("/api/books/facets"),
  addBook: (body) =>
    request("/api/books", { method: "POST", body: JSON.stringify(body) }),
  updateBook: (itemId, body) =>
    request(`/api/books/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteBook: (itemId) => request(`/api/books/${itemId}`, { method: "DELETE" }),
  openLibrarySearch: (params) =>
    request(`/api/books/search?${new URLSearchParams(params)}`),
  records: (params = {}) => request(`/api/records?${new URLSearchParams(params)}`),
  recordFacets: () => request("/api/records/facets"),
  addRecord: (body) =>
    request("/api/records", { method: "POST", body: JSON.stringify(body) }),
  updateRecord: (itemId, body) =>
    request(`/api/records/${itemId}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteRecord: (itemId) => request(`/api/records/${itemId}`, { method: "DELETE" }),
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
  comicVineSearch: (params) =>
    request(`/api/comics/search?${new URLSearchParams(params)}`),
  backupUrl: "/api/backup",
  restoreBackup: async (file) => {
    const fd = new FormData();
    fd.append("file", file);
    // no Content-Type header: the browser sets the multipart boundary
    const res = await fetch("/api/backup/restore", { method: "POST", body: fd });
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      throw new Error(b.detail || `${res.status} ${res.statusText}`);
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
