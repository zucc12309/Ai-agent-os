import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#06111f",
          900: "#0b1728",
          800: "#10213a",
          700: "#20304b",
        },
        mint: {
          400: "#6ee7b7",
          500: "#34d399",
          600: "#10b981",
        },
        amber: {
          400: "#fbbf24",
          500: "#f59e0b",
        },
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(255,255,255,0.05), 0 24px 80px rgba(2,6,23,0.45)",
      },
      fontFamily: {
        sans: ["var(--font-body)", "sans-serif"],
        heading: ["var(--font-heading)", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;

