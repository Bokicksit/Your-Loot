import { useEffect, useRef, useState } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api.js";
import { Icon } from "../components/Icons.jsx";

/** Sets · Pokédex, the way Cards has Collection · Pokédex · Binders. */
export function LegoSwitch() {
  const chip = (to, label, end = false) => (
    <NavLink to={to} end={end} className={({ isActive }) => `chip ${isActive ? "active" : ""}`}>
      {label}
    </NavLink>
  );
  return (
    <div className="chip-row view-switch">
      {chip("/lego", "Sets", true)}
      {chip("/lego/pokedex", "Pokédex")}
    </div>
  );
}

// Web NFC: Chrome on Android, nothing else.
const canScan = () => typeof window !== "undefined" && "NDEFReader" in window;

/** The LEGO Pokédex.
 *
 *  Every Pokémon LEGO has made, and which you have caught. A catch is a Smart
 *  Tag tapped against the phone: the browser gets the tag's serial number and
 *  nothing more — the Pokémon is in the chip's memory, out of a web page's
 *  reach — so a tile's first tap asks which Pokémon it is, and every tap
 *  after that is a capture. Owning the set can count instead, for an iPhone or
 *  anybody without NFC.
 */
export default function LegoPokedexPage() {
  const [page, setPage] = useState(null);
  const [error, setError] = useState(null);
  const [open, setOpen] = useState(null);       // dex_no showing its panel
  const [scanning, setScanning] = useState(false);
  const [scanMsg, setScanMsg] = useState(null);
  const [pairing, setPairing] = useState(null);  // serial waiting for an answer
  const [other, setOther] = useState("");
  const [caught, setCaught] = useState(null);    // dex_no just captured, for the flash
  const abort = useRef(null);

  const load = () =>
    api.legoDex().then(setPage).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    return () => abort.current?.abort();
  }, []);

  const celebrate = (res) => {
    setPage(res.pokedex);
    setCaught(res.dex_no);
    setOpen(null);
    setScanMsg(`Caught ${res.name}!`);
    // bring the slot into view; a grid of twenty can put it below the fold
    setTimeout(() => {
      document.querySelector(`[data-lego-dex="${res.dex_no}"]`)
        ?.scrollIntoView({ block: "center", behavior: "smooth" });
    }, 50);
    setTimeout(() => setCaught(null), 2400);
  };

  const stopScan = () => {
    abort.current?.abort();
    abort.current = null;
    setScanning(false);
  };

  const startScan = async () => {
    setError(null);
    setScanMsg("Hold a Smart Tag tile to the back of your phone…");
    setPairing(null);
    const ctrl = new AbortController();
    abort.current = ctrl;
    try {
      const reader = new window.NDEFReader();
      reader.onreadingerror = () =>
        setScanMsg("Couldn't read that one — hold it still against the phone and try again.");
      reader.onreading = async (ev) => {
        // one tile per scan: stop listening before the reply comes back, so
        // a tile left on the phone does not fire again and again
        stopScan();
        try {
          const res = await api.legoDexScan(ev.serialNumber);
          if (res.known) celebrate(res);
          else {
            setPairing(ev.serialNumber);
            setScanMsg(null);
          }
        } catch (e) {
          setScanMsg(e.message);
        }
      };
      await reader.scan({ signal: ctrl.signal });
      setScanning(true);
    } catch (e) {
      setScanning(false);
      setScanMsg(
        e.name === "NotAllowedError"
          ? "NFC permission was refused. Allow it for this site in Chrome's settings and try again."
          : e.name === "NotSupportedError"
          ? "This phone's NFC is switched off, or there is none. Turn it on in Settings."
          : e.message
      );
    }
  };

  const pair = async (dex) => {
    try {
      const res = await api.legoDexPair(pairing, dex);
      setPairing(null);
      setOther("");
      celebrate(res);
    } catch (e) {
      setError(e.message);
    }
  };

  const forget = async (tileId) => {
    if (!window.confirm("Forget this tile? The Pokémon is uncaught until a tile is scanned again.")) return;
    setPage(await api.legoDexForget(tileId));
  };

  const flip = async () => {
    setPage(await api.legoDexSettings(!page.by_sets));
  };

  if (!page) {
    return (
      <div>
        <LegoSwitch />
        {error ? <p className="error">{error}</p> : <p className="empty">Loading…</p>}
      </div>
    );
  }

  // the answers a new tile is most likely to be: Pokémon that come with a
  // tile and have not been caught yet
  const likely = page.entries.filter((e) => e.has_tile && !e.captured);
  const CAN_SCAN = canScan();

  return (
    <div className="lego-dex">
      <LegoSwitch />

      <div className="toolbar">
        <span className="lego-dex-count">
          <strong>{page.captured}</strong> / {page.total} caught
        </span>
        {CAN_SCAN ? (
          scanning ? (
            <button className="ghost on" onClick={stopScan}>
              <Icon id="x" />
              Stop
            </button>
          ) : (
            <button className="primary" onClick={startScan}>
              <Icon id="scan" />
              Scan a tile
            </button>
          )
        ) : null}
      </div>

      {!CAN_SCAN && (
        <p className="settings-note">
          Scanning a Smart Tag works in <strong>Chrome on Android</strong> — iPhones don't let a
          web page use NFC. Here, switch on <em>Owning the set counts</em> below to catch the
          Pokémon in the sets you own.
        </p>
      )}

      {scanMsg && <p className={`lego-dex-msg ${caught ? "caught" : ""}`}>{scanMsg}</p>}
      {error && <p className="error">{error}</p>}

      {pairing && (
        <div className="filter-sheet binder-sheet lego-pair">
          <p className="lego-pair-q">
            <strong>A new tile.</strong> Which Pokémon is on it? You only answer this once —
            from now on this tile catches it.
          </p>
          <div className="lego-pair-list">
            {likely.map((e) => (
              <button key={e.dex_no} type="button" className="lego-pair-pick" onClick={() => pair(e.dex_no)}>
                {e.art ? <img src={e.art} alt="" loading="lazy" /> : <span className="placeholder" />}
                <span>{e.name}</span>
                <small>#{String(e.dex_no).padStart(4, "0")}</small>
              </button>
            ))}
          </div>
          <form
            className="lego-pair-other"
            onSubmit={(ev) => {
              ev.preventDefault();
              const n = Number(other);
              if (n >= 1 && n <= 1025) pair(n);
            }}
          >
            <label>
              <span>Not listed? The number printed on the tile</span>
              <input
                type="number" inputMode="numeric" min="1" max="1025"
                placeholder="399" value={other}
                onChange={(ev) => setOther(ev.target.value)}
              />
            </label>
            <div className="sheet-actions">
              <button type="submit" className="primary" disabled={!other}>That one</button>
              <button type="button" className="ghost" onClick={() => setPairing(null)}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="lego-dex-grid">
        {page.entries.map((e) => (
          <div key={e.dex_no} className="lego-dex-cell">
            <button
              type="button"
              data-lego-dex={e.dex_no}
              className={`dex-slot ${e.captured ? "owned" : "unowned"} ${caught === e.dex_no ? "just-caught" : ""}`}
              aria-expanded={open === e.dex_no}
              onClick={() => setOpen(open === e.dex_no ? null : e.dex_no)}
            >
              <span className="dex-no">#{String(e.dex_no).padStart(4, "0")}</span>
              {e.art ? <img src={e.art} alt={e.name} loading="lazy" /> : <span className="placeholder" data-label="" />}
              <span className="name">{e.name}</span>
              <span className="lego-dex-how">
                {e.how === "tile" ? "Scanned" : e.how === "set" ? "Set owned" : e.has_tile ? "" : "No tile"}
              </span>
            </button>
            {open === e.dex_no && (
              <div className="dex-detail lego-dex-detail">
                <h3>{e.name}</h3>
                {e.sets.length > 0 ? (
                  <ul className="lego-dex-sets">
                    {e.sets.map((s) => (
                      <li key={s.number}>
                        <span className="set-abbr">{s.number}</span> {s.name}
                        {s.owned && <em className="where"> · you own it</em>}
                        {!s.tags && <em className="where"> · no Smart Tag</em>}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="settings-note">Caught from a tile in a set this list doesn't know yet.</p>
                )}
                {e.tiles.length > 0 && (
                  <ul className="lego-dex-tiles">
                    {e.tiles.map((t, i) => (
                      <li key={t.id}>
                        <span className="settings-note">
                          Tile {e.tiles.length > 1 ? i + 1 : ""} scanned
                          {t.since ? ` ${new Date(t.since).toLocaleDateString()}` : ""}
                        </span>
                        <button className="ghost tiny" onClick={() => forget(t.id)}>Forget</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="shape-row lego-dex-switch">
        <span className="shape-label">Owning the set counts</span>
        <button type="button" className={`toggle ${page.by_sets ? "on" : ""}`} onClick={flip}>
          {page.by_sets ? "Yes — sets I own catch their Pokémon" : "No — only scanned tiles"}
        </button>
      </div>
    </div>
  );
}
