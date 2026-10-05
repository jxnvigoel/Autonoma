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
        brand: {
          bg: "var(--color-bg)",
          card: "var(--color-card)",
          "card-alt": "var(--color-card-alt)",
          accent: "var(--color-accent)",
          "accent-hover": "var(--color-accent-hover)",
          "accent-text": "var(--color-accent-text)",
          headline: "var(--color-headline)",
          body: "var(--color-body)",
          border: "var(--color-border)",
          subtle: "var(--color-subtle)",
          "subtle-hover": "var(--color-subtle-hover)",
        },
      },
      boxShadow: {
        card: "var(--color-card-shadow)",
      },
    },
  },
  plugins: [],
};
