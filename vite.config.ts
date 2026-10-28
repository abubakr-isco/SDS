import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Dedicated port: 5173 is used by another local project.
  server: { port: 5180, strictPort: true },
  preview: { port: 5181, strictPort: true },
})
