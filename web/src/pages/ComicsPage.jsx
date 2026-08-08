import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import useDismiss, { keepOpen } from "../useDismiss.js";
import AddSheet, { ByHand, Searching } from "../components/AddSheet.jsx";
import BarcodeScan from "../components/BarcodeScan.jsx";
import EbayLink from "../components/EbayLink.jsx";
import { Icon } from "../components/Icons.jsx";
import ImagePicker from "../components/ImagePicker.jsx";
import { comicQuery } from "../upc.js";
import {
  COMIC_GRADERS,
  COMIC_GRADES,
  COMIC_SLAB_GRADES,
  labelFor,
  withUnknown,
} from "../vocab.js";
import ViewToggle, { useTileView } from "../components/ViewToggle.jsx";
import { useListPref } from "../settings.jsx";

const EMPTY_FORM = {
  title: "",
  series: "",
  issue_number: "",
  volume_year: "",
  publisher: "",
  cover_year: "",
  variant: "",
  creators: "",
  barcode: "",
  blurb: null,
  image_url: null,
  own: true,
  condition: "VF",
  grader: "",
  grade: "",
};

// A slabbed book is described by its slab; a raw one by its grade.
const copyLabel = (o) =>
  o.grader && o.grade
    ? `${o.grader} ${o.grade}`
    : o.condition
      ? `${labelFor(COMIC_GRADES, o.condition)} (raw)`
      : "";

