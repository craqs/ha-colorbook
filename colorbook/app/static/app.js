(() => {
  "use strict";

  // Work under HA ingress: all URLs are relative to the page base.
  const api = (path) => path.startsWith("/") ? `.${path}` : path;

  const $ = (id) => document.getElementById(id);

  const el = {
    topic: $("topic"),
    btnRandom: $("btn-random"),
    btnGenerate: $("btn-generate"),
    autoAccept: $("auto-accept"),
    preview: $("preview"),
    previewImage: $("preview-image"),
    previewOverlay: $("preview-overlay"),
    overlayText: $("overlay-text"),
    promptBox: $("prompt-box"),
    btnPromptToggle: $("btn-prompt-toggle"),
    btnPrint: $("btn-print"),
    btnRegen: $("btn-regen"),
    btnRefine: $("btn-refine"),
    refineRow: $("refine-row"),
    refineInput: $("refine-input"),
    btnRefineApply: $("btn-refine-apply"),
    btnRefineCancel: $("btn-refine-cancel"),
    gallery: $("gallery"),
    galleryEmpty: $("gallery-empty"),
    btnRefreshGallery: $("btn-refresh-gallery"),
    sheetBackdrop: $("sheet-backdrop"),
    sheetClose: $("sheet-close"),
    sheetImage: $("sheet-image"),
    sheetTitle: $("sheet-title"),
    sheetTopic: $("sheet-topic"),
    sheetDate: $("sheet-date"),
    sheetPrinted: $("sheet-printed"),
    sheetPromptText: $("sheet-prompt-text"),
    sheetPrint: $("sheet-print"),
    sheetDelete: $("sheet-delete"),
    toast: $("toast"),
  };

  const state = {
    current: null,     // currently displayed item (from /api/generate)
    activeSheetItem: null,
  };

  // --- Auto-accept persistence ---------------------------------------------
  const AUTO_ACCEPT_KEY = "colorbook.autoAccept";
  const defaultAutoAccept = document.body.dataset.autoAcceptDefault === "true";
  const stored = localStorage.getItem(AUTO_ACCEPT_KEY);
  el.autoAccept.checked = stored === null ? defaultAutoAccept : stored === "1";
  el.autoAccept.addEventListener("change", () => {
    localStorage.setItem(AUTO_ACCEPT_KEY, el.autoAccept.checked ? "1" : "0");
  });

  // --- Toast ---------------------------------------------------------------
  let toastTimer = null;
  function toast(message, kind) {
    el.toast.textContent = message;
    el.toast.classList.toggle("error", kind === "error");
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.toast.hidden = true; }, 3800);
  }

  // --- Overlay -------------------------------------------------------------
  function setOverlay(text) {
    if (text) {
      el.overlayText.textContent = text;
      el.previewOverlay.hidden = false;
    } else {
      el.previewOverlay.hidden = true;
    }
  }

  function setBusy(busy) {
    [el.btnGenerate, el.btnRandom, el.btnPrint, el.btnRegen, el.btnRefine,
     el.btnRefineApply, el.btnRefreshGallery, el.sheetPrint, el.sheetDelete
    ].forEach((b) => { if (b) b.disabled = busy; });
  }

  // --- API helper ----------------------------------------------------------
  async function apiCall(path, options = {}) {
    const opts = Object.assign({ headers: {} }, options);
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(api(path), opts);
    let data = null;
    try { data = await res.json(); } catch (_) { /* empty/non-json */ }
    if (!res.ok) {
      const msg = (data && data.error) || `Błąd HTTP ${res.status}`;
      throw new Error(msg);
    }
    return data;
  }

  // --- Generation ----------------------------------------------------------
  async function generate({ topic, refinement, parentId } = {}) {
    const t = (topic ?? el.topic.value).trim();
    if (!t) {
      toast("Podaj temat kolorowanki.", "error");
      el.topic.focus();
      return;
    }
    const autoAccept = el.autoAccept.checked;

    // Reveal preview area with spinner immediately
    el.preview.hidden = false;
    el.previewImage.removeAttribute("src");
    el.promptBox.hidden = true;
    el.btnPromptToggle.setAttribute("aria-expanded", "false");
    el.btnPromptToggle.textContent = "Pokaż prompt";
    setOverlay(autoAccept ? "Generuję i drukuję…" : "Generuję…");
    setBusy(true);

    try {
      const item = await apiCall("/api/generate", {
        method: "POST",
        body: {
          topic: t,
          refinement: refinement || null,
          parent_id: parentId || null,
        },
      });
      state.current = item;
      el.previewImage.src = api(item.image_url);
      el.promptBox.textContent = item.full_prompt;
      el.topic.value = item.topic;
      hideRefineRow();

      if (autoAccept) {
        try {
          await apiCall("/api/print", { method: "POST", body: { id: item.id } });
          toast("Wygenerowano i wysłano do drukarki.");
        } catch (err) {
          toast(`Wygenerowano, ale drukowanie nie powiodło się: ${err.message}`, "error");
        }
      } else {
        toast("Gotowe! Możesz wydrukować lub dopracować.");
      }
      await refreshGallery();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setOverlay(null);
      setBusy(false);
    }
  }

  // --- Print ---------------------------------------------------------------
  async function printItem(itemId, { silent = false } = {}) {
    if (!itemId) return;
    setBusy(true);
    if (!silent) toast("Wysyłam do drukarki…");
    try {
      await apiCall("/api/print", { method: "POST", body: { id: itemId } });
      toast("Wysłano do drukarki.");
      await refreshGallery();
    } catch (err) {
      toast(`Nie udało się wydrukować: ${err.message}`, "error");
    } finally {
      setBusy(false);
    }
  }

  // --- Random topic --------------------------------------------------------
  async function fetchRandomTopic() {
    setBusy(true);
    try {
      const { topic } = await apiCall("/api/random-topic");
      el.topic.value = topic;
      el.topic.focus();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  // --- Refine row ----------------------------------------------------------
  function showRefineRow() {
    el.refineRow.hidden = false;
    el.refineInput.value = "";
    el.refineInput.focus();
  }
  function hideRefineRow() {
    el.refineRow.hidden = true;
  }

  // --- Gallery -------------------------------------------------------------
  function formatDate(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString("pl-PL", { dateStyle: "short", timeStyle: "short" });
    } catch (_) {
      return iso;
    }
  }

  async function refreshGallery() {
    try {
      const data = await apiCall("/api/history?limit=60");
      const items = data.items || [];
      el.gallery.innerHTML = "";
      if (items.length === 0) {
        el.galleryEmpty.hidden = false;
        return;
      }
      el.galleryEmpty.hidden = true;
      const frag = document.createDocumentFragment();
      items.forEach((it) => {
        const div = document.createElement("button");
        div.type = "button";
        div.className = "gallery-item";
        div.title = it.topic;
        div.setAttribute("aria-label", it.topic);
        div.innerHTML = `
          <img loading="lazy" src="${escapeHtml(api(it.image_url))}" alt="${escapeHtml(it.topic)}">
          ${it.printed_at ? '<span class="badge">Wydrukowano</span>' : ""}
        `;
        div.addEventListener("click", () => openSheet(it));
        frag.appendChild(div);
      });
      el.gallery.appendChild(frag);
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  // --- Sheet (detail modal) -----------------------------------------------
  function openSheet(item) {
    state.activeSheetItem = item;
    el.sheetTitle.textContent = item.topic || "Kolorowanka";
    el.sheetImage.src = api(item.image_url);
    el.sheetImage.alt = item.topic || "";
    el.sheetTopic.textContent = item.topic;
    el.sheetDate.textContent = formatDate(item.created_at);
    el.sheetPrinted.textContent = item.printed_at ? formatDate(item.printed_at) : "—";
    el.sheetPromptText.textContent = item.full_prompt;
    el.sheetBackdrop.hidden = false;
    document.body.style.overflow = "hidden";
  }
  function closeSheet() {
    state.activeSheetItem = null;
    el.sheetBackdrop.hidden = true;
    document.body.style.overflow = "";
  }

  async function deleteActive() {
    const item = state.activeSheetItem;
    if (!item) return;
    if (!confirm(`Usunąć "${item.topic}" z galerii?`)) return;
    setBusy(true);
    try {
      await apiCall(`/api/history/${encodeURIComponent(item.id)}`, { method: "DELETE" });
      closeSheet();
      toast("Usunięto.");
      await refreshGallery();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  // --- Event wiring --------------------------------------------------------
  el.btnGenerate.addEventListener("click", () => generate());
  el.topic.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); generate(); }
  });
  el.btnRandom.addEventListener("click", fetchRandomTopic);

  el.btnPromptToggle.addEventListener("click", () => {
    const shown = !el.promptBox.hidden;
    el.promptBox.hidden = shown;
    el.btnPromptToggle.setAttribute("aria-expanded", String(!shown));
    el.btnPromptToggle.textContent = shown ? "Pokaż prompt" : "Ukryj prompt";
  });

  el.btnPrint.addEventListener("click", () => {
    if (state.current) printItem(state.current.id);
  });
  el.btnRegen.addEventListener("click", () => {
    if (!state.current) return;
    generate({
      topic: state.current.topic,
      refinement: state.current.refinement || null,
      parentId: state.current.id,
    });
  });
  el.btnRefine.addEventListener("click", () => {
    if (el.refineRow.hidden) showRefineRow(); else hideRefineRow();
  });
  el.btnRefineApply.addEventListener("click", () => {
    if (!state.current) return;
    const refinement = el.refineInput.value.trim();
    if (!refinement) { toast("Wpisz, co chcesz dopracować.", "error"); return; }
    const combined = state.current.refinement
      ? `${state.current.refinement}; ${refinement}`
      : refinement;
    generate({
      topic: state.current.topic,
      refinement: combined,
      parentId: state.current.id,
    });
  });
  el.btnRefineCancel.addEventListener("click", hideRefineRow);
  el.refineInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); el.btnRefineApply.click(); }
    if (e.key === "Escape") { e.preventDefault(); hideRefineRow(); }
  });

  el.btnRefreshGallery.addEventListener("click", refreshGallery);

  el.sheetClose.addEventListener("click", closeSheet);
  el.sheetBackdrop.addEventListener("click", (e) => {
    if (e.target === el.sheetBackdrop) closeSheet();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !el.sheetBackdrop.hidden) closeSheet();
  });
  el.sheetPrint.addEventListener("click", () => {
    if (state.activeSheetItem) printItem(state.activeSheetItem.id);
  });
  el.sheetDelete.addEventListener("click", deleteActive);

  // Initial load
  refreshGallery();
})();
