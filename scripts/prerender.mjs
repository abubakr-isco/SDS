// Writes the rendered homepage into dist/index.html, so crawlers and brand reviewers that don't run
// JavaScript still see SDS UZ INC's name, services and contact details. Runs after both Vite builds.
import { readFileSync, rmSync, writeFileSync } from 'node:fs'
import { render } from '../dist-ssr/entry-server.js'

const file = 'dist/index.html'
const shell = '<div id="root"></div>'
const html = readFileSync(file, 'utf8')
if (!html.includes(shell)) throw new Error(`${shell} not found in ${file}`)

writeFileSync(file, html.replace(shell, () => `<div id="root">${render()}</div>`))
rmSync('dist-ssr', { recursive: true })
