/**
 * COAST Command — shell stubs (Phase 1.1 / 1.4–1.5)
 * Vanilla JS only. Keep small; wire real handlers later.
 */
(function () {
  "use strict";

  var VIEWS = [
    { id: "fleet", label: "Fleet", key: "1" },
    { id: "engine", label: "Engine", key: "2" },
    { id: "model", label: "Model", key: "3" },
    { id: "training", label: "Training", key: "4" },
    { id: "evidence", label: "Evidence", key: "5" },
    { id: "sessions", label: "Sessions", key: "6" },
  ];

  var state = {
    view: "fleet",
    presentation: false,
    paletteOpen: false,
    shortcutsOpen: false,
    connectionStale: false,
    lastOkAt: Date.now(),
    consoleActive: false,
  };

  var STALE_MS = 4000;

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }

  function $$(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function isTypingTarget(el) {
    if (!el) return false;
    var tag = (el.tagName || "").toLowerCase();
    return (
      tag === "input" ||
      tag === "textarea" ||
      tag === "select" ||
      el.isContentEditable
    );
  }

  /* ——— Views ——— */

  function setView(id) {
    if (!VIEWS.some(function (v) { return v.id === id; })) return;
    state.view = id;
    $$("[data-view]").forEach(function (el) {
      var on = el.getAttribute("data-view") === id;
      el.hidden = !on;
      el.classList.toggle("is-active", on);
    });
    $$(".icon-rail__item").forEach(function (el) {
      var on = el.getAttribute("data-nav") === id;
      el.classList.toggle("is-active", on);
      if (on) el.setAttribute("aria-current", "page");
      else el.removeAttribute("aria-current");
    });
    document.dispatchEvent(
      new CustomEvent("coast:view", { detail: { view: id } })
    );
  }

  /* ——— Presentation mode (P) ——— */

  function setPresentation(on) {
    state.presentation = !!on;
    document.body.classList.toggle("is-presentation", state.presentation);
    document.dispatchEvent(
      new CustomEvent("coast:presentation", {
        detail: { on: state.presentation },
      })
    );
  }

  function togglePresentation() {
    setPresentation(!state.presentation);
  }

  /* ——— Command palette (Ctrl/Cmd-K) ——— */

  function ensurePalette() {
    var backdrop = $("#coast-palette");
    if (backdrop) return backdrop;

    backdrop = document.createElement("div");
    backdrop.id = "coast-palette";
    backdrop.className = "palette-backdrop";
    backdrop.setAttribute("role", "dialog");
    backdrop.setAttribute("aria-label", "Command palette");
    backdrop.innerHTML =
      '<div class="palette">' +
      '<input class="palette__input" type="text" placeholder="Jump to view, train, pair, sign out…" aria-label="Command" />' +
      '<ul class="palette__list" role="listbox"></ul>' +
      "</div>";
    document.body.appendChild(backdrop);

    backdrop.addEventListener("click", function (e) {
      if (e.target === backdrop) closePalette();
    });

    var input = $(".palette__input", backdrop);
    input.addEventListener("input", function () {
      renderPaletteItems(input.value);
    });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        e.preventDefault();
        closePalette();
      } else if (e.key === "Enter") {
        e.preventDefault();
        var active = $(".palette__item.is-active", backdrop);
        if (active) runPaletteAction(active.getAttribute("data-action"));
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        movePaletteSelection(e.key === "ArrowDown" ? 1 : -1);
      }
    });

    return backdrop;
  }

  function defaultPaletteActions() {
    return VIEWS.map(function (v) {
      return {
        action: "view:" + v.id,
        label: "Go to " + v.label,
        hint: v.key,
      };
    }).concat([
      { action: "train", label: "Start training", hint: "" },
      { action: "pair", label: "Mint pairing code", hint: "" },
      { action: "signout", label: "Sign out", hint: "" },
      { action: "presentation", label: "Toggle presentation mode", hint: "P" },
      { action: "shortcuts", label: "Keyboard shortcuts", hint: "?" },
    ]);
  }

  function renderPaletteItems(query) {
    var list = $(".palette__list", $("#coast-palette"));
    if (!list) return;
    var q = (query || "").trim().toLowerCase();
    var items = defaultPaletteActions().filter(function (a) {
      return !q || a.label.toLowerCase().indexOf(q) !== -1;
    });
    list.innerHTML = items
      .map(function (a, i) {
        return (
          '<li class="palette__item' +
          (i === 0 ? " is-active" : "") +
          '" role="option" data-action="' +
          a.action +
          '"><span>' +
          a.label +
          '</span><span class="palette__hint">' +
          (a.hint || "") +
          "</span></li>"
        );
      })
      .join("");

    $$(".palette__item", list).forEach(function (el) {
      el.addEventListener("click", function () {
        runPaletteAction(el.getAttribute("data-action"));
      });
    });
  }

  function movePaletteSelection(delta) {
    var items = $$(".palette__item", $("#coast-palette"));
    if (!items.length) return;
    var idx = items.findIndex(function (el) {
      return el.classList.contains("is-active");
    });
    if (idx < 0) idx = 0;
    items[idx].classList.remove("is-active");
    idx = (idx + delta + items.length) % items.length;
    items[idx].classList.add("is-active");
    items[idx].scrollIntoView({ block: "nearest" });
  }

  function runPaletteAction(action) {
    closePalette();
    if (!action) return;
    if (action.indexOf("view:") === 0) {
      setView(action.slice(5));
      return;
    }
    if (action === "presentation") {
      togglePresentation();
      return;
    }
    if (action === "shortcuts") {
      openShortcuts();
      return;
    }
    document.dispatchEvent(
      new CustomEvent("coast:command", { detail: { action: action } })
    );
  }

  function openPalette() {
    var backdrop = ensurePalette();
    state.paletteOpen = true;
    backdrop.classList.add("is-open");
    var input = $(".palette__input", backdrop);
    input.value = "";
    renderPaletteItems("");
    input.focus();
  }

  function closePalette() {
    var backdrop = $("#coast-palette");
    if (!backdrop) return;
    state.paletteOpen = false;
    backdrop.classList.remove("is-open");
  }

  function togglePalette() {
    if (state.paletteOpen) closePalette();
    else openPalette();
  }

  /* ——— Shortcuts sheet (?) ——— */

  function ensureShortcuts() {
    var el = $("#coast-shortcuts");
    if (el) return el;
    el = document.createElement("div");
    el.id = "coast-shortcuts";
    el.className = "shortcuts-sheet";
    el.innerHTML =
      '<div class="shortcuts-sheet__panel" role="dialog" aria-label="Keyboard shortcuts">' +
      "<h2 class=\"h2\" style=\"margin-bottom:16px\">Shortcuts</h2>" +
      '<div class="shortcuts-sheet__row"><span>Fleet</span><kbd>1</kbd></div>' +
      '<div class="shortcuts-sheet__row"><span>Engine</span><kbd>2</kbd></div>' +
      '<div class="shortcuts-sheet__row"><span>Training</span><kbd>3</kbd></div>' +
      '<div class="shortcuts-sheet__row"><span>Evidence</span><kbd>4</kbd></div>' +
      '<div class="shortcuts-sheet__row"><span>Sessions</span><kbd>5</kbd></div>' +
      '<div class="shortcuts-sheet__row"><span>Command palette</span><kbd>Ctrl/⌘ K</kbd></div>' +
      '<div class="shortcuts-sheet__row"><span>Presentation mode</span><kbd>P</kbd></div>' +
      '<div class="shortcuts-sheet__row"><span>This sheet</span><kbd>?</kbd></div>' +
      "</div>";
    document.body.appendChild(el);
    el.addEventListener("click", function (e) {
      if (e.target === el) closeShortcuts();
    });
    return el;
  }

  function openShortcuts() {
    ensureShortcuts().classList.add("is-open");
    state.shortcutsOpen = true;
  }

  function closeShortcuts() {
    var el = $("#coast-shortcuts");
    if (el) el.classList.remove("is-open");
    state.shortcutsOpen = false;
  }

  function toggleShortcuts() {
    if (state.shortcutsOpen) closeShortcuts();
    else openShortcuts();
  }

  /* ——— Connection stale banner ——— */

  function ensureConnBanner() {
    return $("#coast-conn-banner");
  }

  function setConnectionStale(stale) {
    if (!state.consoleActive) {
      stale = false;
    }
    state.connectionStale = !!stale;
    var el = ensureConnBanner();
    if (el) el.classList.toggle("is-visible", state.connectionStale);
    document.body.classList.toggle("is-connection-stale", state.connectionStale);
    $$("#app [data-live]").forEach(function (node) {
      node.classList.toggle("is-stale", state.connectionStale);
    });
    document.dispatchEvent(
      new CustomEvent("coast:connection", {
        detail: { stale: state.connectionStale },
      })
    );
  }

  function setConsoleActive(on) {
    state.consoleActive = !!on;
    document.body.classList.toggle("is-console", state.consoleActive);
    document.body.classList.toggle("is-door", !state.consoleActive);
    if (!state.consoleActive) {
      setConnectionStale(false);
    } else {
      markConnectionOk();
    }
  }

  function markConnectionOk() {
    state.lastOkAt = Date.now();
    if (state.connectionStale) setConnectionStale(false);
  }

  function checkConnectionStale() {
    if (!state.consoleActive) return;
    if (Date.now() - state.lastOkAt >= STALE_MS) {
      if (!state.connectionStale) setConnectionStale(true);
    }
  }

  /* ——— Keyboard ——— */

  function onKeydown(e) {
    var metaK = (e.ctrlKey || e.metaKey) && (e.key === "k" || e.key === "K");
    if (metaK) {
      e.preventDefault();
      togglePalette();
      return;
    }

    if (e.key === "Escape") {
      if (state.paletteOpen) {
        e.preventDefault();
        closePalette();
        return;
      }
      if (state.shortcutsOpen) {
        e.preventDefault();
        closeShortcuts();
        return;
      }
    }

    if (isTypingTarget(e.target) || state.paletteOpen) return;

    if (e.key === "?" && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      toggleShortcuts();
      return;
    }

    if ((e.key === "p" || e.key === "P") && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      togglePresentation();
      return;
    }

    if (/^[1-5]$/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) {
      var idx = parseInt(e.key, 10) - 1;
      if (VIEWS[idx]) {
        e.preventDefault();
        setView(VIEWS[idx].id);
      }
    }
  }

  function bindRail() {
    $$(".icon-rail__item[data-nav]").forEach(function (el) {
      el.addEventListener("click", function (e) {
        e.preventDefault();
        setView(el.getAttribute("data-nav"));
      });
    });
  }

  function init() {
    bindRail();
    document.addEventListener("keydown", onKeydown);
    setInterval(checkConnectionStale, 500);
    document.dispatchEvent(new CustomEvent("coast:ready"));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.COAST = {
    views: VIEWS,
    getState: function () {
      return {
        view: state.view,
        presentation: state.presentation,
        paletteOpen: state.paletteOpen,
        shortcutsOpen: state.shortcutsOpen,
        connectionStale: state.connectionStale,
        lastOkAt: state.lastOkAt,
        consoleActive: state.consoleActive,
      };
    },
    setConsoleActive: setConsoleActive,
    setView: setView,
    openPalette: openPalette,
    closePalette: closePalette,
    togglePalette: togglePalette,
    openShortcuts: openShortcuts,
    closeShortcuts: closeShortcuts,
    toggleShortcuts: toggleShortcuts,
    setPresentation: setPresentation,
    togglePresentation: togglePresentation,
    setConnectionStale: setConnectionStale,
    markConnectionOk: markConnectionOk,
  };
})();
