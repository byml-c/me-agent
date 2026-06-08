import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1f2a24",
        moss: "#3e6b4f",
        clay: "#a75f3d",
        mist: "#eef3ef"
      }
    }
  },
  plugins: []
};

export default config;
