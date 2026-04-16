import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        lookover: {
          bg: "var(--lookover-bg)",
          panel: "var(--lookover-panel)",
          "panel-subtle": "var(--lookover-panel-subtle)",
          sidebar: "var(--lookover-sidebar)",
          border: "var(--lookover-border)",
          "border-strong": "var(--lookover-border-strong)",
          text: "var(--lookover-text)",
          "text-muted": "var(--lookover-text-muted)",
          "text-soft": "var(--lookover-text-soft)",
          success: "var(--lookover-success)",
          "success-soft": "var(--lookover-success-soft)",
          warning: "var(--lookover-warning)",
          "warning-soft": "var(--lookover-warning-soft)",
          danger: "var(--lookover-danger)",
          "danger-soft": "var(--lookover-danger-soft)",
          indigo: "var(--lookover-indigo)",
          sky: "var(--lookover-sky)",
          green: "var(--lookover-green)",
          orange: "var(--lookover-orange)",
          steel: "var(--lookover-steel)",
        },
      },
      boxShadow: {
        "lookover-card": "0 2px 6px rgba(15, 23, 42, 0.03), 0 14px 34px rgba(15, 23, 42, 0.05)",
        "lookover-rail": "0 10px 30px rgba(15, 23, 42, 0.04)",
      },
      fontFamily: {
        sans: ["var(--font-geist-sans)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-geist-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
