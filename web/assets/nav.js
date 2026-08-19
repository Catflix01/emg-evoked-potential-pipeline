/* The moving parts of a page: the menu, the progress bar, back to top, copy buttons.
 *
 * Each is set up only if the page actually contains it, so one script suits every page and
 * a page can leave out anything it does not need.
 */

function mobileMenu() {
  const button = document.querySelector("[data-menu-button]");
  const nav = document.querySelector("[data-nav]");
  if (!button || !nav) return;

  const setOpen = (open) => {
    nav.dataset.open = String(open);
    button.setAttribute("aria-expanded", String(open));
    button.textContent = open ? "✕" : "☰";
  };
  setOpen(false);

  button.addEventListener("click", () => setOpen(nav.dataset.open !== "true"));
  // a menu that stays open after you have chosen is just in the way
  nav.addEventListener("click", (e) => { if (e.target.tagName === "A") setOpen(false); });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") setOpen(false); });
}

function scrollProgress() {
  const bar = document.querySelector("[data-progress]");
  if (!bar) return;

  const update = () => {
    const scrollable = document.documentElement.scrollHeight - window.innerHeight;
    const fraction = scrollable > 0 ? window.scrollY / scrollable : 0;
    bar.style.width = `${Math.min(100, Math.max(0, fraction * 100))}%`;
  };
  update();
  addEventListener("scroll", update, { passive: true });
  addEventListener("resize", update);
}

function backToTop() {
  const button = document.querySelector("[data-to-top]");
  if (!button) return;

  const update = () => { button.dataset.visible = String(window.scrollY > 600); };
  update();
  addEventListener("scroll", update, { passive: true });
  button.addEventListener("click", () => scrollTo({ top: 0, behavior: "smooth" }));
}

function copyButtons() {
  for (const block of document.querySelectorAll(".prose pre")) {
    const button = document.createElement("button");
    button.className = "copy-button";
    button.type = "button";
    button.textContent = "Copy";

    button.addEventListener("click", async () => {
      const code = block.querySelector("code") || block;
      try {
        await navigator.clipboard.writeText(code.innerText.trimEnd());
        button.textContent = "Copied";
      } catch {
        button.textContent = "Press ⌘C";     // clipboard refused, usually over plain http
      }
      setTimeout(() => { button.textContent = "Copy"; }, 2000);
    });

    block.appendChild(button);
  }
}

function markCurrentPage() {
  const here = location.pathname.replace(/index\.html$/, "");
  for (const link of document.querySelectorAll("[data-nav] a")) {
    const target = new URL(link.href).pathname.replace(/index\.html$/, "");
    if (target === here) link.setAttribute("aria-current", "page");
  }
}

mobileMenu();
scrollProgress();
backToTop();
copyButtons();
markCurrentPage();
