/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: '#0A0F21',
        surface: '#1A2035',
        primary: '#38BDF8',
        secondary: '#38BDF8', // Kept same as primary for consistency in action elements
        'user-bubble-text': '#0A0F21',
        text: '#E6EDF3',
        textSecondary: '#8B949E',
        border: '#30363D',
        success: '#238636',
        warning: '#f59e0b',
        error: '#DA3333',
      },
      borderRadius: {
        '4xl': '2rem',
      },
      keyframes: {
        'fade-in': {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(56, 189, 248, 0.4)' },
          '50%': { boxShadow: '0 0 10px 5px rgba(56, 189, 248, 0)' },
        }
      },
      animation: {
        'fade-in': 'fade-in 0.5s ease-out forwards',
        'pulse-glow': 'pulse-glow 2s infinite ease-in-out',
      },
      typography: ({ theme }) => ({
        invert: {
          css: {
            '--tw-prose-body': theme('colors.text'),
            '--tw-prose-bold': theme('colors.text'),
            '--tw-prose-headings': theme('colors.text'),
            '--tw-prose-links': theme('colors.secondary'),
            '--tw-prose-bullets': theme('colors.border'),
            '--tw-prose-quotes': theme('colors.text'),
            '--tw-prose-quote-borders': theme('colors.border'),
          },
        },
      }),
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
