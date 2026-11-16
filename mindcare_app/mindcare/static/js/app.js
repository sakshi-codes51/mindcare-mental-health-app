// Shared behaviour: local time display, confirm prompts, default dates.
(function () {
  document.querySelectorAll("time.js-local").forEach(function (el) {
    var d = new Date(el.getAttribute("datetime"));
    if (isNaN(d)) return;
    var dateOnly = el.textContent.trim().length <= 16;
    el.textContent = d.toLocaleString(undefined, dateOnly ? { dateStyle: "medium" } : { dateStyle: "medium", timeStyle: "short" });
  });

  document.querySelectorAll("form[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  // The server only knows the UTC date. Default new journal entries to the visitor's own local date.
  document.querySelectorAll("input[data-server-today]").forEach(function (input) {
    var now = new Date();
    var local = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
    input.max = local;
    if (input.value === input.dataset.serverToday) input.value = local;
  });
})();
