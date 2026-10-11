/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        wine: { DEFAULT: '#3B0016', deep: '#24000D', soft: '#5E303D' },
        bolt: { DEFAULT: '#E0262A', dark: '#B81B1F', light: '#FF6B6E', cta: '#D42227' },
        ink: '#0B0B0B',
        cream: { DEFAULT: '#F5F1EA', dim: '#D9CFC3' },
      },
      fontFamily: {
        display: ['Anton', 'Impact', 'Arial Narrow', 'sans-serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      letterSpacing: { tightest: '-0.02em' },
    },
  },
  plugins: [],
}
