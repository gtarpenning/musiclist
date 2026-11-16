// SF Music Calendar: renders events.json (written by site/build.py) as a filterable day list.
(() => {
  "use strict";

  const TZ = "America/Los_Angeles";
  const STORE = { venues: "sfmc.venues", city: "sfmc.city", kinds: "sfmc.kinds" };
  const WHENS = ["all", "tonight", "weekend", "date"];
  const OLD_AFTER_DAYS = 9; // the job runs weekly; past this the refresh is probably stuck
  const HOME = "sf"; // the city shown until another is ticked
  const EAST_BAY = ["Oakland", "Berkeley"]; // all of these ticked reads "East Bay"
  // venue kinds (venues_config.py), in filter order
  const KINDS = {
    bar: "bars", club: "clubs", small: "small venues", mid: "mid-size venues",
    large: "large venues", arena: "arenas", other: "other",
  };
  const KIND_SHORT = { small: "small", mid: "mid-size", large: "large" }; // phone button labels

  const $ = (sel) => document.querySelector(sel);
  const el = {
    status: $("#status"), bar: $("#bar"), q: $("#q"), when: $("#when"),
    dateBtn: $("#date-btn"), datePanel: $("#date-panel"), cal: $("#cal"), calTitle: $("#cal-title"),
    cityBtn: $("#city-btn"), cityPanel: $("#city-panel"), cityOpts: $("#city-opts"),
    kindBtn: $("#kind-btn"), kindPanel: $("#kind-panel"), kindOpts: $("#kind-opts"),
    venueBtn: $("#venue-btn"), venuePanel: $("#venue-panel"), chips: $("#chips"),
    list: $("#list"), index: $("#venue-index"),
  };
  const PANELS = {
    date: [el.datePanel, el.dateBtn], city: [el.cityPanel, el.cityBtn],
    kinds: [el.kindPanel, el.kindBtn], venues: [el.venuePanel, el.venueBtn],
  };

  // when: "all" | "tonight" | "weekend" | "date" (then `date` holds the picked day)
  // cities scope everything (never empty); kinds: empty = all; venues: empty = all shown
  const state = { q: "", when: "all", date: null, cities: new Set([HOME]), kinds: new Set(), venues: new Set() };
  let venues = [];
  let events = [];
  let cities = []; // [{key, name}] in data order, home first
  let kinds = []; // kind keys present in the data, in KINDS order
  let order = []; // venue indexes, alphabetical
  let counts = []; // upcoming shows per venue
  let generated = null;
  let calMonth = null; // "YYYY-MM" shown in the date picker
  let openPanel = null; // a PANELS key or null

  // ── helpers ────────────────────────────────────────────

  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ESC[c]);
  const fold = (s) => String(s).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const slug = (s) => fold(s).replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  const sortKey = (s) => fold(s).replace(/^the\s+/, "");
  const plural = (n, word) => `${n.toLocaleString("en-US")} ${word}${n === 1 ? "" : "s"}`;

  function safeUrl(u) {
    try {
      const url = new URL(u);
      return url.protocol === "https:" || url.protocol === "http:" ? url.href : null;
    } catch {
      return null;
    }
  }

  const store = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { /* private mode */ } },
  };

  // Dates are plain YYYY-MM-DD strings in San Francisco time; noon UTC keeps arithmetic DST-proof.
  const todayISO = () =>
    new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
  const asDate = (iso) => new Date(`${iso}T12:00:00Z`);
  const addDays = (iso, n) => {
    const d = asDate(iso);
    d.setUTCDate(d.getUTCDate() + n);
    return d.toISOString().slice(0, 10);
  };
  const dayDiff = (a, b) => Math.round((asDate(b) - asDate(a)) / 86400000);
  const isISODate = (s) => /^\d{4}-\d{2}-\d{2}$/.test(s || "") && !Number.isNaN(asDate(s).getTime());
  const fmt = (iso, opts) => asDate(iso).toLocaleDateString("en-US", { timeZone: "UTC", ...opts });

  function range(today) {
    if (state.when === "tonight") return [today, today];
    if (state.when === "date" && state.date) return [state.date, state.date];
    if (state.when === "weekend") {
      const dow = asDate(today).getUTCDay(); // 0 = Sunday
      if (dow === 0) return [today, today];
      if (dow >= 5) return [today, addDays(today, 7 - dow)];
      const friday = addDays(today, 5 - dow);
      return [friday, addDays(friday, 2)];
    }
    return [today, "9999-12-31"];
  }

  function dayLabel(iso, today) {
    const diff = dayDiff(today, iso);
    const opts = { weekday: "short", month: "short", day: "numeric" };
    if (iso.slice(0, 4) !== today.slice(0, 4)) opts.year = "numeric";
    const date = fmt(iso, opts); // "Fri, Nov 20"
    if (diff === 0) return { name: "Tonight", date };
    if (diff === 1) return { name: "Tomorrow", date };
    return { name: fmt(iso, { weekday: "long" }), date: date.replace(/^\w+, /, "") };
  }

  function clock(hhmm) {
    if (!hhmm) return "";
    const [h, m] = hhmm.split(":").map(Number);
    const hour = h % 12 || 12;
    return `${hour}${m ? `:${String(m).padStart(2, "0")}` : ""}${h < 12 ? "am" : "pm"}`;
  }

  function ago(iso) {
    const days = Math.floor((Date.now() - new Date(iso)) / 86400000);
    const text = days <= 0 ? "updated today" : days === 1 ? "updated yesterday" : `updated ${days} days ago`;
    return { text, old: days > OLD_AFTER_DAYS };
  }

  const cityKey = (city) => (city === "San Francisco" ? HOME : slug(city));
  const inScope = (v) => state.cities.has(v.cityKey);
  const shown = (v) => inScope(v) && (!state.kinds.size || state.kinds.has(v.kind));

  // A picked venue the city or kind filters now hide is dropped, so "1 venue" never means "nothing".
  function pruneVenues() {
    for (const i of state.venues) if (!shown(venues[i])) state.venues.delete(i);
  }

  function cityLabel() {
    const on = cities.filter((c) => state.cities.has(c.key));
    const east = cities.filter((c) => EAST_BAY.includes(c.name));
    const allEast = east.length > 1 && east.every((c) => state.cities.has(c.key));
    const names = on
      .filter((c) => !(allEast && EAST_BAY.includes(c.name)))
      .map((c) => (c.key === HOME ? "SF" : c.name));
    if (allEast) names.push("East Bay");
    return names.join(" + ");
  }

  function kindLabel() {
    const n = state.kinds.size;
    if (!n) return { long: "all kinds", short: "kinds" };
    const short = (k) => KIND_SHORT[k] || KINDS[k];
    if (n === 1) {
      const only = [...state.kinds][0];
      return { long: KINDS[only], short: short(only) };
    }
    if (n === kinds.length - 1) {
      const off = kinds.find((k) => !state.kinds.has(k));
      return { long: `no ${KINDS[off]}`, short: `no ${short(off)}` };
    }
    return { long: `${n} kinds`, short: `${n} kinds` };
  }

  // ── state <-> URL / storage ────────────────────────────

  function readState() {
    const params = new URLSearchParams(location.search);
    state.q = params.get("q") || "";
    const date = params.get("date");
    if (isISODate(date) && date >= todayISO()) {
      state.when = "date";
      state.date = date;
    } else {
      const when = params.get("when");
      state.when = WHENS.includes(when) && when !== "date" ? when : "all";
    }
    // where-filters come from the URL, else from this browser's last visit
    const list = (name, key) => (params.get(name) ?? store.get(key) ?? "").split(",").filter(Boolean);
    const cityKeys = new Set(cities.map((c) => c.key));
    const picked = list("city", STORE.city).filter((k) => cityKeys.has(k));
    state.cities = new Set(picked.length ? picked : [HOME]);
    const kindSet = list("kinds", STORE.kinds).filter((k) => kinds.includes(k));
    state.kinds = new Set(kindSet.length === kinds.length ? [] : kindSet);
    const bySlug = new Map(venues.map((v, i) => [v.slug, i]));
    state.venues = new Set(list("venues", STORE.venues).map((s) => bySlug.get(s)).filter((i) => i !== undefined));
    pruneVenues();
  }

  function writeState() {
    const chosen = [...state.venues].map((i) => venues[i].slug).join(",");
    const city = cities.filter((c) => state.cities.has(c.key)).map((c) => c.key).join(",");
    const kind = kinds.filter((k) => state.kinds.has(k)).join(",");
    store.set(STORE.venues, chosen);
    store.set(STORE.city, city);
    store.set(STORE.kinds, kind);
    const params = new URLSearchParams();
    if (state.q.trim()) params.set("q", state.q.trim());
    if (state.when === "date") params.set("date", state.date);
    else if (state.when !== "all") params.set("when", state.when);
    if (city !== HOME) params.set("city", city);
    if (kind) params.set("kinds", kind);
    if (chosen) params.set("venues", chosen);
    const qs = params.toString();
    history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
  }

  // ── filtering ──────────────────────────────────────────

  // Every filter but the date; the calendar uses this to mark which days have matching shows.
  function matchesExceptDate(today) {
    const terms = fold(state.q).split(/\s+/).filter(Boolean);
    return events.filter(
      (e) =>
        e.date >= today &&
        shown(venues[e.venue]) &&
        (!state.venues.size || state.venues.has(e.venue)) &&
        terms.every((t) => e.hay.includes(t)),
    );
  }

  function matches(today) {
    const [lo, hi] = range(today);
    return matchesExceptDate(today).filter((e) => e.date >= lo && e.date <= hi);
  }

  // ── rendering ──────────────────────────────────────────

  function showHtml(e) {
    const v = venues[e.venue];
    const [head, ...rest] = e.artists.length ? e.artists : ["TBA"];
    const href = safeUrl(e.url);
    const inner =
      `<span class="time">${esc(clock(e.time))}</span>` +
      `<span class="acts"><span class="head">${esc(head)}</span>` +
      (rest.length ? `<span class="with">with ${esc(rest.join(", "))}</span>` : "") +
      `</span>` +
      `<span class="where">${esc(v.name)}</span>` +
      `<span class="price" title="${esc(e.price)}">${esc(e.price)}</span>`;
    return href
      ? `<a class="show" href="${esc(href)}" target="_blank" rel="noopener">${inner}</a>`
      : `<div class="show">${inner}</div>`;
  }

  function renderList(today) {
    const shown = matches(today);
    if (!shown.length) {
      el.list.innerHTML =
        `<p class="empty">No shows match. <button type="button" class="textbtn" data-action="reset">clear filters</button></p>`;
      return shown;
    }
    const parts = [];
    let i = 0;
    while (i < shown.length) {
      const date = shown[i].date;
      let j = i;
      while (j < shown.length && shown[j].date === date) j++;
      const label = dayLabel(date, today);
      parts.push(
        `<section class="day-group"><h2 class="day"><span class="day-name">${esc(label.name)}</span>` +
        `<span class="day-date">${esc(label.date)}</span></h2>`,
      );
      for (let k = i; k < j; k++) parts.push(showHtml(shown[k]));
      parts.push(`</section>`);
      i = j;
    }
    el.list.innerHTML = parts.join("");
    return shown;
  }

  // Counts are within the chosen cities; the other filters show as "n of total".
  function renderStatus(shownCount, today) {
    const upcoming = events.filter((e) => e.date >= today && inScope(venues[e.venue])).length;
    const scoped = venues.filter(inScope);
    const stale = scoped.filter((v) => v.stale).length;
    const filtered = state.q.trim() || state.when !== "all" || state.kinds.size || state.venues.size;
    const age = generated ? ago(generated) : null;
    const bits = [
      filtered ? `${plural(shownCount, "show")} of ${upcoming.toLocaleString("en-US")}` : plural(upcoming, "show"),
      plural(scoped.length, "venue"),
    ];
    let html = bits.map(esc).join(" · ");
    if (age) html += ` · <span class="${age.old ? "old" : ""}">${esc(age.text)}</span>`;
    if (stale) html += ` · <a href="#venue-index">${plural(stale, "venue")} not refreshed</a>`;
    el.status.innerHTML = html;
  }

  function renderCalendar(today) {
    if (!calMonth) calMonth = (state.date || today).slice(0, 7);
    const withShows = new Set(matchesExceptDate(today).map((e) => e.date));
    const first = `${calMonth}-01`;
    const lastMonth = (events.length ? events[events.length - 1].date : today).slice(0, 7);

    el.calTitle.textContent = fmt(first, { month: "long", year: "numeric" });
    el.datePanel.querySelector('[data-cal="-1"]').disabled = calMonth <= today.slice(0, 7);
    el.datePanel.querySelector('[data-cal="1"]').disabled = calMonth >= lastMonth;

    const cells = ["su", "mo", "tu", "we", "th", "fr", "sa"].map((d) => `<span class="cal-dow" aria-hidden="true">${d}</span>`);
    for (let k = asDate(first).getUTCDay(); k > 0; k--) cells.push(`<span></span>`);
    for (let iso = first; iso.slice(0, 7) === calMonth; iso = addDays(iso, 1)) {
      const usable = iso >= today && withShows.has(iso);
      const picked = state.when === "date" && state.date === iso;
      const label = fmt(iso, { weekday: "long", month: "long", day: "numeric" });
      cells.push(
        `<button type="button" class="cal-day${iso === today ? " today" : ""}" data-day="${iso}"` +
        ` aria-pressed="${picked}" aria-label="${esc(label)}"${usable ? "" : " disabled"}>${Number(iso.slice(8))}</button>`,
      );
    }
    el.cal.innerHTML = cells.join("");
  }

  function renderControls() {
    for (const b of el.when.querySelectorAll("[data-when]")) {
      const on = b.dataset.when === state.when;
      b.classList.toggle("tw-toggle-on", on);
      b.setAttribute("aria-pressed", String(on));
    }
    if (state.when === "date") {
      const long = fmt(state.date, { weekday: "short", month: "short", day: "numeric" }).replace(",", "");
      const short = fmt(state.date, { month: "short", day: "numeric" });
      el.dateBtn.innerHTML = `<span class="long">${esc(long)} ▾</span><span class="short">${esc(short)}</span>`;
    } else {
      el.dateBtn.textContent = "date ▾";
    }

    const label = (btn, long, short) => {
      btn.innerHTML = `<span class="long">${esc(long)} ▾</span><span class="short">${esc(short)} ▾</span>`;
    };
    const city = cityLabel();
    label(el.cityBtn, city, city);
    el.cityOpts.innerHTML = cities.map((c) => option("city", c.key, c.name, state.cities.has(c.key), state.cities.size)).join("");

    const on = state.kinds.size ? state.kinds : new Set(kinds);
    const kind = kindLabel();
    label(el.kindBtn, kind.long, kind.short);
    el.kindBtn.classList.toggle("filtered", state.kinds.size > 0);
    el.kindOpts.innerHTML = kinds.map((k) => option("kind", k, KINDS[k], on.has(k), on.size)).join("");
    el.kindPanel.querySelector('[data-action="all-kinds"]').hidden = !state.kinds.size;

    const n = state.venues.size;
    label(
      el.venueBtn,
      n === 0 ? "all venues" : n === 1 ? venues[[...state.venues][0]].name : `${n} venues`,
      n === 0 ? "venues" : n === 1 ? "1 venue" : `${n} venues`,
    );
    el.venueBtn.classList.toggle("filtered", n > 0);
    renderChips();
    if (el.q.value !== state.q) el.q.value = state.q;
  }

  // A checklist row; the last ticked one can't be unticked (no city or kind = nothing to show).
  function option(name, key, text, checked, checkedCount) {
    const last = checked && checkedCount === 1;
    return (
      `<button type="button" class="opt" role="checkbox" data-${name}="${esc(key)}" aria-checked="${checked}"` +
      `${last ? " disabled" : ""}>${esc(text)}</button>`
    );
  }

  // Venue picker: the venues the city and kind filters leave, grouped by kind.
  function renderChips() {
    el.chips.innerHTML = kinds
      .map((k) => {
        const items = order.filter((i) => venues[i].kind === k && shown(venues[i]));
        if (!items.length) return "";
        const chips = items.map(
          (i) =>
            `<button type="button" class="chip" data-venue="${i}" aria-pressed="${state.venues.has(i)}">` +
            `${esc(venues[i].name)}<span class="n">${counts[i]}</span></button>`,
        );
        return `<div class="chip-group"><span class="tw-label">${esc(KINDS[k])}</span><div class="chips">${chips.join("")}</div></div>`;
      })
      .join("");
  }

  // Footer directory: every venue in the chosen cities, by kind.
  function renderIndex() {
    el.index.innerHTML = kinds
      .map((k) => {
        const items = order.filter((i) => venues[i].kind === k && inScope(venues[i]));
        if (!items.length) return "";
        const rows = items.map((i) => {
          const v = venues[i];
          const href = safeUrl(v.url);
          const name = href ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(v.name)}</a>` : esc(v.name);
          const where = v.cityKey === HOME ? v.area : [v.area, v.city].filter(Boolean).join(", ");
          const meta = [where, plural(counts[i], "show")].filter(Boolean).join(" · ");
          const stale = v.stale ? `<span class="stale">not refreshed this week</span>` : "";
          return `<li>${name}<span class="tw-muted">${esc(meta)}</span>${stale}</li>`;
        });
        return `<li><span class="tw-label">${esc(KINDS[k])}</span><ul>${rows.join("")}</ul></li>`;
      })
      .join("");
  }

  function render() {
    const today = todayISO();
    renderControls();
    renderStatus(renderList(today).length, today);
    renderIndex();
    if (openPanel === "date") renderCalendar(today);
    writeState();
  }

  function indexVenues() {
    const today = todayISO();
    counts = venues.map(() => 0);
    for (const e of events) if (e.date >= today) counts[e.venue]++;
    order = venues.map((_, i) => i).sort((a, b) => sortKey(venues[a].name).localeCompare(sortKey(venues[b].name)));
    const seen = [...new Set(venues.map((v) => v.city))];
    cities = seen
      .map((name) => ({ name, key: cityKey(name) }))
      .sort((a, b) => (b.key === HOME) - (a.key === HOME));
    const present = new Set(venues.map((v) => v.kind));
    kinds = Object.keys(KINDS).filter((k) => present.has(k));
  }

  // ── events ─────────────────────────────────────────────

  function setPanel(name) {
    openPanel = name;
    for (const [key, [panel, btn]] of Object.entries(PANELS)) {
      panel.hidden = key !== name;
      btn.setAttribute("aria-expanded", String(key === name));
    }
    if (name === "date") {
      calMonth = null; // reopen on the picked (or current) month
      renderCalendar(todayISO());
    }
  }

  function bind() {
    let timer;
    el.q.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = el.q.value; render(); }, 90);
    });

    el.when.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-when]");
      if (!b) return;
      if (b.dataset.when === "date") {
        setPanel(openPanel === "date" ? null : "date");
        return;
      }
      state.when = b.dataset.when;
      state.date = null;
      setPanel(null);
      render();
    });

    el.cal.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-day]");
      if (!b || b.disabled) return;
      state.when = "date";
      state.date = b.dataset.day;
      setPanel(null);
      render();
    });

    el.datePanel.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-cal]");
      if (!b || b.disabled) return;
      const [y, m] = calMonth.split("-").map(Number);
      const next = new Date(Date.UTC(y, m - 1 + Number(b.dataset.cal), 1));
      calMonth = next.toISOString().slice(0, 7);
      renderCalendar(todayISO());
    });

    for (const [key, [, btn]] of Object.entries(PANELS)) {
      if (key !== "date") btn.addEventListener("click", () => setPanel(openPanel === key ? null : key));
    }

    el.cityOpts.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-city]");
      if (!b || b.disabled) return;
      const key = b.dataset.city;
      if (state.cities.has(key)) state.cities.delete(key);
      else state.cities.add(key);
      pruneVenues();
      render();
    });

    el.kindOpts.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-kind]");
      if (!b || b.disabled) return;
      const on = new Set(state.kinds.size ? state.kinds : kinds);
      const key = b.dataset.kind;
      if (on.has(key)) on.delete(key);
      else on.add(key);
      state.kinds = on.size === kinds.length ? new Set() : on;
      pruneVenues();
      render();
    });

    el.chips.addEventListener("click", (ev) => {
      const b = ev.target.closest("[data-venue]");
      if (!b) return;
      const i = Number(b.dataset.venue);
      if (state.venues.has(i)) state.venues.delete(i);
      else state.venues.add(i);
      render();
    });

    document.addEventListener("click", (ev) => {
      const action = ev.target.closest("[data-action]")?.dataset.action;
      if (action === "all-venues") { state.venues.clear(); render(); }
      if (action === "all-kinds") { state.kinds.clear(); render(); }
      if (action === "close-venues") setPanel(null);
      if (action === "reset") { // the city stays: it's where you are, not a filter
        state.q = ""; state.when = "all"; state.date = null; state.kinds.clear(); state.venues.clear();
        render();
      }
      // Clicks re-render the calendar, so test the click path, not the (possibly detached) target.
      const inside = ev.composedPath().some((n) => n === el.bar);
      if (openPanel && !inside) setPanel(null);
    });

    document.addEventListener("keydown", (ev) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName);
      if (ev.key === "/" && !typing) { ev.preventDefault(); el.q.focus(); el.q.select(); }
      if (ev.key === "Escape") {
        if (openPanel) {
          const btn = PANELS[openPanel][1];
          setPanel(null);
          btn.focus();
        } else if (document.activeElement === el.q && el.q.value) {
          state.q = ""; render();
        }
      }
    });

    // Day headers stick right under the filter bar, whatever height it wraps to.
    const syncBar = () => document.documentElement.style.setProperty("--bar-h", `${el.bar.offsetHeight}px`);
    if ("ResizeObserver" in window) new ResizeObserver(syncBar).observe(el.bar);
    syncBar();
  }

  // ── boot ───────────────────────────────────────────────

  async function boot() {
    bind();
    const version = new URL(document.currentScript?.src || location.href).searchParams.get("v") || "";
    try {
      const res = await fetch(`events.json?v=${encodeURIComponent(version)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      generated = data.generated;
      venues = data.venues.map((v) => {
        const city = v.city || "San Francisco";
        return { ...v, city, cityKey: cityKey(city), kind: v.kind in KINDS ? v.kind : "other", slug: slug(v.name) };
      });
      events = data.events
        .filter((e) => venues[e.venue])
        .map((e) => {
          const v = venues[e.venue];
          const artists = Array.isArray(e.artists) ? e.artists : [];
          return { ...e, artists, hay: fold(`${artists.join(" ")} ${v.name} ${v.area} ${v.city}`) };
        })
        // by day, then by time with untimed (all-day, TBA) shows after the timed ones
        .sort((a, b) => a.date.localeCompare(b.date) || (a.time ?? "99").localeCompare(b.time ?? "99"));
    } catch (err) {
      el.list.innerHTML = `<p class="tw-alert">Couldn't load the listings (${esc(err.message)}). Reload to try again.</p>`;
      return;
    }
    indexVenues();
    readState();
    render();
  }

  boot();
})();
