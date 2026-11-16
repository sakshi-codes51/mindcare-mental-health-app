// Dashboard charts (Chart.js). Falls back to simple messages if the library cannot load.
(function () {
  var node = document.getElementById("chart-data");
  if (!node) return;
  var data = JSON.parse(node.textContent);

  function show(id, hasData) {
    var empty = document.getElementById(id + "Empty");
    var canvas = document.getElementById(id + "Chart");
    if (!hasData) {
      if (empty) empty.classList.remove("d-none");
      if (canvas) canvas.closest(".chart-box").classList.add("d-none");
    }
    return hasData;
  }

  if (typeof Chart === "undefined") {
    ["mood", "emotion", "screening"].forEach(function (id) {
      var c = document.getElementById(id + "Chart");
      if (c) c.closest(".chart-box").insertAdjacentHTML("afterend",
        '<p class="small text-body-secondary">Charts could not load (check your internet connection).</p>');
    });
    return;
  }

  var colors = {
    joy: "#e0a800", calm: "#4aa3a2", sadness: "#4a6fa5", anxiety: "#8e6bbf",
    anger: "#c0392b", stress: "#e67e22", loneliness: "#7f8c9a", neutral: "#adb5bd",
  };
  var primary = "#3b6fb6";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  Chart.defaults.animation = reduce ? false : Chart.defaults.animation;
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

  if (show("mood", data.mood.length > 0)) {
    new Chart(document.getElementById("moodChart"), {
      type: "line",
      data: {
        labels: data.mood.map(function (p) { return p.date; }),
        datasets: [{
          label: "Average mood", data: data.mood.map(function (p) { return p.mood; }),
          borderColor: primary, backgroundColor: "rgba(59,111,182,0.15)", fill: true, tension: 0.3, pointRadius: 4,
        }],
      },
      options: {
        maintainAspectRatio: false,
        scales: { y: { min: 1, max: 5, ticks: { stepSize: 1 }, title: { display: true, text: "Mood (1 low, 5 great)" } } },
        plugins: { legend: { display: false } },
      },
    });
  }

  if (show("emotion", data.emotions.length > 0)) {
    new Chart(document.getElementById("emotionChart"), {
      type: "doughnut",
      data: {
        labels: data.emotions.map(function (e) { return e.label.charAt(0).toUpperCase() + e.label.slice(1); }),
        datasets: [{
          data: data.emotions.map(function (e) { return e.count; }),
          backgroundColor: data.emotions.map(function (e) { return colors[e.label] || "#adb5bd"; }),
        }],
      },
      options: { maintainAspectRatio: false, plugins: { legend: { position: "bottom" } } },
    });
  }

  if (show("screening", data.screenings.length > 1)) {
    new Chart(document.getElementById("screeningChart"), {
      type: "line",
      data: {
        labels: data.screenings.map(function (s) { return s.date; }),
        datasets: [
          { label: "Total (0-12)", data: data.screenings.map(function (s) { return s.total; }), borderColor: primary, tension: 0.2 },
          { label: "Anxiety (0-6)", data: data.screenings.map(function (s) { return s.anxiety; }), borderColor: "#8e6bbf", borderDash: [5, 4], tension: 0.2 },
          { label: "Low mood (0-6)", data: data.screenings.map(function (s) { return s.depression; }), borderColor: "#4a6fa5", borderDash: [2, 3], tension: 0.2 },
        ],
      },
      options: { maintainAspectRatio: false, scales: { y: { min: 0, max: 12 } }, plugins: { legend: { position: "bottom" } } },
    });
  }
})();
