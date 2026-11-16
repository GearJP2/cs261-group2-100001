(function () {
  "use strict";

  const API = "/api/v1";

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function configurePreviousPageLinks(links) {
    const referrer = document.referrer ? new URL(document.referrer, window.location.href) : null;
    const sameOriginReferrer = referrer?.origin === window.location.origin;
    if (!sameOriginReferrer) return;
    const destination = `${referrer.pathname}${referrer.search}${referrer.hash}`;
    links.forEach((link) => { link.href = destination; });
    links.forEach((link) => {
      link.addEventListener("click", (event) => {
        if (window.history.length > 1) {
          event.preventDefault();
          window.history.back();
        }
      });
    });
  }

  function apiMessage(payload, fallback) {
    if (!payload || !payload.error) return fallback;
    const fields = payload.error.fields || {};
    const fieldMessages = Object.values(fields).filter(Boolean);
    return [payload.error.message, ...fieldMessages].filter(Boolean).join(" ");
  }

  async function csrfToken() {
    const response = await fetch(`${API}/auth/csrf`, { credentials: "same-origin" });
    const payload = await response.json();
    if (!response.ok) throw new Error(apiMessage(payload, "ไม่สามารถเตรียมการเข้าสู่ระบบได้"));
    return payload.data.csrf_token;
  }

  async function request(path, options, includeMeta) {
    const settings = Object.assign({ credentials: "same-origin" }, options || {});
    settings.headers = Object.assign({ Accept: "application/json" }, settings.headers || {});
    if (settings.method && !["GET", "HEAD"].includes(settings.method)) {
      settings.headers["X-CSRFToken"] = await csrfToken();
      settings.headers["Content-Type"] = "application/json";
    }
    const response = await fetch(`${API}${path}`, settings);
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const error = new Error(apiMessage(payload, "เกิดข้อผิดพลาด กรุณาลองใหม่"));
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return includeMeta ? payload : payload.data;
  }

  window.UniSport = { request };

  async function currentUser() {
    try { return await request("/me"); } catch (error) { return null; }
  }

  function initials(name) {
    return (name || "U").trim().slice(0, 1).toUpperCase();
  }

  async function initNavigation() {
    const user = await currentUser();
    const avatar = document.querySelector(".nv-avatar");
    const login = document.querySelector("[data-login-link]");
    const profile = document.querySelector("[data-profile-link]");
    const logout = document.querySelector("[data-logout-button]");
    if (!user) return null;
    if (avatar) avatar.textContent = initials(user.display_name);
    if (login) login.hidden = true;
    if (profile) { profile.href = `/users/${user.id}/`; profile.hidden = false; }
    if (logout) logout.hidden = false;
    return user;
  }

  document.addEventListener("click", async function (event) {
    const button = event.target.closest("[data-logout-button]");
    if (!button) return;
    event.preventDefault();
    button.disabled = true;
    try { await request("/auth/logout", { method: "POST", body: "{}" }); window.location.assign("/"); }
    catch (error) { button.disabled = false; alert(error.message); }
  });

  function setError(container, message) {
    container.hidden = !message;
    container.textContent = message || "";
  }

  async function initLogin() {
    const form = document.querySelector("[data-login-form]");
    if (!form) return;
    if (await currentUser()) { window.location.replace("/"); return; }
    const errorBox = form.querySelector("[data-form-error]");
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      setError(errorBox, "");
      const button = form.querySelector("button[type=submit]");
      const username = form.elements.username.value.trim();
      const password = form.elements.password.value;
      if (!username || !password) { setError(errorBox, "กรุณากรอก Username และ Password"); return; }
      button.disabled = true;
      try {
        await request("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) });
        const nextUrl = new URL(form.dataset.nextUrl || "/", window.location.origin);
        window.location.assign(nextUrl.origin === window.location.origin
          ? `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`
          : "/");
      } catch (error) { setError(errorBox, error.message); button.disabled = false; }
    });
  }

  function formatDateTime(iso) {
    return new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Bangkok" }).format(new Date(iso));
  }

  function partyCard(party, catalog) {
    const card = element("article", "hp-card");
    const top = element("div", "hp-card-top");
    const sport = catalog.sports.get(party.sport_id) || "กีฬา";
    top.append(element("span", "hp-tag", sport), element("span", "hp-open", "● เปิดรับอยู่"));
    const title = element("h3", "", party.title);
    const venue = catalog.venues.get(`${party.sport_id}:${party.venue_id}`) || "สนามกีฬา";
    const host = element("div", "hp-host");
    host.append(element("span", "", `ชวนโดย ${party.host.display_name}`), element("span", "", `${party.member_count}/${party.capacity} คน`));
    const foot = element("div", "hp-card-foot");
    foot.append(element("span", "", `เหลือ ${party.remaining_slots} ที่`));
    const link = element("a", "hp-join", "ดูรายละเอียด");
    link.href = `/parties/${party.id}/`;
    foot.append(link);
    card.append(top, title, element("div", "hp-row", `📍 ${venue}`), element("div", "hp-row", `📅 ${formatDateTime(party.starts_at)}`), host, foot);
    return card;
  }

  async function catalogForParties(parties) {
    const sports = await request("/sports");
    const sportNames = new Map(sports.map((sport) => [sport.id, sport.name]));
    const neededSports = [...new Set(parties.map((party) => party.sport_id))];
    const responses = await Promise.all(neededSports.map(async (sportId) => [sportId, await request(`/venues?sport_id=${sportId}`)]));
    const venues = new Map();
    responses.forEach(([sportId, response]) => response.forEach((venue) => venues.set(`${sportId}:${venue.id}`, venue.name)));
    return { sports: sportNames, venues };
  }

  async function allVenues(sportId) {
    const first = await request(`/venues?sport_id=${sportId}&page_size=100`, undefined, true);
    const pages = Math.ceil(first.total / first.page_size);
    if (pages <= 1) return first.data;
    const rest = await Promise.all(Array.from({ length: pages - 1 }, (_, index) => request(`/venues?sport_id=${sportId}&page=${index + 2}&page_size=100`, undefined, true)));
    return first.data.concat(...rest.map((page) => page.data));
  }

  async function initHome() {
    const section = document.querySelector("[data-home-parties]");
    if (!section) return;
    const message = section.querySelector("[data-home-message]");
    const list = section.querySelector("[data-party-list]");
    const user = await currentUser();
    if (!user) {
      message.textContent = "เข้าสู่ระบบด้วยบัญชีมหาวิทยาลัยเพื่อดูและเข้าร่วมปาร์ตี้";
      return;
    }
    try {
      const parties = await request("/parties");
      if (!parties.length) { message.textContent = "ยังไม่มีปาร์ตี้ที่กำลังเปิดรับ ลองสร้างปาร์ตี้แรกได้เลย"; return; }
      const catalog = await catalogForParties(parties);
      list.replaceChildren(...parties.map((party) => partyCard(party, catalog)));
      list.hidden = false;
      message.hidden = true;
    } catch (error) { message.textContent = error.message; }
  }

  async function initSearch() {
    const page = document.querySelector("[data-search-page]");
    if (!page) return;

    const form = page.querySelector("[data-search-form]");
    const status = page.querySelector("[data-search-status]");
    const resultGrid = page.querySelector("[data-search-results]");
    const emptyState = page.querySelector("[data-search-empty]");
    const errorState = page.querySelector("[data-search-error]");
    const loginState = page.querySelector("[data-search-login]");
    const errorMessage = page.querySelector("[data-search-error-message]");
    const resultCount = page.querySelector("[data-result-count]");
    const resultHeading = page.querySelector("[data-result-heading]");
    const chips = page.querySelector("[data-search-chips]");
    const pagination = page.querySelector("[data-search-pagination]");
    const previousPage = page.querySelector("[data-page-previous]");
    const nextPage = page.querySelector("[data-page-next]");
    const pageLabel = page.querySelector("[data-page-label]");
    const queryInput = page.querySelector("[data-search-query]");
    const sportSelect = page.querySelector("[data-filter-sport]");
    const venueSelect = page.querySelector("[data-filter-venue]");
    const venueTypeSelect = page.querySelector("[data-filter-venue-type]");
    const dateInput = page.querySelector("[data-filter-date]");
    const timeFromInput = page.querySelector("[data-filter-time-from]");
    const timeToInput = page.querySelector("[data-filter-time-to]");
    const stateSelect = page.querySelector("[data-filter-state]");
    const pageSize = 20;
    let parties = [];
    let totalResults = 0;
    let currentPage = 1;
    let sports = [];
    let venues = [];
    let sportNames = new Map();
    let venueNames = new Map();
    let venueSports = new Map();
    let searchReady = false;
    let loadState = "loading";
    let requestId = 0;

    function setVisible(node, visible) { node.hidden = !visible; }

    function updateTimeControls() {
      const enabled = Boolean(dateInput.value);
      timeFromInput.disabled = !enabled;
      timeToInput.disabled = !enabled;
      if (!enabled) {
        timeFromInput.value = "";
        timeToInput.value = "";
      }
    }

    function searchDateTimeParts(value) {
      if (!value.includes("T") || !/(?:Z|[+-]\d{2}:\d{2})$/i.test(value)) {
        throw new Error("ลิงก์ค้นหาต้องระบุวันเวลาและ timezone");
      }
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {
        throw new Error("วันเวลาในลิงก์ค้นหาไม่ถูกต้อง");
      }
      return bangkokDateTimeParts(date.toISOString());
    }

    function activeFilters() {
      return {
        q: queryInput.value.trim().toLocaleLowerCase(),
        sport: sportSelect.value,
        venue: venueSelect.value,
        venueType: venueTypeSelect.value,
        date: dateInput.value,
        timeFrom: timeFromInput.value,
        timeTo: timeToInput.value,
        state: stateSelect.value,
      };
    }

    function renderChips() {
      const filters = activeFilters();
      const active = [];
      if (filters.q) active.push(["q", `ค้นหา: ${queryInput.value.trim()}`]);
      if (filters.sport) active.push(["sport", sportNames.get(Number(filters.sport)) || "กีฬา"]);
      if (filters.venue) active.push(["venue", venueNames.get(Number(filters.venue))?.name || "สนาม"]);
      if (filters.venueType) active.push(["venueType", filters.venueType === "Indoor" ? "ในร่ม" : "กลางแจ้ง"]);
      if (filters.date) active.push(["date", new Intl.DateTimeFormat("th-TH", { dateStyle: "medium", timeZone: "Asia/Bangkok" }).format(new Date(`${filters.date}T12:00:00+07:00`))]);
      if (filters.timeFrom || filters.timeTo) {
        const endTime = !filters.timeTo || filters.timeTo === "00:00" ? "24:00" : filters.timeTo;
        active.push(["time", `${filters.timeFrom || "00:00"}–${endTime}`]);
      }
      if (filters.state && filters.state !== "Open") {
        const stateLabels = {
          Full: "เต็มแล้ว",
          InProgress: "กำลังดำเนินการ",
          Completed: "เสร็จสิ้น",
          Cancelled: "ยกเลิกแล้ว",
          all: "ทุกสถานะ",
        };
        active.push(["state", stateLabels[filters.state] || filters.state]);
      }
      chips.replaceChildren(...active.map(([key, text]) => {
        const chip = element("span", "search-chip", text);
        const remove = element("button", "", "×");
        remove.type = "button";
        remove.setAttribute("aria-label", `ล้างตัวกรอง ${text}`);
        remove.addEventListener("click", () => {
          if (key === "q") queryInput.value = "";
          if (key === "sport") { sportSelect.value = ""; updateVenueOptions(); }
          if (key === "venue") venueSelect.value = "";
          if (key === "venueType") venueTypeSelect.value = "";
          if (key === "date") {
            dateInput.value = "";
            updateTimeControls();
          }
          if (key === "time") { timeFromInput.value = ""; timeToInput.value = ""; }
          if (key === "state") stateSelect.value = "Open";
          loadSearchResults(1);
        });
        chip.append(remove);
        return chip;
      }));
      setVisible(chips, active.length > 0);
    }

    function updateVenueOptions() {
      const selectedSport = sportSelect.value;
      const available = venues.filter((venue) => !selectedSport
        || (venueSports.get(venue.id) || new Set()).has(Number(selectedSport)));
      const previous = venueSelect.value;
      venueSelect.replaceChildren(new Option("ทุกสนาม", ""));
      available.forEach((venue) => venueSelect.add(new Option(venue.name, String(venue.id))));
      venueSelect.disabled = available.length === 0;
      if (available.some((venue) => String(venue.id) === previous)) venueSelect.value = previous;
      else venueSelect.value = "";
    }

    function renderResults() {
      if (loadState !== "success") return;
      const resultsPage = parties;
      const filters = activeFilters();
      const hasFilters = Boolean(
        filters.q || filters.sport || filters.venue || filters.venueType
        || filters.date || filters.timeFrom || filters.timeTo || filters.state !== "Open"
      );
      resultHeading.textContent = hasFilters ? "ผลการค้นหา" : "กิจกรรมที่กำลังเปิดรับ";
      resultCount.textContent = `${totalResults} กิจกรรม`;
      renderChips();
      setVisible(status, false);
      setVisible(errorState, false);
      setVisible(loginState, false);
      setVisible(emptyState, totalResults === 0);
      setVisible(resultGrid, resultsPage.length > 0);
      setVisible(pagination, totalResults > pageSize);
      pageLabel.textContent = `หน้า ${currentPage} จาก ${Math.ceil(totalResults / pageSize)}`;
      previousPage.disabled = currentPage <= 1;
      nextPage.disabled = currentPage >= Math.ceil(totalResults / pageSize);
      if (!resultsPage.length) {
        resultGrid.replaceChildren();
        return;
      }

      resultGrid.replaceChildren(...resultsPage.map((party) => {
        const card = element("article", "search-card");
        const sportName = sportNames.get(party.sport_id) || "กีฬา";
        const venue = venueNames.get(party.venue_id);
        const stateLabels = {
          Open: "● เปิดรับอยู่",
          Full: "● เต็มแล้ว",
          InProgress: "● กำลังดำเนินการ",
          Completed: "● เสร็จสิ้น",
          Cancelled: "● ยกเลิกแล้ว",
        };
        const top = element("div", "search-card-top");
        top.append(
          element("span", "search-card-sport", sportName),
          element("span", `search-card-state search-card-state-${party.state.toLowerCase()}`, stateLabels[party.state] || party.state),
        );

        const main = element("div", "search-card-main");
        main.append(element("h3", "", party.title));
        const host = element("div", "search-card-host");
        host.append(element("span", "search-host-avatar", initials(party.host.display_name)), element("span", "", `ชวนโดย ${party.host.display_name}`));
        const meta = element("div", "search-card-meta");
        meta.append(
          element("span", "", `📍 ${venue ? venue.name : "สนามกีฬา"}`),
          element("span", "", `📅 ${formatDateTime(party.starts_at)}`),
          element("span", "", `👥 ${party.member_count}/${party.capacity} คน`),
        );
        main.append(host, meta);

        const footer = element("div", "search-card-footer");
        footer.append(element("span", "search-card-spots", `เหลือ ${party.remaining_slots} ที่`));
        const link = element("a", "search-card-link", "ดูรายละเอียด");
        link.href = `/parties/${party.id}/`;
        footer.append(link);
        card.append(top, main, footer);
        return card;
      }));
    }

    function showError(message) {
      loadState = "error";
      setVisible(status, false);
      setVisible(resultGrid, false);
      setVisible(emptyState, false);
      setVisible(pagination, false);
      setVisible(loginState, false);
      errorMessage.textContent = message;
      setVisible(errorState, true);
    }

    function searchParams(pageNumber) {
      const filters = activeFilters();
      const params = new URLSearchParams();
      if (filters.q) params.set("q", queryInput.value.trim());
      if (filters.sport) params.set("sport_id", filters.sport);
      if (filters.venue) params.set("venue_id", filters.venue);
      if (filters.venueType) params.set("venue_type", filters.venueType);
      if (filters.date) {
        const startsFrom = `${filters.date}T${filters.timeFrom || "00:00"}:00+07:00`;
        const endAtMidnight = !filters.timeTo || filters.timeTo === "00:00";
        const endDate = new Date(`${filters.date}T00:00:00+07:00`);
        if (endAtMidnight) endDate.setUTCDate(endDate.getUTCDate() + 1);
        const startsTo = endAtMidnight
          ? `${bangkokDateTimeParts(endDate.toISOString()).date}T00:00:00+07:00`
          : `${filters.date}T${filters.timeTo}:00+07:00`;
        params.set("starts_from", startsFrom);
        params.set("starts_to", startsTo);
      }
      if (filters.state !== "Open") params.set("state", filters.state);
      params.set("page", String(pageNumber));
      return params;
    }

    function updateSearchUrl(pageNumber) {
      const params = searchParams(pageNumber);
      const url = new URL(window.location.href);
      url.search = params.toString();
      window.history.replaceState({}, "", url);
    }

    async function loadSearchResults(pageNumber) {
      if (!searchReady) return;
      updateSearchUrl(pageNumber);
      const params = searchParams(pageNumber);
      const currentRequestId = ++requestId;
      loadState = "loading";
      status.textContent = `กำลังค้นหาปาร์ตี้ทั้งหมดที่ตรงกับตัวกรองจาก API (แสดงผลหน้าละ ${pageSize} รายการ)…`;
      setVisible(status, true);
      setVisible(resultGrid, false);
      setVisible(emptyState, false);
      setVisible(errorState, false);
      setVisible(loginState, false);
      setVisible(pagination, false);
      try {
        const response = await request(`/parties?${params.toString()}`, undefined, true);
        if (currentRequestId !== requestId) return;
        parties = response.data;
        totalResults = response.total;
        currentPage = response.page;
        loadState = "success";
        renderResults();
      } catch (error) {
        if (currentRequestId !== requestId) return;
        showError(error.message);
      }
    }

    function clearFilters() {
      form.reset();
      sportSelect.value = "";
      updateTimeControls();
      updateVenueOptions();
      loadSearchResults(1);
    }

    const initialParams = new URLSearchParams(window.location.search);
    queryInput.value = initialParams.get("q") || "";
    stateSelect.value = initialParams.get("state") || "Open";
    venueTypeSelect.value = initialParams.get("venue_type") || "";
    const initialStartsFrom = initialParams.get("starts_from");
    const initialStartsTo = initialParams.get("starts_to");
    let initialUrlError = null;
    try {
      const hasStartsFrom = initialParams.has("starts_from");
      const hasStartsTo = initialParams.has("starts_to");
      if (hasStartsFrom !== hasStartsTo) {
        throw new Error("ลิงก์ค้นหาต้องระบุช่วงวันเวลาทั้งสองขอบ");
      }
      if (hasStartsFrom) {
        if (!initialStartsFrom || !initialStartsTo) {
          throw new Error("ลิงก์ค้นหาต้องระบุช่วงวันเวลาที่ไม่ว่าง");
        }
        const start = searchDateTimeParts(initialStartsFrom);
        const end = searchDateTimeParts(initialStartsTo);
        dateInput.value = start.date;
        if (start.time !== "00:00") timeFromInput.value = start.time;
        const nextDate = new Date(`${dateInput.value}T00:00:00+07:00`);
        nextDate.setUTCDate(nextDate.getUTCDate() + 1);
        const nextDateValue = bangkokDateTimeParts(nextDate.toISOString()).date;
        if (end.date === dateInput.value && end.time !== "00:00") {
          timeToInput.value = end.time;
        } else if (end.date !== nextDateValue || end.time !== "00:00") {
          throw new Error("ช่วงวันเวลาในลิงก์ค้นหาไม่รองรับโดยตัวกรองหน้านี้");
        }
      }
      if (!hasStartsFrom && !hasStartsTo) dateInput.value = initialParams.get("date") || "";
    } catch (error) {
      initialUrlError = error.message;
    }
    updateTimeControls();

    form.addEventListener("submit", (event) => {
      event.preventDefault();
      updateVenueOptions();
      loadSearchResults(1);
    });
    sportSelect.addEventListener("change", updateVenueOptions);
    dateInput.addEventListener("change", updateTimeControls);
    previousPage.addEventListener("click", () => loadSearchResults(currentPage - 1));
    nextPage.addEventListener("click", () => loadSearchResults(currentPage + 1));
    page.querySelector("[data-filter-reset]").addEventListener("click", clearFilters);
    page.querySelector("[data-empty-reset]").addEventListener("click", clearFilters);
    page.querySelector("[data-search-retry]").addEventListener("click", () => window.location.reload());
    page.querySelector("[data-search-clear]").addEventListener("click", () => {
      const url = new URL(window.location.href);
      url.search = "";
      window.location.replace(url.toString());
    });

    if (initialUrlError) {
      showError(initialUrlError);
      return;
    }

    try {
      await request("/me");
    } catch (error) {
      if (error.status === 401) {
        loadState = "login";
        setVisible(status, false);
        setVisible(loginState, true);
        return;
      }
      showError(error.message);
      return;
    }

    try {
      sports = await request("/sports");
      sportNames = new Map(sports.map((sport) => [sport.id, sport.name]));
      sportSelect.replaceChildren(new Option("ทุกกีฬา", ""));
      sports.forEach((sport) => sportSelect.add(new Option(sport.name, String(sport.id))));

      const pages = await Promise.all(sports.map((sport) => allVenues(sport.id)));
      const venueById = new Map();
      sports.forEach((sport, index) => {
        pages[index].forEach((venue) => {
          if (!venueById.has(venue.id)) venueById.set(venue.id, venue);
          if (!venueSports.has(venue.id)) venueSports.set(venue.id, new Set());
          venueSports.get(venue.id).add(sport.id);
        });
      });
      venues = [...venueById.values()];
      venueNames = new Map(venues.map((venue) => [venue.id, venue]));
      updateVenueOptions();
      sportSelect.value = initialParams.get("sport_id") || "";
      updateVenueOptions();
      venueSelect.value = initialParams.get("venue_id") || "";
      searchReady = true;
      await loadSearchResults(initialParams.get("page") || 1);
    } catch (error) {
      searchReady = false;
      showError(error.message);
    }
  }

  function bangkokDateTimeParts(iso) {
    const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Bangkok", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(iso));
    const value = (type) => parts.find((part) => part.type === type).value;
    return { date: `${value("year")}-${value("month")}-${value("day")}`, time: `${value("hour")}:${value("minute")}` };
  }

  function formatHours(intervals) {
    const days = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"];
    if (!intervals.length) return "สนามนี้ยังไม่มีเวลาเปิดบริการ";
    return intervals.map((entry) => `${days[entry.weekday]} ${entry.opens_at.slice(0, 5)}–${entry.closes_at.slice(0, 5)} น.`).join(" · ");
  }

  function intervalsForDate(form, intervals) {
    const date = form.elements.date.value;
    if (!date || !intervals) return null;
    const weekday = (new Date(`${date}T12:00:00+07:00`).getUTCDay() + 6) % 7;
    return intervals.filter((entry) => entry.weekday === weekday);
  }

  function minutes(time) {
    const [hour, minute] = time.slice(0, 5).split(":").map(Number);
    return hour * 60 + minute;
  }

  function clock(minutesSinceMidnight) {
    return `${String(Math.floor(minutesSinceMidnight / 60)).padStart(2, "0")}:${String(minutesSinceMidnight % 60).padStart(2, "0")}`;
  }

  function hourChoices(intervals, start) {
    const choices = new Set();
    intervals.forEach((entry) => {
      const opens = minutes(entry.opens_at);
      const closes = minutes(entry.closes_at);
      const first = start === undefined ? opens : Math.max(opens, start + 60);
      for (let value = first; value <= closes; value += 60) {
        if (start === undefined ? value < closes : value <= closes) choices.add(clock(value));
      }
    });
    return [...choices].sort();
  }

  function replaceTimeChoices(select, choices, placeholder) {
    const selected = select.value;
    select.replaceChildren(new Option(placeholder, ""), ...choices.map((value) => new Option(value, value)));
    select.disabled = !choices.length;
    if (choices.includes(selected)) select.value = selected;
  }

  function updateTimeBounds(form, intervals, hoursBox) {
    const startInput = form.elements.start_time;
    const endInput = form.elements.end_time;
    const available = intervalsForDate(form, intervals);
    if (available === null) {
      replaceTimeChoices(startInput, [], "เลือกวันที่และสนามก่อน");
      replaceTimeChoices(endInput, [], "เลือกเวลาเริ่มก่อน");
      return false;
    }
    if (!available.length) {
      replaceTimeChoices(startInput, [], "สนามปิดในวันที่เลือก");
      replaceTimeChoices(endInput, [], "สนามปิดในวันที่เลือก");
      hoursBox.textContent = "สนามปิดในวันที่เลือก";
      hoursBox.classList.add("is-error");
      return false;
    }
    replaceTimeChoices(startInput, hourChoices(available), "เลือกเวลาเริ่ม");
    replaceTimeChoices(
      endInput,
      startInput.value ? hourChoices(available, minutes(startInput.value)) : [],
      "เลือกเวลาเริ่มก่อน"
    );
    return true;
  }

  function localScheduleValid(form, intervals) {
    const date = form.elements.date.value;
    const start = form.elements.start_time.value;
    const end = form.elements.end_time.value;
    if (!date || !intervals) return { valid: true, message: "" };
    const available = intervalsForDate(form, intervals);
    if (!available.length) return { valid: false, message: "สนามปิดในวันที่เลือก" };
    if (!start || !end) return { valid: true, message: "" };
    if (end <= start) return { valid: false, message: "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่ม" };
    const valid = available.some((entry) => entry.opens_at.slice(0, 5) <= start && end <= entry.closes_at.slice(0, 5));
    return valid ? { valid: true, message: "ช่วงเวลาที่เลือกอยู่ในเวลาเปิดบริการ" } : { valid: false, message: "ช่วงเวลาที่เลือกอยู่นอกเวลาเปิดสนาม" };
  }

  async function initPartyForm() {
    const page = document.querySelector("[data-party-form-page]");
    if (!page) return;
    const mode = page.dataset.mode;
    const partyId = page.dataset.partyId;
    const returnLinks = page.querySelectorAll("[data-party-form-return]");
    let returnTo = null;
    if (mode === "edit") {
      returnTo = window.PartyNavigation.resolveReturnTo({
        currentUrl: window.location.href,
        referrerUrl: "",
        fallback: "/my-parties/",
        partyId,
        origin: window.location.origin,
      });
      const detailUrl = window.PartyNavigation.withReturnTo(
        `/parties/${partyId}/`,
        returnTo,
        window.location.origin,
      );
      returnLinks.forEach((link) => { link.href = detailUrl; });
    } else {
      configurePreviousPageLinks(returnLinks);
    }
    if (!await currentUser()) { window.location.replace("/login/"); return; }
    const form = page.querySelector("[data-party-form]");
    const sportSelect = form.querySelector("[data-sport-select]");
    const venueSelect = form.querySelector("[data-venue-select]");
    const hoursBox = form.querySelector("[data-hours-message]");
    const errorBox = form.querySelector("[data-form-error]");
    let intervals = null;

    function renderScheduleCheck() {
      const boundsAvailable = updateTimeBounds(form, intervals, hoursBox);
      if (boundsAvailable && intervals && form.elements.date.value) {
        hoursBox.textContent = formatHours(intervals);
        hoursBox.classList.remove("is-error");
      }
      const check = localScheduleValid(form, intervals);
      if (intervals && form.elements.date.value && form.elements.start_time.value && form.elements.end_time.value) {
        hoursBox.textContent = check.message;
        hoursBox.classList.toggle("is-error", !check.valid);
      }
      return boundsAvailable ? check : { valid: false, message: "สนามปิดในวันที่เลือก" };
    }
    async function loadVenues(selectedVenue) {
      venueSelect.replaceChildren(new Option("เลือกสนาม", ""));
      venueSelect.disabled = true; intervals = null;
      if (!sportSelect.value) { venueSelect.options[0].text = "เลือกกีฬาก่อน"; hoursBox.textContent = "เลือกสนามเพื่อดูเวลาเปิดบริการ"; return; }
      try {
        const venues = await allVenues(sportSelect.value);
        venues.forEach((venue) => venueSelect.add(new Option(`${venue.name} — ${venue.location_text}`, venue.id)));
        venueSelect.disabled = false;
        if (selectedVenue) { venueSelect.value = String(selectedVenue); await loadHours(); }
      } catch (error) { hoursBox.textContent = error.message; hoursBox.classList.add("is-error"); }
    }
    async function loadHours() {
      intervals = null;
      if (!venueSelect.value) { hoursBox.textContent = "เลือกสนามเพื่อดูเวลาเปิดบริการ"; return; }
      try {
        const hours = await request(`/venues/${venueSelect.value}/opening-hours`);
        intervals = hours.intervals;
        hoursBox.textContent = formatHours(intervals);
        hoursBox.classList.remove("is-error");
        updateTimeBounds(form, intervals, hoursBox);
        renderScheduleCheck();
      } catch (error) { hoursBox.textContent = error.message; hoursBox.classList.add("is-error"); }
    }
    sportSelect.addEventListener("change", () => loadVenues());
    venueSelect.addEventListener("change", loadHours);
    [form.elements.date, form.elements.start_time, form.elements.end_time].forEach((input) => input.addEventListener("change", renderScheduleCheck));
    try {
      const sports = await request("/sports");
      sports.forEach((sport) => sportSelect.add(new Option(sport.name, sport.id)));
      if (mode === "edit") {
        const party = await request(`/parties/${partyId}`);
        if (!party.is_host) { window.location.replace(`/parties/${partyId}/`); return; }
        form.elements.title.value = party.title; form.elements.description.value = party.description;
        form.elements.capacity.value = party.capacity; sportSelect.value = String(party.sport_id);
        const starts = bangkokDateTimeParts(party.starts_at); const ends = bangkokDateTimeParts(party.ends_at);
        form.elements.date.value = starts.date; form.elements.start_time.value = starts.time; form.elements.end_time.value = ends.time;
        await loadVenues(party.venue_id);
      } else if (page.dataset.sportId) {
        sportSelect.value = page.dataset.sportId;
        await loadVenues(page.dataset.venueId);
      }
    } catch (error) { setError(errorBox, error.message); return; }
    form.addEventListener("submit", async function (event) {
      event.preventDefault(); setError(errorBox, "");
      const check = renderScheduleCheck();
      if (!form.reportValidity() || !check.valid) { if (!check.valid) setError(errorBox, check.message); return; }
      const date = form.elements.date.value;
      const payload = { title: form.elements.title.value, description: form.elements.description.value, sport_id: Number(sportSelect.value), venue_id: Number(venueSelect.value), starts_at: `${date}T${form.elements.start_time.value}:00+07:00`, ends_at: `${date}T${form.elements.end_time.value}:00+07:00`, capacity: Number(form.elements.capacity.value) };
      const submit = form.querySelector("[data-submit-party]"); submit.disabled = true;
      try {
        const party = await request(mode === "edit" ? `/parties/${partyId}` : "/parties", { method: mode === "edit" ? "PATCH" : "POST", body: JSON.stringify(payload) });
        if (mode === "edit") {
          const detailUrl = window.PartyNavigation.withReturnTo(
            `/parties/${party.id}/`,
            returnTo,
            window.location.origin,
          );
          window.location.replace(detailUrl);
        } else {
          window.location.assign(`/parties/${party.id}/`);
        }
      } catch (error) { setError(errorBox, error.message); submit.disabled = false; }
    });
  }

  function detailIcon(name) {
    const icons = {
      calendar: ["M8 3v3", "M16 3v3", "M4 8h16", "M6 4h12a2 2 0 0 1 2 2v14H4V6a2 2 0 0 1 2-2Z"],
      clock: ["M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z", "M12 6v6l4 2"],
      pin: ["M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z", "M12 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"],
    };
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    icons[name].forEach((pathData) => {
      const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", pathData);
      svg.append(path);
    });
    return svg;
  }

  function detailRow(label, value, iconName) {
    const row = element("span", "mp-info-item detail-info-item");
    row.setAttribute("aria-label", `${label}: ${value}`);
    row.append(detailIcon(iconName), element("span", "detail-info-value", value));
    return row;
  }

  async function initPartyDetail() {
    const root = document.querySelector("[data-party-detail]");
    if (!root) return;
    const partyId = root.dataset.partyId;
    const backLinks = document.querySelectorAll("[data-party-detail-back]");
    const returnTo = window.PartyNavigation.resolveReturnTo({
      currentUrl: window.location.href,
      referrerUrl: document.referrer,
      fallback: backLinks[0]?.getAttribute("href") || "/my-parties/",
      partyId,
      origin: window.location.origin,
    });
    backLinks.forEach((link) => { link.href = returnTo; });
    if (!await currentUser()) { window.location.replace("/login/"); return; }
    const loadingMessage = root.querySelector(".app-message");
    try {
      const party = await request(`/parties/${partyId}`);
      const [sports, venues] = await Promise.all([request("/sports"), request(`/venues?sport_id=${party.sport_id}`)]);
      const sport = sports.find((item) => item.id === party.sport_id);
      const venue = venues.find((item) => item.id === party.venue_id);
      const layout = element("div", "detail-layout party-detail-layout");
      const summary = element("article", "detail-card party-detail-summary mp-card");
      const summaryTop = element("div", "mp-card-top detail-summary-top");
      const summaryDetails = element("div", "mp-card-bottom detail-summary-bottom");
      const content = element("section", "detail-card detail-members-card mp-card");
      content.setAttribute("aria-label", "สมาชิกและคำขอเข้าร่วม");
      const summaryHeader = element("div", "mp-card-header");
      summaryHeader.append(
        element("span", "mp-tag-sport", sport ? sport.name : "กีฬา"),
        element("span", `mp-tag-status detail-state-${String(party.state).toLowerCase()}`, party.state),
      );
      summaryTop.append(
        summaryHeader,
        element("h3", "detail-summary-title", party.title),
      );
      const description = element("p", "detail-description detail-summary-description", party.description || "ไม่มีรายละเอียดเพิ่มเติม");

      const hostSummary = element("div", "detail-host-summary");
      const hostAvatar = element("span", "detail-host-avatar", initials(party.host.display_name));
      hostAvatar.setAttribute("aria-hidden", "true");
      const hostLink = element("a", "detail-host", party.host.display_name);
      hostLink.href = `/users/${party.host.id}/`;
      const hostIdentity = element("div", "detail-host-identity");
      hostIdentity.append(element("span", "detail-host-summary-label", "ผู้จัด:"), hostLink);
      hostSummary.append(hostAvatar, hostIdentity);
      summaryTop.append(hostSummary);
      summaryDetails.append(description);

      const startsAt = new Date(party.starts_at);
      const weekday = new Intl.DateTimeFormat("en-US", {
        weekday: "short",
        timeZone: "Asia/Bangkok",
      }).format(startsAt);
      const thaiWeekdays = { Sun: "อา.", Mon: "จ.", Tue: "อ.", Wed: "พ.", Thu: "พฤ.", Fri: "ศ.", Sat: "ส." };
      const dateTime = `${thaiWeekdays[weekday]} ${new Intl.DateTimeFormat("th-TH", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "Asia/Bangkok",
      }).format(startsAt)}`;
      const startTime = new Intl.DateTimeFormat("th-TH", {
        timeStyle: "short",
        timeZone: "Asia/Bangkok",
      }).format(new Date(party.starts_at));
      const endTime = new Intl.DateTimeFormat("th-TH", {
        timeStyle: "short",
        timeZone: "Asia/Bangkok",
      }).format(new Date(party.ends_at));
      const meta = element("div", "detail-meta detail-summary-meta");
      const venueRow = element("div", "mp-info-row detail-summary-info-row");
      venueRow.append(detailRow("สนาม", venue ? `${venue.name} — ${venue.location_text}` : "-", "pin"));
      const dateRow = element("div", "mp-info-row detail-summary-info-row");
      dateRow.append(detailRow("วันที่", dateTime, "calendar"));
      const timeRow = element("div", "mp-info-row detail-summary-info-row");
      timeRow.append(detailRow("เวลา", `${startTime}–${endTime} น.`, "clock"));
      meta.append(venueRow, dateRow, timeRow);
      summaryDetails.append(meta);

      const capacity = element("div", "detail-capacity");
      const capacityHeading = element("div", "detail-capacity-heading");
      const capacityCount = element("strong", "detail-capacity-count", `${party.member_count} / ${party.capacity} คน`);
      capacityHeading.append(element("span", "detail-capacity-label", "เข้าร่วมแล้ว"), capacityCount);
      const capacityProgress = element("div", "detail-capacity-progress");
      capacityProgress.setAttribute("role", "progressbar");
      capacityProgress.setAttribute("aria-label", "สัดส่วนผู้เข้าร่วม");
      capacityProgress.setAttribute("aria-valuemin", "0");
      capacityProgress.setAttribute("aria-valuemax", String(party.capacity));
      capacityProgress.setAttribute("aria-valuenow", String(party.member_count));
      const capacityFill = element("span", "detail-capacity-fill");
      capacityFill.style.width = `${Math.min(100, (party.member_count / party.capacity) * 100)}%`;
      capacityProgress.append(capacityFill);
      capacity.append(
        capacityHeading,
        element("span", "detail-capacity-remaining", `${party.remaining_slots} ที่ว่าง`),
        capacityProgress,
      );
      summaryDetails.append(capacity);
      summary.append(summaryTop, summaryDetails);

      const tabList = element("div", "detail-tabs");
      tabList.setAttribute("role", "tablist");
      tabList.setAttribute("aria-label", "ข้อมูลการเข้าร่วม");
      const tabs = [];
      function activateTab(active, moveFocus = false) {
        tabs.forEach(({ button, panel }) => {
          const selected = button === active.button;
          button.setAttribute("aria-selected", String(selected));
          button.tabIndex = selected ? 0 : -1;
          panel.hidden = !selected;
        });
        if (moveFocus) active.button.focus();
      }
      function addTab(key, label, panel, selected) {
        const button = element("button", "detail-tab", label);
        button.type = "button";
        button.id = `party-${key}-tab-${partyId}`;
        button.setAttribute("role", "tab");
        button.setAttribute("aria-controls", panel.id);
        button.setAttribute("aria-selected", String(selected));
        button.tabIndex = selected ? 0 : -1;
        panel.setAttribute("role", "tabpanel");
        panel.setAttribute("aria-labelledby", button.id);
        panel.tabIndex = 0;
        panel.hidden = !selected;
        const entry = { button, panel };
        tabs.push(entry);
        button.addEventListener("click", () => activateTab(entry));
        button.addEventListener("keydown", (event) => {
          let index = tabs.indexOf(entry);
          if (event.key === "ArrowRight") index = (index + 1) % tabs.length;
          else if (event.key === "ArrowLeft") index = (index - 1 + tabs.length) % tabs.length;
          else if (event.key === "Home") index = 0;
          else if (event.key === "End") index = tabs.length - 1;
          else return;
          event.preventDefault();
          activateTab(tabs[index], true);
        });
        tabList.append(button);
        return button;
      }

      const membersPanel = element("section", "detail-tab-panel");
      membersPanel.id = `party-members-panel-${partyId}`;
      membersPanel.setAttribute("aria-busy", "true");
      const membersTab = addTab("members", `สมาชิกปัจจุบัน ${party.member_count} คน`, membersPanel, true);
      const memberHint = element("p", "detail-members-hint", "รายชื่อผู้จัดและสมาชิกที่ยืนยันเข้าร่วมกิจกรรม");
      const memberStatus = element("p", "detail-members-state", "กำลังโหลดรายชื่อสมาชิก…");
      memberStatus.setAttribute("role", "status");
      memberStatus.setAttribute("aria-live", "polite");
      const memberSkeleton = element("div", "detail-member-skeleton");
      memberSkeleton.setAttribute("aria-hidden", "true");
      for (let index = 0; index < 3; index += 1) memberSkeleton.append(element("span"));
      const memberList = element("ul", "detail-member-list");
      memberList.setAttribute("aria-label", "รายชื่อสมาชิกปัจจุบัน");
      memberList.hidden = true;
      const memberRetry = element("button", "app-secondary detail-member-retry", "ลองโหลดรายชื่ออีกครั้ง");
      memberRetry.type = "button";
      memberRetry.hidden = true;
      memberRetry.addEventListener("click", loadMembers);
      membersPanel.append(memberHint, memberStatus, memberSkeleton, memberList, memberRetry);

      let requestsPanel = null;
      let requestsStatus = null;
      let requestsList = null;
      let requestsRetry = null;
      if (party.is_host) {
        requestsPanel = element("section", "detail-tab-panel");
        requestsPanel.id = `party-requests-panel-${partyId}`;
        requestsPanel.setAttribute("aria-busy", "true");
        addTab("requests", "คำขอเข้าร่วม", requestsPanel, false);
        requestsPanel.append(element("p", "detail-members-hint", "คำขอจากผู้เล่นที่รอการยืนยันจากผู้จัด"));
        requestsStatus = element("p", "detail-requests-state", "กำลังโหลดคำขอ…");
        requestsStatus.setAttribute("role", "status");
        requestsStatus.setAttribute("aria-live", "polite");
        requestsList = element("ul", "detail-request-list");
        requestsList.setAttribute("aria-label", "คำขอเข้าร่วมที่รออนุมัติ");
        requestsList.hidden = true;
        requestsRetry = element("button", "app-secondary detail-member-retry", "ลองโหลดคำขออีกครั้ง");
        requestsRetry.type = "button";
        requestsRetry.hidden = true;
        requestsRetry.addEventListener("click", loadRequests);
        requestsPanel.append(requestsStatus, requestsList, requestsRetry);
      }
      content.append(tabList, membersPanel);
      if (requestsPanel) content.append(requestsPanel);

      const actions = element("div", "detail-overview-actions");
      let loadJoinAction = null;
      if (party.is_host) {
        const edit = element("a", "app-primary", "แก้ไขปาร์ตี้");
        edit.href = window.PartyNavigation.withReturnTo(
          `/parties/${party.id}/edit/`,
          returnTo,
          window.location.origin,
        );
        const cancel = element("button", "app-secondary app-danger", "ยกเลิกปาร์ตี้");
        cancel.addEventListener("click", async () => {
          if (!window.confirm("ต้องการยกเลิกปาร์ตี้นี้หรือไม่?")) return;
          cancel.disabled = true;
          try {
            await request(`/parties/${party.id}/cancel`, { method: "POST", body: "{}" });
            window.location.reload();
          } catch (error) {
            cancel.disabled = false;
            alert(error.message);
          }
        });
        actions.append(edit, cancel);
      } else if (party.is_member) {
        actions.append(element("div", "app-success", "คุณเป็นสมาชิกของปาร์ตี้นี้แล้ว"));
      } else if (party.state === "Open") {
        const joinStatus = element("p", "app-message", "กำลังตรวจสอบคำขอเข้าร่วม…");
        joinStatus.setAttribute("role", "status");
        joinStatus.setAttribute("aria-live", "polite");
        actions.append(joinStatus);
        loadJoinAction = async function () {
          try {
            const existing = await request(`/parties/${party.id}/join-requests/me`);
            if (existing && existing.status === "Pending") {
              joinStatus.className = "app-success";
              joinStatus.textContent = "ส่งคำขอเข้าร่วมแล้ว กำลังรอการตอบรับ";
              return;
            }
            const join = element("button", "app-primary", "ขอเข้าร่วม");
            join.type = "button";
            join.addEventListener("click", async () => {
              join.disabled = true;
              try {
                await request(`/parties/${party.id}/join-requests`, { method: "POST", body: "{}" });
                window.location.reload();
              } catch (error) {
                join.disabled = false;
                alert(error.message);
              }
            });
            joinStatus.replaceWith(join);
          } catch (error) {
            joinStatus.className = "app-error";
            joinStatus.textContent = error.message;
          }
        }
      } else {
        actions.append(element("div", "app-message", "ปาร์ตี้นี้ไม่เปิดรับคำขอในขณะนี้"));
      }
      const contentColumn = element("div", "party-detail-content-column");
      contentColumn.append(content, actions);
      layout.append(summary, contentColumn);
      loadingMessage.replaceWith(layout);
      root.setAttribute("aria-busy", "false");

      async function loadMembers() {
        membersPanel.setAttribute("aria-busy", "true");
        memberStatus.className = "detail-members-state";
        memberStatus.setAttribute("role", "status");
        memberStatus.textContent = "กำลังโหลดรายชื่อสมาชิก…";
        memberStatus.hidden = false;
        memberSkeleton.hidden = false;
        memberList.hidden = true;
        memberRetry.hidden = true;
        try {
          const result = await request(`/parties/${partyId}/members`);
          if (!result || !Array.isArray(result.members) || !Number.isInteger(result.member_count)) {
            throw new Error("ข้อมูลรายชื่อสมาชิกไม่ถูกต้อง");
          }
          memberList.replaceChildren(...result.members.map((member) => {
            const item = element("li", "detail-member-item");
            const name = member.display_name || (member.role === "Host" ? "ผู้จัดกิจกรรม" : "ผู้ใช้");
            const avatar = element("span", "detail-member-avatar", initials(name));
            avatar.setAttribute("aria-hidden", "true");
            const roleText = member.role === "Host" ? "Host" : "Member";
            const role = element("span", `detail-member-role${member.role === "Host" ? " is-host" : ""}`, roleText);
            item.append(avatar, element("span", "detail-member-name", name), role);
            return item;
          }));
          membersTab.textContent = `สมาชิกปัจจุบัน ${result.member_count} คน`;
          summary.querySelector(".detail-capacity-count").textContent = `${result.member_count} / ${party.capacity} คน`;
          const progress = summary.querySelector(".detail-capacity-progress");
          progress.setAttribute("aria-valuenow", String(result.member_count));
          progress.querySelector(".detail-capacity-fill").style.width = `${Math.min(100, (result.member_count / party.capacity) * 100)}%`;
          summary.querySelector(".detail-capacity-remaining").textContent = `${Math.max(0, party.capacity - result.member_count)} ที่ว่าง`;
          memberStatus.className = "detail-members-state is-empty";
          memberStatus.textContent = result.members.length ? "" : "ยังไม่มีสมาชิกที่แสดงได้";
          memberStatus.hidden = Boolean(result.members.length);
          memberSkeleton.hidden = true;
          memberList.hidden = !result.members.length;
          membersPanel.setAttribute("aria-busy", "false");
        } catch (error) {
          memberStatus.className = "detail-members-state is-error";
          memberStatus.setAttribute("role", "alert");
          memberStatus.textContent = error.status === 403
            ? "เฉพาะผู้จัดกิจกรรมหรือสมาชิกปัจจุบันเท่านั้นที่ดูรายชื่อสมาชิกได้"
            : error.message;
          memberStatus.hidden = false;
          memberSkeleton.hidden = true;
          memberList.hidden = true;
          memberRetry.hidden = error.status === 403;
          membersPanel.setAttribute("aria-busy", "false");
        }
      }

      async function loadRequests() {
        if (!requestsPanel) return;
        requestsPanel.setAttribute("aria-busy", "true");
        requestsStatus.className = "detail-requests-state";
        requestsStatus.setAttribute("role", "status");
        requestsStatus.textContent = "กำลังโหลดคำขอ…";
        requestsStatus.hidden = false;
        requestsList.hidden = true;
        requestsRetry.hidden = true;
        try {
          const requests = await request(`/parties/${partyId}/join-requests/pending`);
          if (!Array.isArray(requests)) throw new Error("ข้อมูลคำขอเข้าร่วมไม่ถูกต้อง");
          requestsList.replaceChildren(...requests.map((entry) => {
            const row = element("li", "detail-request-item");
            const name = element("span", "detail-request-name", entry.display_name || "ผู้สมัคร");
            const state = element("span", "detail-request-status", "รออนุมัติ");
            const controls = element("div", "detail-request-actions");
            ["Approved", "Rejected"].forEach((decision) => {
              const button = element("button", "", decision === "Approved" ? "อนุมัติ" : "ไม่อนุมัติ");
              button.type = "button";
              button.dataset.requestDecision = decision;
              button.addEventListener("click", async () => {
                controls.querySelectorAll("button").forEach((control) => { control.disabled = true; });
                requestsStatus.textContent = "กำลังบันทึกการตัดสินใจ…";
                requestsStatus.hidden = false;
                try {
                  await request(`/parties/${partyId}/join-requests/${entry.id}/decision`, {
                    method: "POST",
                    body: JSON.stringify({ status: decision }),
                  });
                  window.location.reload();
                } catch (error) {
                  requestsStatus.className = "detail-requests-state is-error";
                  requestsStatus.setAttribute("role", "alert");
                  requestsStatus.textContent = error.message;
                  controls.querySelectorAll("button").forEach((control) => { control.disabled = false; });
                }
              });
              controls.append(button);
            });
            row.append(name, state, controls);
            return row;
          }));
          requestsStatus.className = "detail-requests-state is-empty";
          requestsStatus.textContent = requests.length ? "" : "ไม่มีคำขอที่รออนุมัติ";
          requestsStatus.hidden = Boolean(requests.length);
          requestsList.hidden = !requests.length;
          requestsPanel.setAttribute("aria-busy", "false");
        } catch (error) {
          requestsStatus.className = "detail-requests-state is-error";
          requestsStatus.setAttribute("role", "alert");
          requestsStatus.textContent = error.message;
          requestsStatus.hidden = false;
          requestsRetry.hidden = false;
          requestsPanel.setAttribute("aria-busy", "false");
        }
      }

      const initialLoads = [loadMembers()];
      if (party.is_host) initialLoads.push(loadRequests());
      if (loadJoinAction) initialLoads.push(loadJoinAction());
      await Promise.all(initialLoads);
    } catch (error) {
      loadingMessage.className = "app-error";
      loadingMessage.setAttribute("role", "alert");
      loadingMessage.textContent = error.message;
      root.setAttribute("aria-busy", "false");
    }
  }

  document.addEventListener("DOMContentLoaded", async function () {
    const navReady = initNavigation();
    await Promise.all([navReady, initLogin(), initHome(), initSearch(), initPartyForm(), initPartyDetail()]);
  });
})();
