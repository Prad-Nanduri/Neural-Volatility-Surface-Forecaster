import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components.tsx"],
  theme: { extend: {} },
  plugins: [],
} satisfies Config;
