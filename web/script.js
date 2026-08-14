    import { mount } from "https://cdn.jsdelivr.net/npm/@stlite/browser@1.8.1/build/stlite.js";

    // Fetched from this same folder, so the browser app runs the identical Python
    // that the command-line version does.
    const sourceFiles = [
      "pi_app.py",
      "src/harmonize.py",
      "src/cusum.py",
      "src/figures.py",
      "src/lineups.py",
      "src/lineups.json",
      "config/params.yaml",
    ];

    const files = Object.fromEntries(
      sourceFiles.map((path) => [path, { url: path }])
    );

    mount(
      {
        // Only packages Pyodide itself ships. If one of these cannot be resolved the
        // whole install fails and nothing is available, not even pandas, so anything
        // pure-Python that Pyodide lacks (openpyxl) is installed by the app instead,
        // where a failure can be caught and explained.
        requirements: ["pandas", "numpy", "matplotlib", "pyyaml"],
        entrypoint: "pi_app.py",
        files,
      },
      document.getElementById("root")
    );

    // the placeholder disappears once Streamlit has painted
    const root = document.getElementById("root");
    new MutationObserver((_, observer) => {
      if (root.childElementCount > 0) {
        document.getElementById("loading").remove();
        observer.disconnect();
      }
    }).observe(root, { childList: true, subtree: true });