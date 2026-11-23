// Light or dark. The choice is remembered; the new page grows out of the button where the browser can do that.
(function () {
  var root = document.documentElement;
  var button = document.getElementById("theme");
  function apply(next) {
    root.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
  }
  button.addEventListener("click", function () {
    var next = root.getAttribute("data-theme") === "light" ? "dark" : "light";
    if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) { apply(next); return; }
    var box = button.getBoundingClientRect();
    root.style.setProperty("--grow-x", (box.left + box.width / 2) + "px");
    root.style.setProperty("--grow-y", (box.top + box.height / 2) + "px");
    root.classList.add("theme-switching");
    var done = function () { root.classList.remove("theme-switching"); };
    document.startViewTransition(function () { apply(next); }).finished.then(done, done);
  });
})();

// Copy the install command when it, or the yellow button next to it, is clicked.
(function () {
  var box = document.getElementById("install");
  var button = document.getElementById("copy");
  if (!box || !button) return;                       // the manual has an "install" section too, but no copy button
  var cmd = document.getElementById("cmd");
  var said = document.getElementById("copied");
  var reset;
  function done() {
    box.classList.add("done"); said.textContent = "Copied";
    clearTimeout(reset);
    reset = setTimeout(function () { box.classList.remove("done"); said.textContent = ""; }, 1600);
  }
  function fallback() {
    var range = document.createRange(); range.selectNodeContents(cmd);
    var sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
    try { document.execCommand("copy"); done(); } catch (e) {}
    sel.removeAllRanges();
  }
  button.addEventListener("click", function () {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(cmd.textContent).then(done, fallback);
    } else { fallback(); }
  });
  cmd.addEventListener("click", function () { button.click(); });
})();


// A copy button on each block of commands in the manual. It copies the lines after "$ ", without the prompts or the output.
(function () {
  var blocks = document.querySelectorAll(".term");
  var icons = '<svg class="i-copy" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15h-.5A1.5 1.5 0 0 1 3 13.5v-9A1.5 1.5 0 0 1 4.5 3h9A1.5 1.5 0 0 1 15 4.5V5"/></svg>' +
              '<svg class="i-done" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5"/></svg>';
  Array.prototype.forEach.call(blocks, function (block) {
    var text = block.textContent.split("\n").filter(function (l) { return l.indexOf("$ ") === 0; })
                    .map(function (l) { return l.slice(2); }).join("\n");
    if (!text) return;
    var button = document.createElement("button");
    button.type = "button"; button.className = "term-copy"; button.title = "Copy";
    button.setAttribute("aria-label", "Copy the commands"); button.innerHTML = icons;
    var reset;
    function done() {
      button.classList.add("done"); button.setAttribute("aria-label", "Copied");
      clearTimeout(reset);
      reset = setTimeout(function () { button.classList.remove("done"); button.setAttribute("aria-label", "Copy the commands"); }, 1600);
    }
    button.addEventListener("click", function () {
      if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, function () {});
    });
    block.appendChild(button);
  });
})();

// Stars and forks next to the GitHub link. Asked of GitHub at most once an hour per visitor; nothing shows if it can't be reached.
(function () {
  var spots = document.querySelectorAll("[data-gh]");
  if (!spots.length) return;
  function short(n) { return n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, "") + "k" : String(n); }
  function show(repo) {
    Array.prototype.forEach.call(spots, function (spot) {
      var n = repo[spot.getAttribute("data-gh")];
      if (typeof n !== "number") return;
      spot.lastElementChild.textContent = short(n);
      spot.setAttribute("aria-label", n + (spot.getAttribute("data-gh") === "forks_count" ? " forks" : " stars") + " on GitHub");
      spot.hidden = false;
    });
  }
  var saved = null;
  try { saved = JSON.parse(localStorage.getItem("gh-repo") || "null"); } catch (e) {}
  if (saved && Date.now() - saved.at < 3600e3) { show(saved); return; }
  if (!window.fetch) return;
  fetch("https://api.github.com/repos/ACoci86/terrahour").then(function (r) { return r.ok ? r.json() : null; }).then(function (repo) {
    if (!repo) { if (saved) show(saved); return; }
    var keep = { stargazers_count: repo.stargazers_count, forks_count: repo.forks_count, at: Date.now() };
    try { localStorage.setItem("gh-repo", JSON.stringify(keep)); } catch (e) {}
    show(keep);
  }, function () { if (saved) show(saved); });
})();

// The demo plays on its own, unless the visitor has asked for less motion: then it waits, with controls to start it.
(function () {
  var video = document.getElementById("demo");
  if (!video || !window.matchMedia || !matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  video.removeAttribute("autoplay"); video.pause(); video.controls = true;
})();
