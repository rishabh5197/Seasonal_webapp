document.addEventListener("DOMContentLoaded", () => {
  const root = document.documentElement;
  const themeToggle = document.querySelector("[data-theme-toggle]");
  const bannerRoot = document.querySelector("[data-banner-carousel]");
  const banners = bannerRoot ? Array.from(bannerRoot.querySelectorAll("[data-banner-slide]")) : [];
  const heroBanners = Array.from(document.querySelectorAll("[data-hero-banner]"));
  const rotationMs = 10000;

  const storedTheme = window.localStorage.getItem("theme");
  const systemTheme = window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  const initialTheme = storedTheme || systemTheme;
  root.dataset.theme = initialTheme;

  if (themeToggle) {
    const updateLabel = () => {
      const isLight = root.dataset.theme === "light";
      themeToggle.classList.toggle("is-light", isLight);
      themeToggle.setAttribute("aria-pressed", String(isLight));
      themeToggle.setAttribute("aria-label", isLight ? "Switch to dark mode" : "Switch to light mode");
    };

    updateLabel();
    themeToggle.addEventListener("click", () => {
      root.dataset.theme = root.dataset.theme === "light" ? "dark" : "light";
      window.localStorage.setItem("theme", root.dataset.theme);
      updateLabel();
    });
  }

  if (banners.length > 1) {
    let activeIndex = banners.findIndex((banner) => banner.classList.contains("is-active"));
    if (activeIndex < 0) {
      activeIndex = 0;
    }

    const showBanner = (index) => {
      banners.forEach((banner, current) => banner.classList.toggle("is-active", current === index));
    };

    showBanner(activeIndex);
    window.setInterval(() => {
      activeIndex = (activeIndex + 1) % banners.length;
      showBanner(activeIndex);
    }, rotationMs);
  }

  if (heroBanners.length) {
    let heroIndex = 0;
    const showHeroBanner = (index) => {
      heroBanners.forEach((banner, current) => banner.classList.toggle("is-active", current === index));
    };

    showHeroBanner(heroIndex);
    if (heroBanners.length > 1) {
      window.setInterval(() => {
        heroIndex = (heroIndex + 1) % heroBanners.length;
        showHeroBanner(heroIndex);
      }, rotationMs);
    }
  }

  const monthFormatter = new Intl.DateTimeFormat("en-GB", {
    month: "long",
    year: "numeric",
  });
  const displayFormatter = new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
  const weekdayLabels = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
  const yearBounds = { min: 1900, max: 2100 };
  const monthIndexLookup = {
    jan: 0,
    january: 0,
    feb: 1,
    february: 1,
    mar: 2,
    march: 2,
    apr: 3,
    april: 3,
    may: 4,
    jun: 5,
    june: 5,
    jul: 6,
    july: 6,
    aug: 7,
    august: 7,
    sep: 8,
    sept: 8,
    september: 8,
    oct: 9,
    october: 9,
    nov: 10,
    november: 10,
    dec: 11,
    december: 11,
  };
  const pad2 = (value) => String(value).padStart(2, "0");
  const normalizeToLocalNoon = (date) => new Date(date.getFullYear(), date.getMonth(), date.getDate(), 12, 0, 0, 0);
  const startOfMonth = (date) => new Date(date.getFullYear(), date.getMonth(), 1);
  const addMonths = (date, amount) => new Date(date.getFullYear(), date.getMonth() + amount, 1);
  const addYears = (date, amount) => new Date(date.getFullYear() + amount, date.getMonth(), 1);
  const clampYear = (year) => Math.min(yearBounds.max, Math.max(yearBounds.min, year));
  const formatRawDate = (date) => `${pad2(date.getDate())}-${pad2(date.getMonth() + 1)}-${date.getFullYear()}`;
  const formatDisplayDate = (date) => displayFormatter.format(normalizeToLocalNoon(date));
  const parseTypedDate = (value) => {
    const trimmed = (value || "").trim();
    if (!trimmed) {
      return null;
    }

    const rawMatch = /^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/.exec(trimmed);
    if (rawMatch) {
      const [, dayText, monthText, yearText] = rawMatch;
      const date = new Date(Number(yearText), Number(monthText) - 1, Number(dayText));
      if (!Number.isNaN(date.getTime()) && date.getDate() === Number(dayText) && date.getMonth() === Number(monthText) - 1) {
        return date;
      }
      return null;
    }

    const prettyMatch = /^(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})$/.exec(trimmed);
    if (prettyMatch) {
      const [, dayText, monthText, yearText] = prettyMatch;
      const monthIndex = monthIndexLookup[monthText.toLowerCase()];
      if (monthIndex === undefined) {
        return null;
      }
      const date = new Date(Number(yearText), monthIndex, Number(dayText));
      if (!Number.isNaN(date.getTime()) && date.getDate() === Number(dayText) && date.getMonth() === monthIndex) {
        return date;
      }
    }

    return null;
  };

  document.querySelectorAll("[data-date-picker]").forEach((picker) => {
    const dateInput = picker.querySelector("[data-date-input]");
    const toggleButton = picker.querySelector("[data-date-toggle]");
    const panel = picker.querySelector("[data-date-panel]");

    if (!dateInput || !toggleButton || !panel) {
      return;
    }

    let selectedDate = parseTypedDate(dateInput.value) || null;
    let viewDate = startOfMonth(selectedDate || new Date());

    const syncDisplay = () => {
      dateInput.value = selectedDate ? formatDisplayDate(selectedDate) : "";
      dateInput.dispatchEvent(new Event("change", { bubbles: true }));
    };

    const closePicker = () => {
      panel.hidden = true;
      picker.classList.remove("is-open");
    };

    const openPicker = () => {
      renderPicker();
      panel.hidden = false;
      picker.classList.add("is-open");
    };

    const setSelectedDate = (date) => {
      selectedDate = normalizeToLocalNoon(date);
      viewDate = startOfMonth(selectedDate);
      syncDisplay();
      renderPicker();
    };

    const renderPicker = () => {
      const year = viewDate.getFullYear();
      const month = viewDate.getMonth();
      const firstDay = new Date(year, month, 1);
      const daysInMonth = new Date(year, month + 1, 0).getDate();
      const leadingOffset = (firstDay.getDay() + 6) % 7;
      const cells = [];

      for (let i = 0; i < leadingOffset; i += 1) {
        cells.push(`<button type="button" class="date-picker__day is-empty" tabindex="-1" aria-hidden="true"></button>`);
      }

      for (let day = 1; day <= daysInMonth; day += 1) {
        const current = new Date(year, month, day);
        const isSelected = selectedDate && current.getFullYear() === selectedDate.getFullYear() && current.getMonth() === selectedDate.getMonth() && current.getDate() === selectedDate.getDate();
        cells.push(`
          <button type="button" class="date-picker__day${isSelected ? " is-selected" : ""}" data-date-day="${formatRawDate(current)}">
            ${day}
          </button>
        `);
      }

      panel.innerHTML = `
        <div class="date-picker__shell">
          <div class="date-picker__top">
            <div class="date-picker__headline">
              <p class="date-picker__label">Birth date</p>
              <strong>${monthFormatter.format(viewDate)}</strong>
              <label class="date-picker__year-jump">
                <span class="sr-only">Jump to year</span>
                <input
                  type="text"
                  min="${yearBounds.min}"
                  max="${yearBounds.max}"
                  maxlength="4"
                  inputmode="numeric"
                  pattern="[0-9]{4}"
                  data-date-year-jump
                  value="${year}"
                  aria-label="Jump to year"
                >
              </label>
            </div>
            <div class="date-picker__nav">
              <button type="button" class="date-picker__nav-btn" data-date-prev-decade aria-label="Previous decade">&#8810;</button>
              <button type="button" class="date-picker__nav-btn" data-date-prev aria-label="Previous month">&#8592;</button>
              <button type="button" class="date-picker__nav-btn date-picker__nav-btn--text" data-date-today aria-label="Jump to today">Today</button>
              <button type="button" class="date-picker__nav-btn" data-date-next aria-label="Next month">&#8594;</button>
              <button type="button" class="date-picker__nav-btn" data-date-next-decade aria-label="Next decade">&#8811;</button>
            </div>
          </div>
          <div class="date-picker__weekdays">
            ${weekdayLabels.map((day) => `<span>${day}</span>`).join("")}
          </div>
          <div class="date-picker__grid">
            ${cells.join("")}
          </div>
        </div>
      `;
    };

    const commitTypedValue = () => {
      const parsed = parseTypedDate(dateInput.value);
      if (parsed) {
        selectedDate = normalizeToLocalNoon(parsed);
        viewDate = startOfMonth(selectedDate);
        syncDisplay();
        renderPicker();
        return true;
      }
      if (!dateInput.value.trim()) {
        selectedDate = null;
        renderPicker();
        return true;
      }
      return false;
    };

    renderPicker();
    closePicker();

    const openIfNeeded = () => {
      if (!picker.classList.contains("is-open")) {
        openPicker();
      }
    };

    toggleButton.addEventListener("click", (event) => {
      event.preventDefault();
      if (picker.classList.contains("is-open")) {
        closePicker();
      } else {
        openPicker();
      }
      dateInput.focus();
    });

    dateInput.addEventListener("focus", () => {
      openIfNeeded();
      const parsed = parseTypedDate(dateInput.value);
      if (selectedDate && parsed && parsed.getTime() === selectedDate.getTime()) {
        dateInput.value = formatRawDate(selectedDate);
      } else if (selectedDate && dateInput.value === formatDisplayDate(selectedDate)) {
        dateInput.value = formatRawDate(selectedDate);
      }
      window.requestAnimationFrame(() => {
        try {
          dateInput.select();
        } catch (error) {
          void error;
        }
      });
    });

    dateInput.addEventListener("blur", () => {
      window.setTimeout(() => {
        if (picker.contains(document.activeElement) && document.activeElement !== dateInput) {
          return;
        }

        commitTypedValue();
        if (selectedDate) {
          dateInput.value = formatDisplayDate(selectedDate);
        }
        closePicker();
      }, 0);
    });

    dateInput.addEventListener("input", () => {
      const parsed = parseTypedDate(dateInput.value);
      if (parsed) {
        selectedDate = normalizeToLocalNoon(parsed);
        viewDate = startOfMonth(selectedDate);
        syncDisplay();
        renderPicker();
        return;
      }

      if (dateInput.value.trim()) {
        openIfNeeded();
      }
    });

    picker.addEventListener("click", (event) => {
      if (!picker.classList.contains("is-open")) {
        if (event.target.closest("[data-date-day], [data-date-prev], [data-date-prev-decade], [data-date-next], [data-date-next-decade], [data-date-today], [data-date-toggle]")) {
          return;
        }
        openIfNeeded();
      }
    });

    panel.addEventListener("click", (event) => {
      const dayButton = event.target.closest("[data-date-day]");
      if (dayButton) {
        const picked = parseTypedDate(dayButton.dataset.dateDay);
        if (picked) {
          setSelectedDate(picked);
          closePicker();
        }
        return;
      }

      if (event.target.closest("[data-date-prev-decade]")) {
        viewDate = addMonths(viewDate, -120);
        renderPicker();
      }

      if (event.target.closest("[data-date-prev]")) {
        viewDate = addMonths(viewDate, -1);
        renderPicker();
      }

      if (event.target.closest("[data-date-today]")) {
        const today = normalizeToLocalNoon(new Date());
        viewDate = startOfMonth(today);
        setSelectedDate(today);
        renderPicker();
      }

      if (event.target.closest("[data-date-next]")) {
        viewDate = addMonths(viewDate, 1);
        renderPicker();
      }

      if (event.target.closest("[data-date-next-decade]")) {
        viewDate = addMonths(viewDate, 120);
        renderPicker();
      }
    });

    panel.addEventListener("change", (event) => {
      const yearJump = event.target.closest("[data-date-year-jump]");
      if (!yearJump) {
        return;
      }

      const nextYear = Number.parseInt(yearJump.value, 10);
      if (!Number.isFinite(nextYear)) {
        yearJump.value = String(viewDate.getFullYear());
        return;
      }

      viewDate = new Date(clampYear(nextYear), viewDate.getMonth(), 1);
      renderPicker();
    });

    panel.addEventListener("keydown", (event) => {
      const yearJump = event.target.closest("[data-date-year-jump]");
      if (!yearJump || event.key !== "Enter") {
        return;
      }

      event.preventDefault();
      yearJump.dispatchEvent(new Event("change", { bubbles: true }));
    });

    document.addEventListener("click", (event) => {
      const path = typeof event.composedPath === "function" ? event.composedPath() : [];
      if (picker.classList.contains("is-open") && !path.includes(picker)) {
        closePicker();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && picker.classList.contains("is-open")) {
        closePicker();
      }
      if (picker.classList.contains("is-open") && event.key === "PageUp") {
        if (event.shiftKey) {
          viewDate = addYears(viewDate, -1);
        } else {
          viewDate = addMonths(viewDate, -1);
        }
        renderPicker();
      }
      if (picker.classList.contains("is-open") && event.key === "PageDown") {
        if (event.shiftKey) {
          viewDate = addYears(viewDate, 1);
        } else {
          viewDate = addMonths(viewDate, 1);
        }
        renderPicker();
      }
    });
  });

  const authModeTabs = Array.from(document.querySelectorAll("[data-auth-mode]"));
  const authModePanels = Array.from(document.querySelectorAll("[data-auth-panel]"));
  if (authModeTabs.length && authModePanels.length) {
    const showAuthMode = (mode) => {
      authModeTabs.forEach((tab) => {
        tab.classList.toggle("is-active", tab.dataset.authMode === mode);
      });
      authModePanels.forEach((panel) => {
        panel.classList.toggle("is-active", panel.dataset.authPanel === mode);
      });
    };

    const defaultMode = authModeTabs.find((tab) => tab.classList.contains("is-active"))?.dataset.authMode || "password";
    showAuthMode(defaultMode);
    authModeTabs.forEach((tab) => {
      tab.addEventListener("click", () => {
        showAuthMode(tab.dataset.authMode);
      });
    });
  }

  const resendLink = document.querySelector("[data-resend-seconds]");
  if (resendLink) {
    const countdownNode = resendLink.querySelector("[data-resend-countdown]");
    let remaining = Number.parseInt(resendLink.dataset.resendSeconds, 10);
    if (!Number.isFinite(remaining)) {
      remaining = 0;
    }

    const syncResendState = () => {
      if (countdownNode) {
        countdownNode.textContent = String(remaining);
      }
      if (remaining <= 0) {
        resendLink.classList.remove("is-disabled");
        resendLink.removeAttribute("aria-disabled");
        resendLink.removeAttribute("data-resend-seconds");
      }
    };

    syncResendState();
    if (remaining > 0) {
      const timer = window.setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
          remaining = 0;
          syncResendState();
          window.clearInterval(timer);
        } else {
          syncResendState();
        }
      }, 1000);

      resendLink.addEventListener("click", (event) => {
        if (remaining > 0) {
          event.preventDefault();
        }
      });
    }
  }

  document.querySelectorAll("[data-countdown]").forEach((node) => {
    const target = new Date(node.getAttribute("data-countdown"));
    if (!Number.isNaN(target.getTime())) {
      const delta = Math.max(0, target.getTime() - Date.now());
      const days = Math.floor(delta / 86400000);
      const hours = Math.floor((delta % 86400000) / 3600000);
      node.textContent = `${days}d ${hours}h left`;
    }
  });
});
