/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Clinical navy blue - primary
        'clinical-navy': '#0A1628',
        'clinical-navy-light': '#1E3A5F',
        'clinical-navy-dark': '#050D1A',
        
        // Semantic severity colors
        'severity-major': '#DC2626',
        'severity-major-light': '#FEE2E2',
        'severity-minor': '#D97706',
        'severity-minor-light': '#FEF3C7',
        'severity-admin': '#2563EB',
        'severity-admin-light': '#DBEAFE',
        
        // Risk tier colors
        'risk-high': '#DC2626',
        'risk-high-light': '#FEE2E2',
        'risk-medium': '#D97706',
        'risk-medium-light': '#FEF3C7',
        'risk-low': '#059669',
        'risk-low-light': '#D1FAE5',
        
        // Neutral surfaces
        'surface': '#FFFFFF',
        'surface-alt': '#F8FAFC',
        'surface-elevated': '#FFFFFF',
        
        // Text colors
        'text-primary': '#0F172A',
        'text-secondary': '#475569',
        'text-tertiary': '#94A3B8',
        'text-muted': '#64748B',
        
        // Borders
        'border': '#E2E8F0',
        'border-light': '#F1F5F9',
        'border-dark': '#CBD5E1',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
        mono: ['IBM Plex Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
      },
      boxShadow: {
        'card': '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
        'card-hover': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        'elevation': '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
      },
      spacing: {
        'page': '1.5rem',
        'section': '1.25rem',
        'card': '1rem',
      },
    },
  },
  plugins: [],
}
