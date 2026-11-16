// Guided box breathing: in 4s, hold 4s, out 4s, hold 4s.
(function () {
  var btn = document.getElementById("breathBtn");
  var circle = document.getElementById("breathCircle");
  var text = document.getElementById("breathText");
  var count = document.getElementById("breathCount");
  if (!btn) return;

  var phases = [
    { label: "Breathe in", cls: "in" },
    { label: "Hold", cls: "hold-in" },
    { label: "Breathe out", cls: "out" },
    { label: "Hold", cls: "hold-out" },
  ];
  var timer = null, step = 0, rounds = 0;

  function tick() {
    var p = phases[step];
    text.textContent = p.label;
    circle.className = "breath-circle " + p.cls;
    step = (step + 1) % phases.length;
    if (step === 0) { rounds += 1; count.textContent = "Rounds completed: " + rounds; }
  }

  function stop() {
    clearInterval(timer);
    timer = null;
    circle.className = "breath-circle";
    text.textContent = "Well done. Notice how you feel.";
    btn.textContent = "Start again";
  }

  btn.addEventListener("click", function () {
    if (timer) { stop(); return; }
    step = 0; rounds = 0;
    count.textContent = "Rounds completed: 0";
    btn.textContent = "Stop";
    tick();
    timer = setInterval(tick, 4000);
  });
})();
