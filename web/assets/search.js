/* Searching the guides, entirely in the browser.
 *
 * build_site.py writes search-index.json: one entry per heading, with the text under it.
 * Nothing is sent anywhere, which matters here — a search box that quietly reports what
 * people looked for would contradict the promise the rest of this makes.
 */

const box = document.querySelector("[data-search]");
const results = document.querySelector("[data-search-results]");

if (box && results) {
  let entries = [];

  const load = fetch(box.dataset.search)
    .then((r) => r.json())
    .then((loaded) => { entries = loaded; })
    .catch(() => { entries = []; });

  const show = (matches, typed) => {
    results.innerHTML = "";
    if (!typed) return;

    if (!matches.length) {
      const nothing = document.createElement("li");
      nothing.className = "search-empty";
      nothing.textContent = `Nothing in the guides matches "${typed}".`;
      results.appendChild(nothing);
      return;
    }

    for (const entry of matches.slice(0, 8)) {
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = entry.url;
      link.textContent = entry.heading;
      const where = document.createElement("span");
      where.className = "where";
      where.textContent = ` — ${entry.page}`;
      item.append(link, where);
      results.appendChild(item);
    }
  };

  const search = async () => {
    await load;
    const typed = box.value.trim().toLowerCase();
    if (!typed) return show([], "");

    const words = typed.split(/\s+/);
    const scored = entries
      .map((entry) => {
        const haystack = `${entry.heading} ${entry.text}`.toLowerCase();
        // every word must appear; a heading match is worth more than a body match
        if (!words.every((w) => haystack.includes(w))) return null;
        const inHeading = words.filter((w) => entry.heading.toLowerCase().includes(w)).length;
        return { entry, score: inHeading };
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score)
      .map((m) => m.entry);

    show(scored, typed);
  };

  box.addEventListener("input", search);
}
