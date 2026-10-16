(function () {
  var root = document.documentElement;
  var saved = "dark";
  try { saved = localStorage.getItem("theme") || "dark"; } catch (e) {}
  var q = new URLSearchParams(location.search).get("theme");
  if (q === "dark" || q === "light") saved = q;
  root.setAttribute("data-theme", saved);
  document.getElementById("mode").addEventListener("click", function () {
    var next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
  });
})();
(function () {
  var header = document.querySelector("header");
  var button = document.getElementById("menu");
  button.addEventListener("click", function () {
    var open = header.classList.toggle("open");
    button.setAttribute("aria-expanded", open ? "true" : "false");
  });
  document.querySelectorAll("#nav a").forEach(function (a) { a.addEventListener("click", function () { header.classList.remove("open"); }); });
  document.addEventListener("click", function (e) { if (!header.contains(e.target)) header.classList.remove("open"); });
})();
(function () {
  var button = document.getElementById("copy");
  var text = document.getElementById("cmd").textContent;
  var reset;
  function done() {
    button.classList.add("done"); button.title = "Copied";
    clearTimeout(reset);
    reset = setTimeout(function () { button.classList.remove("done"); button.title = "Copy"; }, 1600);
  }
  function fallback() {
    var range = document.createRange(); range.selectNodeContents(document.getElementById("cmd"));
    var sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
    try { document.execCommand("copy"); done(); } catch (e) {}
  }
  button.addEventListener("click", function () {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(done, fallback);
    } else { fallback(); }
  });
  document.getElementById("cmd").addEventListener("click", function () { button.click(); });
})();
(function () {
  var box = document.getElementById("carousel");
  var track = box.querySelector(".track");
  var slides = track.querySelectorAll("img");
  var title = box.querySelector(".title");
  var dots = document.getElementById("dots");
  var i = 0, timer;
  slides.forEach(function (_, n) {
    var b = document.createElement("button"); b.type = "button"; b.setAttribute("aria-label", "Picture " + (n + 1));
    b.addEventListener("click", function () { show(n); restart(); });
    dots.appendChild(b);
  });
  function show(n) {
    i = (n + slides.length) % slides.length;
    track.style.transform = "translateX(-" + (i * 100) + "%)";
    dots.querySelectorAll("button").forEach(function (b, k) { b.classList.toggle("on", k === i); });
    title.textContent = slides[i].getAttribute("data-title");
  }
  function restart() { clearInterval(timer); timer = setInterval(function () { show(i + 1); }, 4000); }
  box.querySelector(".prev").addEventListener("click", function () { show(i - 1); restart(); });
  box.querySelector(".next").addEventListener("click", function () { show(i + 1); restart(); });
  box.addEventListener("mouseenter", function () { clearInterval(timer); });
  box.addEventListener("mouseleave", restart);
  document.addEventListener("keydown", function (e) {
    if (e.key === "ArrowLeft") { show(i - 1); restart(); }
    if (e.key === "ArrowRight") { show(i + 1); restart(); }
  });
  show(0); restart();
})();
