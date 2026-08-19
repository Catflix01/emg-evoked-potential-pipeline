/* The dark mode toggle.
 *
 * Three states, not two: light, dark, and "whatever this computer is set to", which is the
 * default and what most people want. Pressing the button moves to the opposite of what is
 * currently showing and remembers it.
 *
 * The theme is also handed to the app, so it does not open light inside a dark page.
 */

const REMEMBERED = "emg-theme";

export function currentTheme() {
  const chosen = localStorage.getItem(REMEMBERED);
  if (chosen === "light" || chosen === "dark") return chosen;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  for (const button of document.querySelectorAll("[data-theme-toggle]")) {
    button.setAttribute("aria-pressed", String(theme === "dark"));
    button.setAttribute("aria-label",
      theme === "dark" ? "Switch to the light theme" : "Switch to the dark theme");
    button.textContent = theme === "dark" ? "☀" : "☾";
  }
}

function startTheme() {
  applyTheme(currentTheme());

  for (const button of document.querySelectorAll("[data-theme-toggle]")) {
    button.addEventListener("click", () => {
      const next = currentTheme() === "dark" ? "light" : "dark";
      localStorage.setItem(REMEMBERED, next);
      applyTheme(next);
    });
  }

  // keep following the computer's setting, for anyone who never pressed the button
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (!localStorage.getItem(REMEMBERED)) applyTheme(currentTheme());
  });
}

startTheme();