export default function ComicsPage() {
  const [comics, setComics] = useState([]);
  const [total, setTotal] = useState(0);
  const [facets, setFacets] = useState({ series: [], publishers: [] });
  const [search, setSearch] = useState("");
  const [tiles] = useTileView("comics");
  const [seriesFilter, setSeriesFilter] = useListPref("comics", "seriesFilter", "");
  const [publisherFilter, setPublisherFilter] = useListPref("comics", "publisherFilter", "");
  const [sort, setSort] = useListPref("comics", "sort", "series");
  const [showForm, setShowForm] = useState(false);
  const [step, setStep] = useState("search"); // search -> details
  const [form, setForm] = useState(EMPTY_FORM);
  const [results, setResults] = useState(null);
  const [runs, setRuns] = useState(null); // which run a scanned barcode belongs to
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    const params = { sort };
    if (search) params.search = search;
    if (seriesFilter) params.series = seriesFilter;
    if (publisherFilter) params.publisher = publisherFilter;
    api
      .comics(params)
      .then((d) => {
        setComics(d.items);
        setTotal(d.total);
        setError(null);
        setLoaded(true);
      })
      .catch((e) => setError(e.message));
    api.comicFacets().then((f) => {
      setFacets(f);
      const gone = (list, v) => v && !list.some((x) => x.value === v);
      if (gone(f.series, seriesFilter)) setSeriesFilter("");
      if (gone(f.publishers, publisherFilter)) setPublisherFilter("");
    });
  };

  useEffect(() => {
    const t = setTimeout(load, 250);
    return () => clearTimeout(t);
  }, [search, seriesFilter, publisherFilter, sort]);

  const lookup = async (params) => {
    setSearching(true);
    setResults(null); // clear the old hits so the status stands alone
    try {
      setResults(await api.comicVineSearch(params));
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  // Comic Vine has no barcode endpoint at all — it indexes issues, and no key
  // changes that. So the scan takes the long way round: the retail database
  // knows what the barcode is, and its product title usually carries the
  // series and issue number, which is exactly what Comic Vine can search on.
  // The digits are kept either way; they're worth having on the entry even
  // when nothing recognises them.
  /** A run picked from the list: this is where the title and the year come
   *  from, and the only two things a comic's barcode can actually tell you. */
  const pickRun = (run) => {
    setRuns(null);
    setForm((f) => ({
      ...f,
      series: run.name,
      title: f.title || run.name,
      volume_year: run.start_year || "",
      publisher: run.publisher || f.publisher,
    }));
  };

  const onBarcode = async (code) => {
    // The small five-digit symbol beside the main barcode encodes the issue,
    // the cover and the printing. Scanners read it inconsistently, shops don't
    // print it on every book, and the number is on the cover in your hand
    // anyway — so it fills the issue in when it arrives and is never required.
    if (/^\d{5}$/.test(code)) {
      setForm((f) => ({ ...f, issue_number: String(Number(code.slice(0, 3))) }));
      return;
    }

    setForm((f) => ({ ...f, barcode: code }));
    setRuns(null);
    let raw = null;
    try {
      const res = await api.barcodeLookup(code);
      raw = res.found ? res.titles[0].title : null;
    } catch (e) {
      alert(e.message);
      return;
    }
    if (!raw) {
      alert(
        "No product match for that barcode — comics databases don't index " +
          "them. The digits are saved; search by series and issue."
      );
      return;
    }
    const guess = comicQuery(raw);
    if (!guess) {
      setForm((f) => ({ ...f, title: f.title || raw }));
      alert(`That barcode is "${raw}" — fill the series and issue in by hand.`);
      return;
    }

    // Every issue of a run carries the same main barcode, so the scan names
    // the run and not the issue. The run is worth having on its own: it is
    // the comic's title and the year that tells five Guardians of the Galaxy
    // apart. Comic Vine knows the runs; ask it, rather than trusting whatever
    // issue the shop's listing happened to be selling.
    setForm((f) => ({ ...f, series: guess.series, title: f.title || guess.series }));
    setSearching(true);
    try {
      const found = await api.comicRuns(guess.series);
      if (found.length === 1) {
        pickRun(found[0]);
      } else if (found.length) {
        setRuns(found);
      } else {
        alert(`Scanned "${guess.series}" — Comic Vine has no run by that name.`);
      }
    } catch (e) {
      alert(e.message);
    } finally {
      setSearching(false);
    }
  };

  // Series and issue go over as separate fields so the API can search the run
  // rather than the whole database — the only way to say which Guardians of
  // the Galaxy #1 you mean. The year narrows it further when you know it.
  const textSearch = () => {
    const series = form.series.trim() || form.title.trim();
    const issue = form.issue_number.trim();
    if (series.length < 2 && issue.length < 1) return;
    const params = {};
    if (series) params.series = series;
    if (issue) params.issue = issue;
    if (form.volume_year) params.year = form.volume_year;
    lookup(params);
  };

  const pickResult = (r) => {
    setForm((f) => ({
      ...f,
      title: r.title || f.title,
      series: r.series || "",
      issue_number: r.issue_number || "",
      volume_year: r.volume_year || "",
      cover_year: r.cover_year || "",
      blurb: r.blurb || null,
      image_url: r.image_url || null,
    }));
    setResults(null);
    setStep("details");
  };

  const openForm = () => {
    setForm(EMPTY_FORM);
    setResults(null);
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
      const created = await api.addComic({
        title: form.title,
        series: form.series.trim() || null,
        issue_number: form.issue_number.trim() || null,
        volume_year: form.volume_year ? Number(form.volume_year) : null,
        publisher: form.publisher.trim() || null,
        cover_year: form.cover_year ? Number(form.cover_year) : null,
        variant: form.variant.trim() || null,
        creators: form.creators.trim() || null,
        barcode: form.barcode.trim() || null,
        blurb: form.blurb,
        image_url: form.image_url,
      });
      if (form.own) {
        await api.addOwned(created.id, {
          condition: form.condition,
          grader: form.grader || null,
          grade: form.grader ? form.grade || null : null,
        });
      } else {
        await api.addWanted(created.id);
      }
      const wantMode = !form.own;
      setForm(EMPTY_FORM);
      setResults(null);
      setShowForm(false);
      if (wantMode) navigate("/wanted");
      else load();
    } catch (err) {
      alert(err.message);
    }
  };

  const patchComic = (id, status) =>
    setComics((cs) =>
      cs.map((c) => (c.id === id ? { ...c, owned: status.owned, wanted: status.wanted } : c))
    );

  return (
    <div>
      <div className="toolbar">
        <input
          type="search"
          placeholder="Search series, title or creator…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <span className="count">{total}</span>
        <button className="primary" onClick={openForm} title="Add an issue">
          <Icon id="plus" />
          Add
        </button>
      </div>

      <div className="chip-row">
        {facets.series.length > 0 && (
          <select
            className="chip-select"
            value={seriesFilter}
            onChange={(e) => setSeriesFilter(e.target.value)}
          >
            <option value="">All series</option>
            {facets.series.map((s) => (
              <option key={s.value} value={s.value}>
                {s.value} ({s.count})
              </option>
            ))}
          </select>
        )}
        {facets.publishers.length > 0 && (
          <select
            className="chip-select"
            value={publisherFilter}
            onChange={(e) => setPublisherFilter(e.target.value)}
          >
            <option value="">All publishers</option>
            {facets.publishers.map((p) => (
              <option key={p.value} value={p.value}>
                {p.value} ({p.count})
              </option>
            ))}
          </select>
        )}
        <select
          className="chip-select"
          title="Sort"
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          style={{ marginLeft: "auto" }}
        >
          <option value="series">By series &amp; issue</option>
          <option value="title">A–Z</option>
          <option value="publisher">By publisher</option>
          <option value="year">By cover year</option>
          <option value="added">Last added</option>
          <option value="oldest">First added</option>
        </select>
        <ViewToggle module="comics" />
      </div>

      <AddSheet open={showForm && step === "search"} title="Find an issue" onClose={closeForm}>
          {/* three fields plus the scan button is too much for a phone on one
              line, so this row is allowed to wrap rather than crush the series
              name down to the width of an issue number */}
          <div className="form-row wrap">
            <input
              type="text"
              className="grow"
              style={{ flexBasis: "160px" }}
              placeholder="Series (Saga, Amazing Spider-Man…)"
              value={form.series}
              onChange={(e) => setForm({ ...form, series: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), textSearch())}
            />
            <input
              type="text"
              style={{ flex: "0 0 66px" }}
              placeholder="Issue #"
              value={form.issue_number}
              onChange={(e) => setForm({ ...form, issue_number: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), textSearch())}
            />
            {/* the run's start year, not the cover year — it's what tells six
                different Guardians of the Galaxy #1s apart. Same field as the
                one in the details below, so filling either fills both. */}
            <input
              type="text"
              inputMode="numeric"
              style={{ flex: "0 0 92px" }}
              placeholder="Vol. year"
              title="The year the run started — 2008 for that Guardians of the Galaxy"
              value={form.volume_year}
              onChange={(e) => setForm({ ...form, volume_year: e.target.value })}
              onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), textSearch())}
            />
            {/* supplement mode: the small five-digit symbol beside the main
                barcode is the only thing that names the issue */}
            <BarcodeScan onCode={onBarcode} supplement />
          </div>
          <p className="modal-note">
            <Icon id="info" />
            Scanning the big barcode names the series — every issue of a run
            shares it. Scan the <strong>small five-digit code</strong> beside it
            for the issue number, or just type it.
          </p>
          <div className="form-row">
            <input
              type="text"
              required
              className="grow"
              placeholder="Title as you want it filed"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
            />
            <button type="button" className="ghost" onClick={textSearch} disabled={searching}>
              {searching ? "…" : "Look up"}
            </button>
          </div>

        {searching && <Searching />}

          {/* A scan names the run, not the issue — so this is the whole answer
              a barcode can give, and the year is the part that matters. */}
          {runs && (
            <>
              <span className="game-info-line">
                {runs.length} runs called “{form.series}” — which one is it?
              </span>
              <div className="run-list">
                {runs.map((r) => (
                  <button
                    type="button"
                    key={r.id}
                    className="run-row"
                    onClick={() => pickRun(r)}
                  >
                    <b>{r.start_year || "—"}</b>
                    <span className="run-text">
                      <strong>{r.name}</strong>
                      <small>
                        {[r.publisher, r.issue_count && `${r.issue_count} issues`]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                    </span>
                  </button>
                ))}
              </div>
              <p className="settings-note" style={{ marginBottom: "var(--s-2)" }}>
                Then type the issue number off the cover.
              </p>
            </>
          )}

          {results && (
            <>
              <span className="game-info-line">
                Comic Vine · {results.length} match{results.length === 1 ? "" : "es"}
              </span>
              {results.length === 0 && (
                <p className="empty" style={{ padding: "var(--s-3)" }}>
                  Nothing found — fill the details in by hand below.
                </p>
              )}
              <div className="grid pick-grid">
                {results.map((r, i) => (
                  <div
                    key={r.comicvine_id || i}
                    className="tile pick"
                    onClick={() => pickResult(r)}
                    title="Use this issue"
                  >
                    {r.image_url ? (
                      <img src={r.image_url} alt={r.title} loading="lazy" />
                    ) : (
                      <div className="placeholder" data-label="no cover" />
                    )}
                    <div className="tile-info">
                      <strong>{r.title}</strong>
                      <small>{r.story_title || "—"}</small>
                      <small>
                        {[r.volume_year && `vol. ${r.volume_year}`, r.cover_year]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        <ByHand onClick={() => setStep("details")} />
      </AddSheet>

      <AddSheet
        open={showForm && step === "details"}
        title="Add an issue"
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
            <input
              type="text"
              className="grow"
              placeholder="Series"
              value={form.series}
              onChange={(e) => setForm({ ...form, series: e.target.value })}
            />
            <input
              type="text"
              style={{ flex: "0 0 84px" }}
              placeholder="Issue #"
              value={form.issue_number}
              onChange={(e) => setForm({ ...form, issue_number: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Publisher (Marvel, Image…)"
              value={form.publisher}
              onChange={(e) => setForm({ ...form, publisher: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Vol. year"
              inputMode="numeric"
              value={form.volume_year}
              onChange={(e) => setForm({ ...form, volume_year: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Cover year"
              inputMode="numeric"
              value={form.cover_year}
              onChange={(e) => setForm({ ...form, cover_year: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Variant cover (1:25, Campbell…)"
              value={form.variant}
              onChange={(e) => setForm({ ...form, variant: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Creators"
              value={form.creators}
              onChange={(e) => setForm({ ...form, creators: e.target.value })}
            />
          </div>
          <div className="form-row">
            <ImagePicker
              value={form.image_url}
              label="Cover photo"
              onChange={(url) => setForm({ ...form, image_url: url })}
            />
          </div>
          <div className="form-row wrap">
            <button
              type="button"
              className={`toggle ${form.own ? "on" : ""}`}
              onClick={() => setForm({ ...form, own: !form.own })}
            >
              {form.own ? "I own it" : "I want it"}
            </button>
            <select
              disabled={!form.own || !!form.grader}
              title={form.grader ? "Slabbed — the grade below applies" : "Raw grade"}
              value={form.condition}
              onChange={(e) => setForm({ ...form, condition: e.target.value })}
            >
              {COMIC_GRADES.map(([v, l]) => (
                <option key={v} value={v}>
                  {l}
                </option>
              ))}
            </select>
            <select
              disabled={!form.own}
              title="Slabbed by"
              value={form.grader}
              onChange={(e) =>
                setForm({ ...form, grader: e.target.value, grade: e.target.value ? "9.8" : "" })
              }
            >
              <option value="">Raw</option>
              {COMIC_GRADERS.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
            {form.grader && (
              <select
                disabled={!form.own}
                title="Slab grade"
                value={form.grade}
                onChange={(e) => setForm({ ...form, grade: e.target.value })}
              >
                {COMIC_SLAB_GRADES.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
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
      {!error && loaded && comics.length === 0 && (
        <div className="empty">
          <span className="glyph"><Icon id="comic" /></span>
          <strong>No issues yet</strong>
          <p>Search a series and issue number, or fill one in by hand.</p>
        </div>
      )}

      <div className={`game-list ${tiles ? "as-tiles" : ""}`}>
        {comics.map((c) => (
          <ComicRow key={c.id} comic={c} onChange={patchComic} onReload={load} />
        ))}
      </div>
    </div>
  );
}

function ComicRow({ comic, onChange, onReload }) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);
  const [editVals, setEditVals] = useState({ condition: "VF", grader: "", grade: "" });
  const [infoOpen, setInfoOpen] = useState(false);
  const a = comic.attrs;

  const run = async (fn) => {
    if (busy) return;
    setBusy(true);
    try {
      onChange(comic.id, await fn());
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  const removeCopy = (o) => {
    if (!confirm(`Remove this copy of ${comic.title} (${copyLabel(o) || "copy"})?`)) return;
    run(() => api.removeOwned(comic.id, o.id));
  };
  const openEdit = (o) => {
    setEditing(o.id);
    setEditVals({
      condition: o.condition || "VF",
      grader: o.grader || "",
      grade: o.grade || "",
    });
  };
  const saveEdit = () =>
    run(async () => {
      const s = await api.updateOwned(comic.id, editing, {
        condition: editVals.condition,
        grader: editVals.grader || null,
        grade: editVals.grader ? editVals.grade || null : null,
      });
      setEditing(null);
      return s;
    });

  const del = async () => {
    if (!confirm(`Delete "${comic.title}" and its copies?`)) return;
    await api.deleteComic(comic.id);
    onReload();
  };

  const [entry, setEntry] = useState(null); // null = editor closed
  const rowRef = useRef(null);
  const entryInit = useRef(null); // what the editor opened with, to spot edits
  useDismiss(
    infoOpen || entry !== null || editing !== null,
    () => {
      setInfoOpen(false);
      setEntry(null);
      setEditing(null);
    },
    [rowRef],
    () => keepOpen(entry, entryInit.current, entry !== null, comic.title),
  );
  const openEntry = () => {
    const vals = {
      title: comic.title || "",
      series: a.series || "",
      issue_number: a.issue_number || "",
      volume_year: a.volume_year ?? "",
      publisher: a.publisher || "",
      cover_year: a.cover_year ?? "",
      variant: a.variant || "",
      creators: a.creators || "",
      image_url: comic.image_url,
    };
    entryInit.current = vals;
    setEntry(vals);
  };

  const saveEntry = async () => {
    if (busy) return;
    if (!entry.title.trim()) return alert("An issue needs a title.");
    setBusy(true);
    try {
      await api.updateComic(comic.id, {
        title: entry.title.trim(),
        series: entry.series.trim() || null,
        issue_number: entry.issue_number.trim() || null,
        publisher: entry.publisher.trim() || null,
        variant: entry.variant.trim() || null,
        creators: entry.creators.trim() || null,
        volume_year: entry.volume_year ? Number(entry.volume_year) : null,
        cover_year: entry.cover_year ? Number(entry.cover_year) : null,
        image_url: await api.localiseImage(entry.image_url),
      });
      setEntry(null);
      onReload();
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      ref={rowRef}
      className={`game-row ${comic.owned.length ? "row-owned" : ""} ${infoOpen || entry ? "open" : ""}`}
    >
      {comic.image_url ? (
        <img
          className="game-cover"
          src={comic.image_url}
          alt=""
          loading="lazy"
          style={{ cursor: "pointer" }}
          onClick={() => setInfoOpen(!infoOpen)}
        />
      ) : (
        <span className="game-icon" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
          <Icon id="comic" />
        </span>
      )}
      <span className="game-text" style={{ cursor: "pointer" }} onClick={() => setInfoOpen(!infoOpen)}>
        <strong>{comic.title}</strong>
        <small className="game-meta">
          {a.issue_number && <span className="plat-badge">#{a.issue_number}</span>}
          {a.publisher && <span>{a.publisher}</span>}
          {a.cover_year && <span>{a.cover_year}</span>}
          {a.variant && <span>{a.variant}</span>}
        </small>
        {comic.owned.length > 0 && (
          <span className="copy-chips">
            {comic.owned.map((o) => (
              <span
                key={o.id}
                className={`chip copy ${o.grader ? "graded" : ""}`}
                onClick={() => (editing === o.id ? setEditing(null) : openEdit(o))}
                title="Edit this copy"
              >
                <Icon id="pencil" />
                {copyLabel(o) || "set grade…"}
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
          onClick={() => (entry ? setEntry(null) : openEntry())}
          title="Edit entry"
        >
          <Icon id="pencil" />
        </button>
        <button className="ghost icon danger" onClick={del} title="Delete entry">
          <Icon id="trash" />
        </button>
      </span>

      {entry && (
        <span className="entry-edit">
          <span className="game-info-line">Issue details</span>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Title as you want it filed"
              value={entry.title}
              onChange={(e) => setEntry({ ...entry, title: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Series"
              value={entry.series}
              onChange={(e) => setEntry({ ...entry, series: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "100px" }}
              placeholder="Issue #"
              value={entry.issue_number}
              onChange={(e) => setEntry({ ...entry, issue_number: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Publisher"
              value={entry.publisher}
              onChange={(e) => setEntry({ ...entry, publisher: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Vol. year"
              inputMode="numeric"
              value={entry.volume_year}
              onChange={(e) => setEntry({ ...entry, volume_year: e.target.value })}
            />
            <input
              type="text"
              style={{ maxWidth: "110px" }}
              placeholder="Cover year"
              inputMode="numeric"
              value={entry.cover_year}
              onChange={(e) => setEntry({ ...entry, cover_year: e.target.value })}
            />
          </div>
          <div className="form-row">
            <input
              type="text"
              className="grow"
              placeholder="Variant cover"
              value={entry.variant}
              onChange={(e) => setEntry({ ...entry, variant: e.target.value })}
            />
            <input
              type="text"
              className="grow"
              placeholder="Creators"
              value={entry.creators}
              onChange={(e) => setEntry({ ...entry, creators: e.target.value })}
            />
          </div>
          <div className="form-row">
            <ImagePicker
              value={entry.image_url}
              label="Cover photo"
              onChange={(url) => setEntry({ ...entry, image_url: url })}
            />
            <button
              className="primary icon"
              onClick={saveEntry}
              disabled={busy}
              title="Save"
              style={{ marginLeft: "auto" }}
            >
              <Icon id="check" />
            </button>
            <button className="ghost icon" onClick={() => setEntry(null)} title="Cancel">
              <Icon id="x" />
            </button>
          </div>
        </span>
      )}

      {infoOpen && (
        <span className="entry-edit game-info">
          <div className="expand-card">
            {comic.image_url && (
              <img className="expand-cover" src={comic.image_url} alt="" loading="lazy" />
            )}
            <div className="expand-body">
              <span className="expand-title">{comic.title}</span>
              <span className="expand-sub">
                {[a.series, a.volume_year && `vol. ${a.volume_year}`]
                  .filter(Boolean)
                  .join(" · ") || "Unknown series"}
              </span>
              <span className="game-info-line">
                {[
                  a.publisher,
                  a.cover_year,
                  a.variant,
                  a.creators,
                  a.barcode && `Barcode ${a.barcode}`,
                ]
                  .filter(Boolean)
                  .join("  ·  ")}
              </span>
            </div>
            {/* the title already carries series and issue, so the variant
                cover is the only thing left that separates two listings */}
            <EbayLink title={comic.title} terms={[a.variant]} />
          </div>
          {a.blurb && <p className="game-summary">{a.blurb}</p>}
        </span>
      )}

      {editing !== null && (
        <span className="copy-edit">
          <select
            title={editVals.grader ? "Slabbed — the grade applies" : "Raw grade"}
            disabled={!!editVals.grader}
            value={editVals.condition}
            onChange={(e) => setEditVals({ ...editVals, condition: e.target.value })}
          >
            {withUnknown(COMIC_GRADES, editVals.condition).map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
          <select
            title="Slabbed by"
            value={editVals.grader}
            onChange={(e) =>
              setEditVals({
                ...editVals,
                grader: e.target.value,
                grade: e.target.value ? editVals.grade || "9.8" : "",
              })
            }
          >
            <option value="">Raw</option>
            {COMIC_GRADERS.map((g) => (
              <option key={g}>{g}</option>
            ))}
          </select>
          {editVals.grader && (
            <select
              title="Slab grade"
              value={editVals.grade}
              onChange={(e) => setEditVals({ ...editVals, grade: e.target.value })}
            >
              {COMIC_SLAB_GRADES.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          )}
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
