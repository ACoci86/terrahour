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
