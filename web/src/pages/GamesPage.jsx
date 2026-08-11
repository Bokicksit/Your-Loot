import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import ArtOptions from "../components/ArtOptions.jsx";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { Icon } from "../components/Icons.jsx";
import { TagChips, TagEditor, TagFilter } from "../components/Tags.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { useSettings, useListPref } from "../settings.jsx";
import { cleanGameTitle, firstHits, queryLadder } from "../upc.js";
import { GAME_COMPLETENESS, labelFor, shortFor, withUnknown } from "../vocab.js";
import ViewToggle, { useTileView } from "../components/ViewToggle.jsx";

const REGIONS = ["NTSC-U", "PAL", "NTSC-J", "Region-free"];
const CONDITIONS = ["Mint", "Good", "Fair", "Poor"];

// `region` is overwritten from Settings → default region on every fresh form
const EMPTY_FORM = {
  title: "",
  platform_id: "",
  region: "NTSC-U",
  is_hardware: false,
  igdb_id: null,
  image_url: null,
  tags: [],
  notes: "",
  own: true, // most additions are things already on the shelf
  completeness: "CIB",
  condition: "Good",
  // info-panel metadata, filled by an IGDB pick
  summary: null,
  release_year: null,
  genres: null,
  developer: null,
  publisher: null,
};

// best-effort map from IGDB platform names to our lookup table.
// Order matters: exact, then prefix ("Super Nintendo" prefixes "Super Nintendo
// Entertainment System"), then substring — plain substring alone would map
// SNES to NES, since "…Nintendo Entertainment System" contains the NES name.
function matchPlatform(igdbNames, platforms) {
  for (const name of igdbNames) {
    const n = name.toLowerCase();
    const exact = platforms.find((p) => p.name.toLowerCase() === n);
    if (exact) return exact.id;
    const prefix = platforms
      .filter((p) => n.startsWith(p.name.toLowerCase()))
      .sort((a, b) => b.name.length - a.name.length)[0];
    if (prefix) return prefix.id;
    // theirs contains ours ("…Entertainment System" ⊃ "Super Nintendo"):
    // longest of ours wins. Ours contains theirs ("Nintendo Wii" ⊃ "Wii"):
    // shortest of ours wins — "Wii" must not match "Nintendo Wii U".
    const contained = platforms
      .filter((p) => n.includes(p.name.toLowerCase()))
      .sort((a, b) => b.name.length - a.name.length)[0];
    if (contained) return contained.id;
    const containing = platforms
      .filter((p) => p.name.toLowerCase().includes(n))
      .sort((a, b) => a.name.length - b.name.length)[0];
    if (containing) return containing.id;
  }
  return "";
}

// all our platform ids a game was released on (for restricting the dropdown)
function matchAllPlatforms(igdbNames, platforms) {
  const ids = new Set();
  for (const name of igdbNames) {
    const id = matchPlatform([name], platforms);
    if (id) ids.add(id);
  }
  return [...ids];
}

// Shared wording, so every collection asks the same question the same way.
// Returns false only if the person says no.
async function confirmDuplicate(scope, title) {
  let matches = [];
  try {
    ({ matches } = await api.duplicates(scope, title));
  } catch {
    return true; // the check failing must never block an add
  }
  if (!matches.length) return true;
  const m = matches[0];
  const copies = m.copies === 1 ? "1 copy" : `${m.copies} copies`;
  return confirm(
    `${m.title} is already in this collection` +
      (m.detail ? ` — ${m.detail}` : "") +
      `, with ${copies}.

Add another?`
  );
}

