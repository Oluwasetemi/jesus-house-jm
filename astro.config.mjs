// @ts-check
import mdx from '@astrojs/mdx'
import sitemap from '@astrojs/sitemap'
import { defineConfig } from 'astro/config'

export default defineConfig({
  integrations: [mdx(), sitemap()],
  site: 'https://jesus-house-jamaica.netlify.app',
  output: 'static',
  vite: {
    server: {
      proxy: {
        // In dev, forward /api/* to the Netlify functions server (ntl functions:serve)
        '/api': 'http://localhost:9999',
      },
    },
  },
})
