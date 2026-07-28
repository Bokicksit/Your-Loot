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
  addCard: (body) =>
    request("/api/cards", { method: "POST", body: JSON.stringify(body) }),
  deleteCard: (itemId) => request(`/api/cards/${itemId}`, { method: "DELETE" }),
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
  settings: () => request("/api/settings"),
  stats: () => request("/api/stats"),
  health: () => request("/api/health"),
  saveSettings: (body) =>
    request("/api/settings", { method: "PUT", body: JSON.stringify(body) }),
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
