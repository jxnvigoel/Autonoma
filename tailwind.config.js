/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Theme colours are CSS variables (light/dark). Tailwind cannot add transparency to a variable on
        // its own, so classes like bg-brand-accent/10 produced no CSS; color-mix makes them work.
        brand: Object.fromEntries(
          ["bg", "card", "card-alt", "accent", "accent-hover", "accent-text", "headline", "body", "border",
           "subtle", "subtle-hover", "muted", "surface"].map((name) => [
            name,
            ({ opacityValue }) =>
              opacityValue === undefined || opacityValue === "1"
                ? `var(--color-${name})`
                : `color-mix(in srgb, var(--color-${name}) calc(${opacityValue} * 100%), transparent)`,
          ])
        ),
      },
      boxShadow: {
        card: "var(--color-card-shadow)",
      },
    },
  },
  plugins: [],
};
