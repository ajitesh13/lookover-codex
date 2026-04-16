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
        "lookover-card": "0 1px 2px rgba(16, 24, 40, 0.04), 0 10px 24px rgba(16, 24, 40, 0.05)",
        "lookover-rail": "0 1px 2px rgba(16, 24, 40, 0.05), 0 18px 38px rgba(16, 24, 40, 0.05)",
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
