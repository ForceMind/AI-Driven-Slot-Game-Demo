/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'slot-gold': '#FFD700',
        'slot-dark': '#1a1a1a',
        'slot-panel': '#2d2d2d',
      }
    },
  },
  plugins: [],
}
