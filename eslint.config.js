import setemiojo from '@setemiojo/eslint-config'

export default setemiojo({
  type: 'app',
  typescript: true,
  astro: true,
  stylistic: {
    indent: 2,
    quotes: 'single',
  },
})
