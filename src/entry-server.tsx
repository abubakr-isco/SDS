import { renderToString } from 'react-dom/server'
import App from './App'

/** Homepage HTML for scripts/prerender.mjs. */
export function render() {
  return renderToString(<App />)
}
