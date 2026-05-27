/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        dark: {
          50:  '#f8fafc',
          100: '#1e2433',
          200: '#171d2d',
          300: '#111827',
          400: '#0d1117',
          500: '#080d14',
        },
        brand: {
          primary:  '#6366f1',
          success:  '#22c55e',
          warning:  '#f59e0b',
          danger:   '#ef4444',
          info:     '#3b82f6',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow':  'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in':     'fadeIn 0.25s ease-out',
        'slide-up':    'slideUp 0.3s ease-out',
        'slide-right': 'slideRight 0.25s ease-out',
        'shimmer':     'shimmer 1.8s infinite linear',
        'ring-pulse':  'ringPulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'bounce-in':   'bounceIn 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275)',
        'count-up':    'countUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn:    { from: { opacity: '0', transform: 'translateY(6px)' },  to: { opacity: '1', transform: 'translateY(0)' } },
        slideUp:   { from: { opacity: '0', transform: 'translateY(16px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        slideRight:{ from: { opacity: '0', transform: 'translateX(-12px)' },to: { opacity: '1', transform: 'translateX(0)' } },
        shimmer: {
          '0%':   { backgroundPosition: '-400px 0' },
          '100%': { backgroundPosition: '400px 0' },
        },
        ringPulse: {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(99,102,241,0.4)' },
          '50%':      { boxShadow: '0 0 0 6px rgba(99,102,241,0)' },
        },
        bounceIn: {
          '0%':   { opacity: '0', transform: 'scale(0.8)' },
          '60%':  { opacity: '1', transform: 'scale(1.05)' },
          '100%': { transform: 'scale(1)' },
        },
        countUp: {
          from: { opacity: '0.4', transform: 'scale(0.96)' },
          to:   { opacity: '1',   transform: 'scale(1)' },
        },
      },
      backgroundImage: {
        'shimmer-gradient': 'linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.04) 50%, transparent 100%)',
        'card-gradient':    'linear-gradient(135deg, rgba(255,255,255,0.03) 0%, transparent 100%)',
      },
      boxShadow: {
        'glow-indigo': '0 0 20px rgba(99,102,241,0.15)',
        'glow-green':  '0 0 20px rgba(34,197,94,0.15)',
        'glow-red':    '0 0 20px rgba(239,68,68,0.2)',
        'card':        '0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)',
      },
    },
  },
  plugins: [],
}
