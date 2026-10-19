/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#000000',
        panel: '#0e1014',
        panel2: '#171a21',
        line: '#2c3544',
        ink: '#ffffff',
        mute: '#cfd8e3',
        accent: '#00c2ff', brand: '#0d52ad',
        ok: '#4ade80',
        warn: '#fcd34d',
        bad: '#ff7b7b',
        info: '#7cb8ff',
      },
      fontFamily: {
        sans: ['Poppins', 'system-ui', 'sans-serif'],
        mono: ['Geist Mono Variable', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
}
