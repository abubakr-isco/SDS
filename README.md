# SDS — Trucking & Freight Website

Single-page marketing site for SDS, an American trucking and freight transportation company.

**Stack:** React 19 · TypeScript · Vite 8 · Tailwind CSS 4 · lucide-react icons. No backend.

## Commands

```bash
npm install        # install dependencies
npm run dev        # dev server at http://localhost:5173
npm run build      # type-check + production build to dist/
npm run preview    # serve the production build locally
npm run lint       # oxlint
```

## Where to edit content

Almost everything company-specific lives in **`src/config/site.ts`**:

| What | Key |
| --- | --- |
| Phone, email, hours, service area | `contact` (set `placeholder: false` once real) |
| Services (proposed — confirm or remove) | `services` (`confirmed` flag) |
| Fleet / equipment categories | `fleet` (`confirmed` flag) |
| Value propositions | `values` |
| Navigation & CTAs | `navigation`, `cta` |
| Freight type options in the quote form | `freightTypes` |
| Social profiles (only real ones) | `socialLinks` |
| USDOT / MC numbers | `company.registration` |
| Production domain | `company.siteUrl` — also update `index.html`, `public/robots.txt`, `public/sitemap.xml` |

Legal pages: `public/privacy.html` (Privacy Policy), `public/sms-terms.html` (SMS Terms) and
`public/terms.html` (Terms of Service, still a placeholder).

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

`npm run build` outputs a static site in `dist/` that can be hosted on any static host
(Netlify, Vercel, Cloudflare Pages, S3 + CloudFront, etc.). No hosting platform is configured in this
repository yet.
