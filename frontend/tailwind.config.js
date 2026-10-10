/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: { brand: { 50: "#eef2ff", 100: "#e0e7ff", 500: "#4f46e5", 600: "#4338ca", 700: "#3730a3", 900: "#1e1b4b" } },
      fontSize: { xs: ["0.875rem", "1.25rem"], sm: ["0.9375rem", "1.375rem"] },
    },
  },
  plugins: [],
};
