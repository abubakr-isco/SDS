# SDS UZ INC — Trucking & Freight Website

Marketing site for SDS UZ INC, an American trucking and freight transportation company.

**Stack:** React 19 · TypeScript · Vite 8 · Tailwind CSS 4 · lucide-react icons. No backend.

The homepage is a React app, prerendered into `dist/index.html` at build time (`scripts/prerender.mjs`) so its
content is in the HTML for crawlers and brand reviewers. The other pages are plain HTML in `public/`.

## Commands

```bash
npm install        # install dependencies
npm run dev        # dev server at http://localhost:5180
npm run build      # type-check + production build to dist/, with the homepage prerendered
npm run preview    # serve the production build at http://localhost:5181
npm run lint       # oxlint
```

## Where to edit content

Almost everything company-specific lives in **`src/config/site.ts`**:

| What | Key |
| --- | --- |
| Phone, email, address, hours, service area | `contact` (hidden on the site until `placeholder: false`) |
| Services (proposed — confirm or remove) | `services` (`confirmed` flag) |
| Fleet / equipment categories | `fleet` (`confirmed` flag) |
| Value propositions | `values` |
| Navigation & CTAs | `navigation`, `cta` |
| Freight type options in the quote form | `freightTypes` |
| Social profiles (only real ones) | `socialLinks` |
| USDOT / MC numbers | `company.registration` |
| Production domain | `company.siteUrl` — also update `index.html`, `public/robots.txt`, `public/sitemap.xml` and the `public/*.html` pages |

Static pages in `public/`: `about.html`, `contact.html`, `privacy.html`, `terms.html`, `sms-terms.html` and `404.html`
(shared styles in `site.css`). Company details are repeated in them, so change them there too when they change in
`src/config/site.ts`. Keep the SMS consent wording in `sms-terms.html` identical to `smsConsentText`.

## Quote form

The form validates input, has a honeypot field and a minimum fill-time check, and never writes to
`localStorage`.

- **Nothing configured (default):** runs in demo mode and tells the visitor plainly that the request
  was **not** sent, with the phone/email to use instead.
- **Email via Web3Forms (current setup):** create an access key at https://web3forms.com for
  `dispatch@sdsuzinc.com` and set `VITE_WEB3FORMS_ACCESS_KEY` (in `.env.local`, or in the host's
  environment before building). Each request arrives as an email with a reference ID (`SDS-W-…`),
  the visitor's email as reply-to, and the SMS consent record (yes/no, number, time, exact wording).
- **SDS bot server:** set `VITE_QUOTE_ENDPOINT` to the bot's `/api/quote` URL instead
  (see `sds-telegram-bot/`); requests are saved in its database and sent to admins in Telegram.

Vite inlines these variables at build time: after changing them, rebuild/redeploy the site.

Add server-side validation and rate limiting on whatever receives the request — client-side checks
are not a security boundary.

## Images

Photos are stored locally in `public/images` as responsive WebP (see `IMAGE_CREDITS.md`). To swap one,
keep the `<name>-<width>.webp` naming and update the `image` entry in `src/config/site.ts`.
Replace stock photos with SDS's own fleet photography when available.

## Deploying

The site runs on Vercel (project `sds-uz-inc`, domain `sdsuz-inc.com`), configured in `vercel.json`. Deploy from this
folder with `npx vercel deploy --prod`. `VITE_WEB3FORMS_ACCESS_KEY` is set in the Vercel project's environment.
