(() => {
  "use strict";

  // ---------------------------------------------------------------------------
  // Translations
  // ---------------------------------------------------------------------------

  const TRANSLATIONS = {
    en: {
      appTitle:           "Colorbook",
      topicLabel:         "Coloring page topic",
      topicPlaceholder:   "e.g. a fox running in the woods",
      btnRandom:          "Random topic",
      autoAcceptLabel:    "Auto-print",
      btnGenerate:        "Generate",
      previewTitle:       "Preview",
      showPrompt:         "Show prompt",
      hidePrompt:         "Hide prompt",
      btnPrint:           "Print",
      btnRegenerate:      "Regenerate",
      btnRefine:          "Refine\u2026",
      refinePlaceholder:  "e.g. add balloons and sunshine",
      btnApply:           "Apply",
      btnCancel:          "Cancel",
      galleryTitle:       "Gallery",
      btnRefresh:         "Refresh",
      galleryEmpty:       "No pages yet \u2014 generate your first!",
      metaTopic:          "Topic",
      metaDate:           "Date",
      metaPrinted:        "Printed",
      promptLabel:        "Prompt",
      btnReprint:         "Reprint",
      btnDelete:          "Delete",
      generating:         "Generating\u2026",
      generatingPrinting: "Generating and printing\u2026",
      doneReady:          "Done! You can print or refine.",
      sentToPrinter:      "Sent to printer.",
      generatedAndPrinted:"Generated and sent to printer.",
      generatedPrintFail: "Generated, but printing failed: ",
      sending:            "Sending to printer\u2026",
      printFailed:        "Print failed: ",
      enterTopic:         "Please enter a topic.",
      enterRefinement:    "Please describe what to change.",
      deleted:            "Deleted.",
      printedBadge:       "Printed",
      confirmDelete:      "Delete \"{topic}\" from the gallery?",
      never:              "\u2014",
      sheetDefaultTitle:  "Coloring page",
    },
    pl: {
      appTitle:           "Kolorowanki",
      topicLabel:         "Temat kolorowanki",
      topicPlaceholder:   "np. lis biegn\u0105cy przez las",
      btnRandom:          "Losowy temat",
      autoAcceptLabel:    "Drukuj automatycznie",
      btnGenerate:        "Generuj",
      previewTitle:       "Podgl\u0105d",
      showPrompt:         "Poka\u017c prompt",
      hidePrompt:         "Ukryj prompt",
      btnPrint:           "Drukuj",
      btnRegenerate:      "Wygeneruj ponownie",
      btnRefine:          "Dopracuj\u2026",
      refinePlaceholder:  "np. dodaj balony i s\u0142o\u0144ce",
      btnApply:           "Zastosuj",
      btnCancel:          "Anuluj",
      galleryTitle:       "Galeria",
      btnRefresh:         "Od\u015bwie\u017c",
      galleryEmpty:       "Brak kolorowanek \u2014 wygeneruj pierwsz\u0105!",
      metaTopic:          "Temat",
      metaDate:           "Data",
      metaPrinted:        "Wydrukowano",
      promptLabel:        "Prompt",
      btnReprint:         "Wydrukuj ponownie",
      btnDelete:          "Usu\u0144",
      generating:         "Generuj\u0119\u2026",
      generatingPrinting: "Generuj\u0119 i drukuj\u0119\u2026",
      doneReady:          "Gotowe! Mo\u017cesz wydrukowa\u0107 lub dopracowa\u0107.",
      sentToPrinter:      "Wys\u0142ano do drukarki.",
      generatedAndPrinted:"Wygenerowano i wys\u0142ano do drukarki.",
      generatedPrintFail: "Wygenerowano, ale drukowanie nie powiod\u0142o si\u0119: ",
      sending:            "Wysy\u0142am do drukarki\u2026",
      printFailed:        "Nie uda\u0142o si\u0119 wydrukowa\u0107: ",
      enterTopic:         "Podaj temat kolorowanki.",
      enterRefinement:    "Wpisz, co chcesz dopracowa\u0107.",
      deleted:            "Usuni\u0119to.",
      printedBadge:       "Wydrukowano",
      confirmDelete:      "Usun\u0105\u0107 \u201e{topic}\u201d z galerii?",
      never:              "\u2014",
      sheetDefaultTitle:  "Kolorowanka",
    },
  };

  const LANG = (document.body.dataset.lang || "en").toLowerCase();
  const T = TRANSLATIONS[LANG] || TRANSLATIONS.en;

  function applyTranslations() {
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.dataset.i18n;
      if (T[key] !== undefined) el.textContent = T[key];
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      const key = el.dataset.i18nPlaceholder;
      if (T[key] !== undefined) el.placeholder = T[key];
    });
    document.title = T.appTitle;
  }

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const api = (path) => path.startsWith("/") ? "." + path : path;
  const $ = (id) => document.getElementById(id);

  const el = {
    topic:             $("topic"),
    btnRandom:         $("btn-random"),
    btnGenerate:       $("btn-generate"),
    autoAccept:        $("auto-accept"),
    preview:           $("preview"),
    previewImage:      $("preview-image"),
    previewOverlay:    $("preview-overlay"),
    overlayText:       $("overlay-text"),
    promptDetails:     $("prompt-details"),
    promptBox:         $("prompt-box"),
    btnPrint:          $("btn-print"),
    btnRegen:          $("btn-regen"),
    btnRefine:         $("btn-refine"),
    refineRow:         $("refine-row"),
    refineInput:       $("refine-input"),
    btnRefineApply:    $("btn-refine-apply"),
    btnRefineCancel:   $("btn-refine-cancel"),
    gallery:           $("gallery"),
    galleryEmpty:      $("gallery-empty"),
    btnRefreshGallery: $("btn-refresh-gallery"),
    sheetBackdrop:     $("sheet-backdrop"),
    sheetClose:        $("sheet-close"),
    sheetImage:        $("sheet-image"),
    sheetTitle:        $("sheet-title"),
    sheetTopic:        $("sheet-topic"),
    sheetDate:         $("sheet-date"),
    sheetPrinted:      $("sheet-printed"),
    sheetPromptText:   $("sheet-prompt-text"),
    sheetPrint:        $("sheet-print"),
    sheetDelete:       $("sheet-delete"),
    toast:             $("toast"),
  };

  const state = { current: null, activeSheetItem: null };

  // ---------------------------------------------------------------------------
  // Auto-accept persistence
  // ---------------------------------------------------------------------------
  const AUTO_ACCEPT_KEY = "colorbook.autoAccept";
  const defaultAutoAccept = document.body.dataset.autoAcceptDefault === "true";
  const stored = localStorage.getItem(AUTO_ACCEPT_KEY);
  el.autoAccept.checked = stored === null ? defaultAutoAccept : stored === "1";
  el.autoAccept.addEventListener("change", () => {
    localStorage.setItem(AUTO_ACCEPT_KEY, el.autoAccept.checked ? "1" : "0");
  });

  // ---------------------------------------------------------------------------
  // Toast
  // ---------------------------------------------------------------------------
  let toastTimer = null;
  function toast(message, kind) {
    el.toast.textContent = message;
    el.toast.classList.toggle("error", kind === "error");
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.toast.hidden = true; }, 3800);
  }

  // ---------------------------------------------------------------------------
  // Overlay / busy state
  // ---------------------------------------------------------------------------
  function setOverlay(text) {
    if (text) { el.overlayText.textContent = text; el.previewOverlay.hidden = false; }
    else       { el.previewOverlay.hidden = true; }
  }

  function setBusy(busy) {
    [el.btnGenerate, el.btnRandom, el.btnPrint, el.btnRegen, el.btnRefine,
     el.btnRefineApply, el.btnRefreshGallery, el.sheetPrint, el.sheetDelete
    ].forEach((b) => { if (b) b.disabled = busy; });
  }

  // ---------------------------------------------------------------------------
  // API helper
  // ---------------------------------------------------------------------------
  async function apiCall(path, options = {}) {
    const opts = Object.assign({ headers: {} }, options);
    if (opts.body && typeof opts.body === "object" && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.body);
    }
    const res = await fetch(api(path), opts);
    let data = null;
    try { data = await res.json(); } catch (_) {}
    if (!res.ok) throw new Error((data && data.error) || "HTTP " + res.status);
    return data;
  }

  // ---------------------------------------------------------------------------
  // Generation
  // ---------------------------------------------------------------------------
  async function generate({ topic, refinement, parentId } = {}) {
    const t = (topic ?? el.topic.value).trim();
    if (!t) { toast(T.enterTopic, "error"); el.topic.focus(); return; }
    const autoAccept = el.autoAccept.checked;

    el.preview.hidden = false;
    el.previewImage.removeAttribute("src");
    el.promptDetails.open = false;
    setOverlay(autoAccept ? T.generatingPrinting : T.generating);
    setBusy(true);

    try {
      const item = await apiCall("/api/generate", {
        method: "POST",
        body: { topic: t, refinement: refinement || null, parent_id: parentId || null },
      });
      state.current = item;
      el.previewImage.src = api(item.image_url);
      el.promptBox.textContent = item.full_prompt;
      el.topic.value = item.topic;
      hideRefineRow();

      if (autoAccept) {
        try {
          await apiCall("/api/print", { method: "POST", body: { id: item.id } });
          toast(T.generatedAndPrinted);
        } catch (err) {
          toast(T.generatedPrintFail + err.message, "error");
        }
      } else {
        toast(T.doneReady);
      }
      await refreshGallery();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setOverlay(null);
      setBusy(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Print
  // ---------------------------------------------------------------------------
  async function printItem(itemId) {
    if (!itemId) return;
    setBusy(true);
    toast(T.sending);
    try {
      await apiCall("/api/print", { method: "POST", body: { id: itemId } });
      toast(T.sentToPrinter);
      await refreshGallery();
    } catch (err) {
      toast(T.printFailed + err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Random topic
  // ---------------------------------------------------------------------------
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

  // ---------------------------------------------------------------------------
  // Refine row
  // ---------------------------------------------------------------------------
  function showRefineRow() { el.refineRow.hidden = false; el.refineInput.value = ""; el.refineInput.focus(); }
  function hideRefineRow() { el.refineRow.hidden = true; }

  // ---------------------------------------------------------------------------
  // Gallery
  // ---------------------------------------------------------------------------
  function formatDate(iso) {
    try {
      return new Date(iso).toLocaleString(
        LANG === "pl" ? "pl-PL" : "en-GB", { dateStyle: "short", timeStyle: "short" });
    } catch (_) { return iso; }
  }

  async function refreshGallery() {
    try {
      const data = await apiCall("/api/history?limit=60");
      const items = data.items || [];
      el.gallery.innerHTML = "";
      if (items.length === 0) { el.galleryEmpty.hidden = false; return; }
      el.galleryEmpty.hidden = true;
      const frag = document.createDocumentFragment();
      items.forEach((it) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "gallery-item";
        btn.title = it.topic;
        btn.setAttribute("aria-label", it.topic);
        btn.innerHTML =
          '<img loading="lazy" src="' + escapeHtml(api(it.image_url)) + '" alt="' + escapeHtml(it.topic) + '">' +
          (it.printed_at ? '<span class="badge">' + escapeHtml(T.printedBadge) + "</span>" : "");
        btn.addEventListener("click", () => openSheet(it));
        frag.appendChild(btn);
      });
      el.gallery.appendChild(frag);
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  // ---------------------------------------------------------------------------
  // Sheet (detail modal)
  // ---------------------------------------------------------------------------
  function openSheet(item) {
    state.activeSheetItem = item;
    el.sheetTitle.textContent = item.topic || T.sheetDefaultTitle;
    el.sheetImage.src = api(item.image_url);
    el.sheetImage.alt = item.topic || "";
    el.sheetTopic.textContent = item.topic;
    el.sheetDate.textContent = formatDate(item.created_at);
    el.sheetPrinted.textContent = item.printed_at ? formatDate(item.printed_at) : T.never;
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
    if (!confirm(T.confirmDelete.replace("{topic}", item.topic))) return;
    setBusy(true);
    try {
      await apiCall("/api/history/" + encodeURIComponent(item.id), { method: "DELETE" });
      closeSheet();
      toast(T.deleted);
      await refreshGallery();
    } catch (err) {
      toast(err.message, "error");
    } finally {
      setBusy(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Event wiring
  // ---------------------------------------------------------------------------
  el.btnGenerate.addEventListener("click", () => generate());
  el.topic.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); generate(); } });
  el.btnRandom.addEventListener("click", fetchRandomTopic);
  el.btnPrint.addEventListener("click", () => { if (state.current) printItem(state.current.id); });
  el.btnRegen.addEventListener("click", () => {
    if (!state.current) return;
    generate({ topic: state.current.topic, refinement: state.current.refinement || null, parentId: state.current.id });
  });
  el.btnRefine.addEventListener("click", () => { if (el.refineRow.hidden) showRefineRow(); else hideRefineRow(); });
  el.btnRefineApply.addEventListener("click", () => {
    if (!state.current) return;
    const refinement = el.refineInput.value.trim();
    if (!refinement) { toast(T.enterRefinement, "error"); return; }
    const combined = state.current.refinement ? state.current.refinement + "; " + refinement : refinement;
    generate({ topic: state.current.topic, refinement: combined, parentId: state.current.id });
  });
  el.btnRefineCancel.addEventListener("click", hideRefineRow);
  el.refineInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter")  { e.preventDefault(); el.btnRefineApply.click(); }
    if (e.key === "Escape") { e.preventDefault(); hideRefineRow(); }
  });
  el.btnRefreshGallery.addEventListener("click", refreshGallery);
  el.sheetClose.addEventListener("click", closeSheet);
  el.sheetBackdrop.addEventListener("click", (e) => { if (e.target === el.sheetBackdrop) closeSheet(); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !el.sheetBackdrop.hidden) closeSheet(); });
  el.sheetPrint.addEventListener("click", () => { if (state.activeSheetItem) printItem(state.activeSheetItem.id); });
  el.sheetDelete.addEventListener("click", deleteActive);

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------
  applyTranslations();
  refreshGallery();
})();
