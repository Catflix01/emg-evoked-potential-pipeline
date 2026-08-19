/* Starting the tool: Python, running inside this browser.
 *
 * stlite downloads a Python interpreter compiled to WebAssembly, then runs the same
 * pi_app.py the desktop version runs. Recordings a visitor picks are read by that
 * in-browser Python. There is no server here, so there is nowhere for them to be sent.
 */

import { mount } from "https://cdn.jsdelivr.net/npm/@stlite/browser@1.8.1/build/stlite.js";
import { currentTheme } from "./theme.js";

// Fetched from this same folder, so the browser runs the identical Python the
// command line does. Adding a module here without adding it to build_site.py's
// APP_PYTHON publishes a page that fails on its first import.
const sourceFiles = [
  "pi_app.py",
  "src/harmonize.py",
  "src/cusum.py",
  "src/figures.py",
  "src/lineups.py",
  "src/lineups.json",
  "config/params.yaml",
];

const files = Object.fromEntries(sourceFiles.map((path) => [path, { url: path }]));

mount(
  {
    // Only packages Pyodide itself ships. If one of these cannot be resolved the whole
    // install fails and nothing is available, not even pandas, so anything pure-Python
    // that Pyodide lacks (openpyxl) is installed by the app instead, where a failure can
    // be caught and explained.
    requirements: ["pandas", "numpy", "matplotlib", "pyyaml"],
    entrypoint: "pi_app.py",
    files,
    // Streamlit's own theming, rather than CSS aimed at class names it does not promise
    // to keep. Without this the app opens light inside a dark page.
    streamlitConfig: { "theme.base": currentTheme() },
  },
  document.getElementById("root"),
);

// the loading screen goes once Streamlit has painted something
const root = document.getElementById("root");
new MutationObserver((_, observer) => {
  if (root.childElementCount > 0) {
    document.getElementById("loading")?.remove();
    observer.disconnect();
  }
}).observe(root, { childList: true, subtree: true });
