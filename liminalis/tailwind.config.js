/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Syne', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        sans: [
          '"DM Sans"',
          'ui-sans-serif',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          'sans-serif',
        ],
      },
      colors: {
        bg: '#060810',
        surface: '#0d1120',
        line: 'rgba(255,255,255,0.07)',
        text: '#e8eaf2',
        muted: '#636b8a',
        accent: '#4f8eff',
        accent2: '#a78bfa',
      },
    },
  },
  plugins: [],
};
