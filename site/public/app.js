// SF Music Calendar: renders events.json (written by site/build.py) as a filterable day list.
(() => {
  "use strict";

  const TZ = "America/Los_Angeles";
  const STORE = "sfmc.venues";
  const WHENS = ["all", "tonight", "weekend", "date"];
  const OLD_AFTER_DAYS = 9; // the job runs weekly; past this the refresh is probably stuck

  const $ = (sel) => document.querySelector(sel);
  const el = {
    status: $("#status"), bar: $("#bar"), q: $("#q"), when: $("#when"),
    dateBtn: $("#date-btn"), datePanel: $("#date-panel"), cal: $("#cal"), calTitle: $("#cal-title"),
    venueBtn: $("#venue-btn"), venuePanel: $("#venue-panel"), chips: $("#chips"),
    list: $("#list"), index: $("#venue-index"),
  };

  // when: "all" | "tonight" | "weekend" | "date" (then `date` holds the picked day)
  const state = { q: "", when: "all", date: null, venues: new Set() };
  let venues = [];
  let events = [];
  let generated = null;
  let calMonth = null; // "YYYY-MM" shown in the date picker
  let openPanel = null; // "date" | "venues" | null

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
    const fromUrl = params.get("venues");
    const slugs = (fromUrl ?? store.get(STORE) ?? "").split(",").filter(Boolean);
    const bySlug = new Map(venues.map((v, i) => [v.slug, i]));
    state.venues = new Set(slugs.map((s) => bySlug.get(s)).filter((i) => i !== undefined));
  }

  function writeState() {
    const chosen = [...state.venues].map((i) => venues[i].slug).join(",");
    store.set(STORE, chosen);
    const params = new URLSearchParams();
    if (state.q.trim()) params.set("q", state.q.trim());
    if (state.when === "date") params.set("date", state.date);
    else if (state.when !== "all") params.set("when", state.when);
    if (chosen) params.set("venues", chosen);
    const qs = params.toString();
    history.replaceState(null, "", qs ? `?${qs}` : location.pathname);
  }

  // ── filtering ──────────────────────────────────────────

  // Venue + search filters only; the calendar uses this to mark which days have matching shows.
  function matchesExceptDate(today) {
    const terms = fold(state.q).split(/\s+/).filter(Boolean);
    return events.filter(
      (e) =>
        e.date >= today &&
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

  function renderStatus(shownCount, today) {
    const upcoming = events.filter((e) => e.date >= today).length;
    const stale = venues.filter((v) => v.stale).length;
    const filtered = state.q.trim() || state.when !== "all" || state.venues.size;
    const age = generated ? ago(generated) : null;
    const bits = [
      filtered ? `${plural(shownCount, "show")} of ${upcoming.toLocaleString("en-US")}` : plural(upcoming, "show"),
      plural(venues.length, "venue"),
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

    for (const b of el.chips.querySelectorAll("[data-venue]")) {
      b.setAttribute("aria-pressed", String(state.venues.has(Number(b.dataset.venue))));
    }
    const n = state.venues.size;
    const long = n === 0 ? "all venues" : n === 1 ? venues[[...state.venues][0]].name : `${n} venues`;
    const short = n === 0 ? "venues" : n === 1 ? "1 venue" : `${n} venues`; // phones: fits beside the when-toggle
    el.venueBtn.innerHTML = `<span class="long">${esc(long)}</span><span class="short">${esc(short)}</span> ▾`;
    el.venueBtn.classList.toggle("filtered", n > 0);
    if (el.q.value !== state.q) el.q.value = state.q;
  }

  function render() {
    const today = todayISO();
    renderControls();
    renderStatus(renderList(today).length, today);
    if (openPanel === "date") renderCalendar(today);
    writeState();
  }

  function buildVenueUi() {
    const today = todayISO();
    const counts = venues.map(() => 0);
    for (const e of events) if (e.date >= today) counts[e.venue]++;
    const order = venues.map((_, i) => i).sort((a, b) => sortKey(venues[a].name).localeCompare(sortKey(venues[b].name)));

    el.chips.innerHTML = order
      .map((i) => `<button type="button" class="chip" data-venue="${i}" aria-pressed="false">${esc(venues[i].name)}<span class="n">${counts[i]}</span></button>`)
      .join("");

    el.index.innerHTML = order
      .map((i) => {
        const v = venues[i];
        const href = safeUrl(v.url);
        const name = href ? `<a href="${esc(href)}" target="_blank" rel="noopener">${esc(v.name)}</a>` : esc(v.name);
        const meta = [v.area, plural(counts[i], "show")].filter(Boolean).join(" · ");
        const stale = v.stale ? `<span class="stale">not refreshed this week</span>` : "";
        return `<li>${name}<span class="tw-muted">${esc(meta)}</span>${stale}</li>`;
      })
      .join("");
  }

  // ── events ─────────────────────────────────────────────

  function setPanel(name) {
    openPanel = name;
    el.datePanel.hidden = name !== "date";
    el.venuePanel.hidden = name !== "venues";
    el.dateBtn.setAttribute("aria-expanded", String(name === "date"));
    el.venueBtn.setAttribute("aria-expanded", String(name === "venues"));
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

    el.venueBtn.addEventListener("click", () => setPanel(openPanel === "venues" ? null : "venues"));

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
      if (action === "close-venues") setPanel(null);
      if (action === "reset") {
        state.q = ""; state.when = "all"; state.date = null; state.venues.clear();
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
          const btn = openPanel === "date" ? el.dateBtn : el.venueBtn;
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
      venues = data.venues.map((v) => ({ ...v, slug: slug(v.name) }));
      events = data.events
        .filter((e) => venues[e.venue])
        .map((e) => ({
          ...e,
          artists: Array.isArray(e.artists) ? e.artists : [],
          hay: fold(`${(e.artists || []).join(" ")} ${venues[e.venue].name} ${venues[e.venue].area}`),
        }))
        // by day, then by time with untimed (all-day, TBA) shows after the timed ones
        .sort((a, b) => a.date.localeCompare(b.date) || (a.time ?? "99").localeCompare(b.time ?? "99"));
    } catch (err) {
      el.list.innerHTML = `<p class="tw-alert">Couldn't load the listings (${esc(err.message)}). Reload to try again.</p>`;
      return;
    }
    readState();
    buildVenueUi();
    render();
  }

  boot();
})();
