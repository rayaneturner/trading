// Génère public/og-image.png (1200×630) pour l'aperçu LinkedIn. Usage : npm run og
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const require = createRequire(import.meta.url)
let chromium
try {
  ;({ chromium } = require('playwright'))
} catch {
  ;({ chromium } = require('/opt/node22/lib/node_modules/playwright'))
}
const b64 = (p) => readFileSync(resolve(root, p)).toString('base64')

const html = `<!doctype html><html><head><style>
@font-face{font-family:Anton;src:url(data:font/woff2;base64,${b64('public/fonts/anton.woff2')})}
@font-face{font-family:Inter;src:url(data:font/woff2;base64,${b64('public/fonts/inter.woff2')});font-weight:100 900}
*{margin:0;box-sizing:border-box}
body{width:1200px;height:630px;background:#3B0016;color:#F5F1EA;font-family:Inter;position:relative;overflow:hidden}
.bolt{position:absolute;right:-60px;top:-40px;height:720px;fill:#5E303D;opacity:.75}
.cut{position:absolute;left:-100px;bottom:120px;width:1600px;height:3px;background:#E0262A;transform:rotate(-12deg);transform-origin:left}
.wrap{position:absolute;left:72px;top:64px;right:420px}
.logo{font-family:Anton;font-size:44px;transform:skewX(-8deg);display:flex;align-items:center;gap:2px}
.logo svg{height:40px;fill:#E0262A}
h1{font-family:Anton;font-weight:400;font-size:128px;line-height:.9;margin-top:44px;transform:skewX(-8deg);transform-origin:left bottom}
h1 span{color:#E0262A}
p{margin-top:30px;font-size:26px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:#F5F1EA}
.tag{margin-top:10px;font-size:22px;opacity:.85;font-weight:500;text-transform:none;letter-spacing:0}
.photo{position:absolute;right:70px;top:150px;width:330px;height:330px;border-radius:50%;box-shadow:0 0 0 6px #E0262A,0 0 0 14px #3B0016,0 0 0 16px rgba(245,241,234,.25)}
</style></head><body>
<svg class="bolt" viewBox="0 0 24 40"><path d="M16.5 0 2 23h8.5L6 40 22 15h-8.6L16.5 0z"/></svg>
<div class="cut"></div>
<div class="wrap">
  <div class="logo">OBL<svg viewBox="0 0 24 40"><path d="M16.5 0 2 23h8.5L6 40 22 15h-8.6L16.5 0z"/></svg>QUE</div>
  <h1>REPRENEZ<br><span>LE CONTRÔLE.</span></h1>
  <p>Coach sportif &amp; nutrition · Bourges</p>
  <p class="tag">Une méthode. Un objectif. Des résultats.</p>
</div>
<img class="photo" src="data:image/webp;base64,${b64('public/img/jahen.webp')}">
</body></html>`

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1200, height: 630 } })
await page.setContent(html, { waitUntil: 'load' })
await page.evaluate(() => document.fonts.ready)
await page.screenshot({ path: resolve(root, 'public/og-image.png') })
await browser.close()
console.log('✓ public/og-image.png')
