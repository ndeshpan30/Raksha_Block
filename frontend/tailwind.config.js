/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        railway: {
          dark: '#0f172a',
          navy: '#1e293b',
          card: '#1e293b',
          border: '#334155',
          accent: '#38bdf8',
          eng: '#3b82f6', // Engineering blue
          snt: '#10b981', // S&T emerald green
          trd: '#f59e0b', // TRD traction amber/gold
        },
      },
    },
  },
  plugins: [],
};
