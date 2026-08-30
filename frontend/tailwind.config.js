/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        slatebase: "#0b1724",
        steel: "#12314f",
        cyanaccent: "#4cc9f0",
        amberaccent: "#f6ad55",
        mintaccent: "#7dd3a7",
      },
      boxShadow: {
        panel: "0 20px 45px rgba(11, 23, 36, 0.16)",
      },
      backgroundImage: {
        grid: "linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)",
      },
    },
  },
  plugins: [],
};