export default function GamesPage() {
  const [games, setGames] = useState([]);
  const [total, setTotal] = useState(0);
  const [platforms, setPlatforms] = useState([]);
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("games");
  const [platformFilter, setPlatformFilter] = useListPref("games", "platformFilter", ""); // system; genre later
  const [usedPlatforms, setUsedPlatforms] = useState([]); // only what's in the collection
  const [tagFilter, setTagFilter] = useListPref("games", "tagFilter", "");
  // bumped whenever tags change, so the filter re-reads its counts
  const [tagsChanged, setTagsChanged] = useState(0);
  const [sort, setSort] = useListPref("games", "sort", "title"); // title | platform | added
  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState("search"); // search -> details
  const { settings } = useSettings();
  // a blank form starts at whatever region you told Settings you mostly buy
  const blankForm = () => ({
    ...EMPTY_FORM,
    region: settings?.default_region || EMPTY_FORM.region,
  });
  const [form, setForm] = useState(blankForm);
  const [results, setResults] = useState(null); // null = no search yet
  const [art, setArt] = useState([]); // artwork candidates: box photos + cover
  const [allowedPlatforms, setAllowedPlatforms] = useState([]); // from IGDB pick
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  // keep one entry per url, box photos first — they're the copy you own
  const mergeArt = (extra) =>
    setArt((prev) => {
      const seen = new Set(prev.map((a) => a.url));
      return [...prev, ...extra.filter((a) => a.url && !seen.has(a.url))];
    });

  useEffect(() => {
    api.platforms().then(setPlatforms);
  }, []);

  const load = () => {
    // hardware lives on its own tab now — this page is games only
    const params = { sort, is_hardware: false };
    if (search) params.search = search;
    if (tagFilter) params.tag = tagFilter;
    if (platformFilter) params.platform_id = platformFilter;
    api
      .games(params)
      .then((d) => {
        setGames(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    // keep the system filter honest: only platforms with entries, with counts
    api.platformsInUse().then((used) => {
      setUsedPlatforms(used);
      if (platformFilter && !used.some((p) => String(p.id) === String(platformFilter))) {
        setPlatformFilter(""); // selected system's last entry was deleted
      }
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, platformFilter, sort, tagFilter, tagsChanged]);

  // Same ladder the barcode path uses. A typed title has the same trouble a
  // scanned one does — people type what's printed on the box, subtitle and
  // all — so one exact query is exactly the wrong thing to try only once.
  const igdbSearch = async () => {
    if (form.title.trim().length < 2 || searching) return;
    setSearching(true);
    setResults(null); // clear the old hits so the status stands alone
    try {
      setResults(await firstHits(queryLadder(form.title), (q) => api.igdbSearch(q)));
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  // barcode (CIB boxes) → product title → auto-run the IGDB search
  const onBarcode = async (code) => {
    try {
      const res = await api.barcodeLookup(code);
      if (!res.found) {
        alert("No product match for that barcode — type the title instead.");
        return;
      }
      const raw = res.titles[0].title;
      const title = cleanGameTitle(raw) || raw;
      // retailer photos of the actual box — IGDB's cover is the game's key
      // art, which doesn't distinguish a Player's Choice reprint from the
      // original release
      const boxArt = (res.titles[0].images || []).map((url) => ({ url, kind: "box" }));
      setArt(boxArt);
      setForm((f) => ({
        ...f,
        title,
        igdb_id: null,
        image_url: boxArt[0]?.url || null,
      }));
      setSearching(true);
      try {
        setResults(await firstHits(queryLadder(title), (q) => api.igdbSearch(q)));
      } finally {
        setSearching(false);
      }
    } catch (e) {
      alert(e.message);
    }
  };

  // Shop listings by name, for the systems the scan archive doesn't cover.
  // Runs only when there's no scan, and only on an explicit pick — it shares
  // the barcode service's daily budget.
  const findRetailArt = async (title) => {
    const term = cleanGameTitle(title) || title;
    if (!term || term.length < 3) return;
    try {
      const { items } = await api.productSearch(term);
      const shots = (items || []).flatMap((i) => i.images).slice(0, 6);
      if (!shots.length) return;
      mergeArt(shots.map((url) => ({ url, kind: "box" })));
      setForm((f) => ({
        ...f,
        image_url:
          !f.image_url || /igdb\.com/i.test(f.image_url) ? shots[0] : f.image_url,
      }));
    } catch {
      /* artwork is a bonus */
    }
  };

  // A scan of the actual box, which IGDB's key art isn't. Needs the platform,
  // so it runs once one is settled on rather than at pick time; it's offered
  // alongside the other art instead of replacing whatever you already chose.
  // The artwork these lookups pick is a suggestion, and a suggestion should
  // stand aside for a better one. Tracking what we chose last lets a second
  // lookup replace it, while anything picked off the strip by hand is left
  // exactly where it is.
  const autoArt = useRef(null);

  const findBoxart = async (title, platformId, region) => {
    if (!title || !platformId) return;
    try {
      const { url } = await api.gameBoxart({
        title,
        platform_id: platformId,
        ...(region ? { region } : {}),
      });
      if (!url) {
        // libretro stops around the Xbox 360, so anything newer has no box
        // scan at all. A shop listing carries a photograph of the case, which
        // is still the thing on your shelf rather than the key art.
        findRetailArt(title);
        return;
      }
      mergeArt([{ url, kind: "box" }]);
      // and take the slot. A box scan is a photograph of the thing on your
      // shelf; IGDB's cover is the game's key art — the same picture for the
      // original, the reprint and the download. Offering the scan but leaving
      // the key art selected meant everything still looked like key art unless
      // you noticed the strip. Anything you chose yourself is left alone.
      setForm((f) => {
        const ours =
          !f.image_url || /igdb\.com/i.test(f.image_url) || f.image_url === autoArt.current;
        if (!ours) return f;
        autoArt.current = url;
        return { ...f, image_url: url };
      });
    } catch {
      /* box art is a bonus; never let it break the add flow */
    }
  };

  const pickResult = (r) => {
    // restrict the platform dropdown to systems this game shipped on
    const allowed = matchAllPlatforms(r.platforms, platforms);
    setAllowedPlatforms(allowed);
    if (r.cover_url) mergeArt([{ url: r.cover_url, kind: "poster" }]);
    const picked = matchPlatform(r.platforms, platforms) || "";
    const rawTitle = r.year ? `${r.title} (${r.year})` : r.title;
    findBoxart(rawTitle, picked, form.region);
    setForm({
      ...form,
      title: r.year ? `${r.title} (${r.year})` : r.title,
      igdb_id: r.igdb_id,
      // a box photo from the barcode is the copy you own; IGDB's cover only
      // fills in when there isn't one
      image_url: form.image_url || r.cover_url,
      platform_id: picked,
      summary: r.summary || null,
      release_year: r.year ? Number(r.year) : null,
      genres: r.genres?.length ? r.genres.join(", ") : null,
      developer: r.developer || null,
      publisher: r.publisher || null,
    });
    setResults(null);
    setStep("details"); // picked something — on to describing your copy
  };

  // settings arrive after mount, so the default region is picked up on open
  const openForm = () => {
    setForm(blankForm());
    setArt([]);
    setResults(null);
    setAllowedPlatforms([]);
    setStep("search");
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setResults(null);
  };

  const submit = async (e) => {
    e.preventDefault();
    try {
      // Ask before making a second one. Two identical rows take a moment
      // to create and a while to notice.
      if (!(await confirmDuplicate("games", form.title))) return;

      const created = await api.addGame({
        title: form.title,
        platform_id: form.platform_id ? Number(form.platform_id) : null,
        region: form.region || null,
        is_hardware: form.is_hardware,
        igdb_id: form.igdb_id,
        image_url: await api.localiseImage(form.image_url),
        notes: form.notes.trim() || null,
        summary: form.summary,
        release_year: form.release_year,
        genres: form.genres,
        developer: form.developer,
        publisher: form.publisher,
      });
      // after the create, because a tag needs something to hang on
      if (form.tags.length) {
        await api.setItemTags(created.id, "games", form.tags);
        setTagsChanged((n) => n + 1);
      }
      if (form.own) {
        // catalog + first copy in one go
        await api.addOwned(created.id, {
          condition: form.condition,
          completeness: form.completeness,
        });
      } else {
        // "I want it": straight to the wanted list — it won't appear in the
        // library until a copy is owned, so jump there for visible feedback
        await api.addWanted(created.id);
      }
      const wantMode = !form.own;
      setForm(blankForm());
      setResults(null);
      setArt([]);
      setAllowedPlatforms([]);
      setShowForm(false);
      if (wantMode) {
        navigate("/wanted");
      } else {
        load();
      }
    } catch (err) {
      alert(err.message);
    }
  };

  const patchGame = (id, status) =>
    setGames((gs) =>
      gs.map((g) =>
        g.id === id ? { ...g, owned: status.owned, wanted: status.wanted, tags: status.tags ?? game.tags } : g
      )
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search games…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button className="primary" onClick={openForm} title="Add to library">
          <Icon id="plus" />
          Add
        </button>
      </div>

      <div className="chip-row">
        <select
          className="chip-select"
          title="Filter by system"
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
        >
          <option value="">All systems</option>
          {usedPlatforms.map((p) => (
            <option key={p.id} value={p.id}>
              {p.abbreviation || p.name} ({p.count})
            </option>
          ))}
        </select>
        <TagFilter
          scope="games"
          value={tagFilter}
          onChange={setTagFilter}
          reloadKey={tagsChanged}
        />
        <select
          className="chip-select"
          title="Sort"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
        >
          <option value="title">A–Z</option>
          <option value="platform">By system</option>
          <option value="year">By year</option>
          <option value="added">Last added</option>
          <option value="oldest">First added</option>
        </select>
        <ViewToggle module="games" />
      </div>

      <AddSheet
        open={showForm && step === "search"}
        title="Find a game"
        onClose={closeForm}
      >
        <div className="form-row">
          <input
            type="text"
            className="grow"
            autoFocus
            placeholder="Title to search for"
            value={form.title}
            onChange={(e) => {
              // manual edits detach the IGDB link/cover/metadata
              setForm({
                ...form,
                title: e.target.value,
                igdb_id: null,
                image_url: null,
                summary: null,
                release_year: null,
                genres: null,
                developer: null,
                publisher: null,
              });
              setAllowedPlatforms([]);
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                igdbSearch();
              }
            }}
          />
          <button type="button" className="ghost" onClick={igdbSearch} disabled={searching}>
            {searching ? "…" : "Search"}
          </button>
          <BarcodeScan onCode={onBarcode} />
        </div>
        {searching && <Searching />}
        {results && (
          <ul className="igdb-results">
            {results.length === 0 && (
              <li style={{ cursor: "default", color: "var(--text-mute)" }}>
                No IGDB matches.
              </li>
            )}
            {results.map((r) => (
              <li key={r.igdb_id} onClick={() => pickResult(r)}>
                {r.cover_url ? (
                  <img src={r.cover_url} alt="" loading="lazy" />
                ) : (
                  <span className="placeholder" data-label="" />
                )}
                <span className="game-text">
                  <strong>{r.title}</strong>
                  <small>{r.platforms.slice(0, 4).join(", ")}</small>
                </span>
                <span className="year">{r.year || ""}</span>
              </li>
            ))}
          </ul>
        )}
        <ByHand onClick={() => setStep("details")} />
      </AddSheet>

      <AddSheet
        open={showForm && step === "details"}
        title="Add to library"
        onClose={closeForm}
        onBack={() => setStep("search")}
      >
        <form className="add-form" onSubmit={submit}>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Title as you want it filed"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
          </div>
          <div className="form-row">
            <select
              value={form.platform_id}
              onChange={(e) => {
                setForm({ ...form, platform_id: e.target.value });
                // the box scan is per-system, so naming the system is exactly
                // when it becomes findable
                findBoxart(form.title, e.target.value, form.region);
              }}
            >
              <option value="">Platform…</option>
              {/* IGDB's suggestion leads, but never locks you in. Its entries
                  are per-platform, so searching a game that saw a later port
                  can match the port and offer only that system — and then the
                  cartridge on your shelf has no system to pick, and no box
                  scan to find, because the scan is looked up per system. */}
              {form.igdb_id && allowedPlatforms.length > 0 ? (
                <>
                  <optgroup label="Released on">
                    {platforms
                      .filter((p) => allowedPlatforms.includes(p.id))
                      .map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                  </optgroup>
                  <optgroup label="All systems">
                    {platforms
                      .filter((p) => !allowedPlatforms.includes(p.id))
                      .map((p) => (
                        <option key={p.id} value={p.id}>{p.name}</option>
                      ))}
                  </optgroup>
                </>
              ) : (
                platforms.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))
              )}
            </select>
            <select
              value={form.region}
              onChange={(e) => setForm({ ...form, region: e.target.value })}
            >
              <option value="">Region…</option>
              {REGIONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </div>
          <ArtOptions
            options={art}
            value={form.image_url}
            onChange={(url) => setForm({ ...form, image_url: url })}
          />
          <div className="form-row">
            <ImagePicker
              value={form.image_url}
              label="Box photo"
              onChange={(url) => setForm({ ...form, image_url: url })}
            />
          </div>
          {/* last of the fields: a tag is what you think of once the rest
              is filled in */}
          <div className="form-row">
            <TagEditor
              scope="games"
              value={form.tags}
              onChange={(tags) => setForm({ ...form, tags })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Note (optional)"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
          </div>
          <div className="form-row">
            <button
              type="button"
              className={`toggle ${form.own ? "on" : ""}`}
              onClick={() => setForm({ ...form, own: !form.own })}
            >
              {form.own ? "I own it" : "I want it"}
            </button>
            <select
              title="What you have"
              disabled={!form.own}
              value={form.completeness}
              onChange={(e) => setForm({ ...form, completeness: e.target.value })}
            >
              {GAME_COMPLETENESS.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <select
              title="Condition"
              disabled={!form.own}
              value={form.condition}
              onChange={(e) => setForm({ ...form, condition: e.target.value })}
            >
              {CONDITIONS.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            {form.igdb_id && (
              <span className="igdb-linked">
                <Icon id="link" />
                IGDB #{form.igdb_id} linked
              </span>
            )}
            <button type="submit" className="primary" style={{ marginLeft: "auto" }}>
              <Icon id="plus" />
              Add
            </button>
          </div>
        </form>
      </AddSheet>

      {error && (
        <p className="error">
          <Icon id="alert" />
          {error}
        </p>
      )}
      {!error && loaded && games.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="pad" /></span>
          <strong>No games yet</strong>
          <p>Hit Add and search IGDB, or enter consoles and carts by hand.</p>
        </div>
      )}

      <div className={`game-list ${tiles ? "as-tiles" : ""}`}>
        {games.map((g) => (
          <GameRow
            key={g.id}
            game={g}
            platforms={platforms}
            onChange={patchGame}
            onReload={load}
            onTagsChanged={() => setTagsChanged((n) => n + 1)}
          />
        ))}
      </div>
    </div>
  );
}

// Shows /platforms/<ABBR>.svg when that file exists in web/public/platforms/
// (drop in any logo pack you like); falls back to a styled abbreviation tag.
function PlatformBadge({ abbr, name }) {
  const [hasLogo, setHasLogo] = useState(true);
  const label = abbr || name;
  if (!label) return null;
  return hasLogo ? (
    <img
      className="plat-logo"
      src={`/platforms/${label}.svg`}
      alt={label}
      title={name || label}
      onError={() => setHasLogo(false)}
    />
  ) : (
    <span className="plat-badge" title={name || label}>{label}</span>
  );
}

function GameRow({ game, platforms, onChange, onReload , onTagsChanged}) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null); // owned id being edited
  const [editVals, setEditVals] = useState({ completeness: "CIB", condition: "Good" });
  const [entryOpen, setEntryOpen] = useState(false); // entry (catalog) editor
  const [entry, setEntry] = useState({});
  const [infoOpen, setInfoOpen] = useState(false); // expandable detail card
  const rowRef = useRef(null);
  const entryInit = useRef(null); // what the editor opened with, to spot edits
  useDismiss(
    infoOpen || entryOpen || editing !== null,
    () => {
      setInfoOpen(false);
      setEntryOpen(false);
      setEditing(null);
    },
    [rowRef],
    () => keepOpen(entry, entryInit.current, entryOpen, game.title),
  );

  const a = game.attrs;
  const infoLine = [
    a.release_year,
    a.genres,
    a.developer && `Dev: ${a.developer}`,
    a.publisher && a.publisher !== a.developer && `Pub: ${a.publisher}`,
  ]
    .filter(Boolean)
    .join("  ·  ");

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      const status = await fn();
      onChange(game.id, status);
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const copyLabel = (o) =>
    [o.completeness && shortFor(GAME_COMPLETENESS, o.completeness), o.condition]
      .filter(Boolean)
      .join(" · ");

  const removeCopy = (o) => {
    if (!confirm(`Remove this copy of ${game.title} (${copyLabel(o) || "copy"})?`)) return;
    run(() => api.removeOwned(game.id, o.id));
  };

  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      completeness: o.completeness || "CIB",
      condition: o.condition || "Good",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const status = await api.updateOwned(game.id, editing, editVals);
      setEditing(null);
      return status;
    });
  const openEntry = () => {
    const vals = {
      title: game.title,
      platform_id: game.attrs.platform_id ? String(game.attrs.platform_id) : "",
      region: game.attrs.region || "",
      is_hardware: game.attrs.is_hardware,
      image_url: game.image_url,
      tags: game.tags || [],
      notes: game.notes || "",
    };
    entryInit.current = vals;
    setEntry(vals);
    setEntryOpen(true);
  };

  const saveEntry = async () => {
    if (busy || !entry.title.trim()) return;
    setBusy(true);
    try {
      await api.updateGame(game.id, {
        title: entry.title.trim(),
        platform_id: entry.platform_id ? Number(entry.platform_id) : null,
        region: entry.region || null,
        is_hardware: entry.is_hardware,
        image_url: await api.localiseImage(entry.image_url),
        notes: entry.notes.trim() || null,
      });
      // Staged with the rest of the form, so Cancel discards a tag the
      // same way it discards a retyped title.
      await api.setItemTags(game.id, "games", entry.tags);
      onTagsChanged?.();
      setEntryOpen(false);
      onReload(); // re-fetch: sort order and filter counts may have changed
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  // no want-star here: wanting happens at add time ("I want it") and is
  // managed on the Wanted tab — library rows are for owned copies
  const del = async () => {
    if (!confirm(`Delete "${game.title}" and its records?`)) return;
    await api.deleteGame(game.id);
    onReload();
  };

  return (
    <div
      ref={rowRef}
      className={`game-row ${game.owned.length ? "row-owned" : ""} ${infoOpen || entryOpen ? "open" : ""}`}
    >
      {game.image_url ? (
        <img
          className="game-cover"
          src={game.image_url}
          alt=""
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={() => setInfoOpen(!infoOpen)}
        />
      ) : (
        <span
          className="game-icon"
          style={{ cursor: "pointer" }}
          onClick={() => setInfoOpen(!infoOpen)}
        >
          <Icon id={game.attrs.is_hardware ? "pad" : "disc"} />
        </span>
      )}
      <span
        className="game-text"
        style={{ cursor: "pointer" }}
        onClick={() => setInfoOpen(!infoOpen)}
      >
        <strong>{game.title}</strong>
        <small className="game-meta">
          <PlatformBadge abbr={game.attrs.platform_abbr} name={game.attrs.platform_name} />
          {game.attrs.region && <span>{game.attrs.region}</span>}
        </small>
        {game.owned.length > 0 && (
          <span className="copy-chips">
            {game.owned.map((o) => (
              <span
                key={o.id}
                className="chip copy"
                onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
                title="Edit this copy"
              >
                <Icon id="pencil" />
                {copyLabel(o) || "set condition…"}
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    removeCopy(o);
                  }}
                  title="Remove this copy"
                >
                  <Icon id="x" />
                </button>
              </span>
            ))}
          </span>
        )}
      </span>
      <span className="row-buttons">
        <button
          className="ghost icon"
          onClick={() => (entryOpen ? setEntryOpen(false) : openEntry())}
          title="Edit entry"
        >
          <Icon id="pencil" />
        </button>
        <button className="ghost icon danger" onClick={del} title="Delete entry">
          <Icon id="trash" />
        </button>
      </span>
      {infoOpen && (
        <span className="entry-edit game-info">
          <div className="expand-card">
            {game.image_url && (
              <img className="expand-cover" src={game.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{game.title}</span>
              <span className="expand-sub">
                {[a.platform_name, a.region, a.is_hardware && "Hardware"]
                  .filter(Boolean)
                  .join(" · ") || "No system set"}
              </span>
              {infoLine && <span className="game-info-line">{infoLine}</span>}
            </div>
            {/* the system, not the region: a region code is something almost
                no seller writes into a listing title */}
            <EbayLink title={game.title} terms={[a.platform_name]} />
          </div>
          <TagChips tags={game.tags} />
          {/* your own words about the thing, not about one copy */}
          {game.notes && <p className="game-summary">{game.notes}</p>}
          {a.summary && <p className="game-summary">{a.summary}</p>}
        </span>
      )}
      {entryOpen && (
        <span className="entry-edit">
          <div className="form-row">
            <input
              type="text"
              className="grow"
              value={entry.title}
              onChange={(e) => setEntry({ ...entry, title: e.target.value })}
            />
          </div>
          <div className="form-row">
            <select
              value={entry.platform_id}
              onChange={(e) => setEntry({ ...entry, platform_id: e.target.value })}
            >
              <option value="">Platform…</option>
              {platforms.map((p) => (
                <option key={p.id} value={p.id}>{p.name}</option>
              ))}
            </select>
            <select
              value={entry.region}
              onChange={(e) => setEntry({ ...entry, region: e.target.value })}
            >
              <option value="">Region…</option>
              {REGIONS.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <button
              type="button"
              className={`toggle ${entry.is_hardware ? "on" : ""}`}
              onClick={() => setEntry({ ...entry, is_hardware: !entry.is_hardware })}
            >
              Hardware
            </button>
          </div>
          <div className="form-row">
            <TagEditor
              scope="games"
              id={game.id}
              value={entry.tags}
              onChange={(tags) => setEntry({ ...entry, tags })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Note (optional)"
              value={entry.notes}
              onChange={(e) => setEntry({ ...entry, notes: e.target.value })}
            />
          </div>
          <div className="form-row">
            <ImagePicker
              value={entry.image_url}
              label="Box photo"
              onChange={(url) => setEntry({ ...entry, image_url: url })}
            />
            <button
              className="primary icon"
              style={{ marginLeft: "auto" }}
              onClick={saveEntry}
              disabled={busy}
              title="Save"
            >
              <Icon id="check" />
            </button>
            <button className="ghost icon" onClick={() => setEntryOpen(false)} title="Cancel">
              <Icon id="x" />
            </button>
          </div>
        </span>
      )}
      {editing !== null && (
        <span className="copy-edit">
          <select
            title="What you have"
            value={editVals.completeness}
            onChange={(e) => setEditVals({ ...editVals, completeness: e.target.value })}
          >
            {withUnknown(GAME_COMPLETENESS, editVals.completeness).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <select
            value={editVals.condition}
            onChange={(e) => setEditVals({ ...editVals, condition: e.target.value })}
          >
            {CONDITIONS.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
          <button className="primary icon" onClick={saveEdit} disabled={busy} title="Save">
            <Icon id="check" />
          </button>
          <button className="ghost icon" onClick={() => setEditing(null)} title="Cancel">
            <Icon id="x" />
          </button>
        </span>
      )}
    </div>
  );
}
