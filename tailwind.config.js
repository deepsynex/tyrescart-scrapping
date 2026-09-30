/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
    "./app/**/*.py",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:      '#f7f4fd',
          100:     '#ede5fa',
          200:     '#daccf5',
          300:     '#c0a8ed',
          400:     '#9f7dde',
          500:     '#4B237B',
          600:     '#3a1960',
          700:     '#2b1247',
          800:     '#3a1960',
          900:     '#2b1247',
          950:     '#1c0b30',
          /* Semantic aliases */
          primary: '#4B237B',
          deep:    '#2b1247',
          bright:  '#9f7dde',
          tint:    '#f7f4fd',
          border:  '#c0a8ed',
          ink:     '#0E1108',
          green:   '#4B237B',
        },
      },
      boxShadow: {
        xs: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
      },
      dropShadow: {
        xs: '0 1px 1px rgb(0 0 0 / 0.05)',
      },
      fontFamily: {
        sans: ['Plus Jakarta Sans', 'Poppins', 'Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
