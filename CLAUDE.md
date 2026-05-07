# ЖК Lakeview — Project Brain

## What is this?

Promotional one-page website for **ЖК Lakeview** — a business-class residential complex near a lake in Lviv, Ukraine (вул. Володимира Великого, 2а). Developer brand: **Вигода**. Legal entity: ПП «ДІК "Вигода +"», ЄДРПОУ 44876801.

**Production:** https://www.lakeview.com.ua/
**Mirror (GitHub Pages):** https://yaroslavpetrukha.github.io/Lakeview/
**Repo:** https://github.com/YaroslavPetrukha/Lakeview

## Tech Stack

- **Pure static HTML/CSS/JS** — single `index.html` file (~1880 lines)
- **PHP 8.2 backend** — `api/submit.php` for form processing (Telegram delivery)
- Fonts: Cormorant Garamond (headings) + Outfit (body) via Google Fonts
- No build tools, no frameworks, no npm
- **Hosting:** shared cPanel-style host on `uj593106.ftp.tools` (CloudLinux 8 + LiteSpeed/Apache, .htaccess support)
- **Deploy:** `./deploy.sh` (rsync over SSH, see Deploy section)

## Architecture

Single-page site with sections:
1. **Hero** — full-screen render bg with responsive AVIF/WebP/JPG, CTAs, key stats
2. **Quick Facts card** — citable elevator pitch for AI engines
3. **Apartments** — features grid + plan cards with tabs (1/2/3-room filter) + apartment modal with lead form
4. **Catalog CTA** — split-layout lead form to receive PDF with all plans
5. **Conditions** — pricing ($1600/m²), installment, legal contract + trust bar
6. **FAQ** — 10 native `<details>` Q&A blocks (also in JSON-LD FAQPage)
7. **Location** — map embed + distance badges
8. **Construction** — monthly photo grid (Dec 2025 — Mar 2026) with WebP thumbnails + lightbox
9. **Developer (Вигода)** — credentials, principles, evidence base
10. **Commercial** — ground floor commercial spaces with type cards + lead form
11. **Gallery** — horizontal scroll of 6 renders (AVIF + WebP + JPG)
12. **Footer** — nav, contacts, mini lead form

### Key Components
- **Callback modal** (`#cbModal`), **apartment modal** (`#aptModal`), **construction lightbox** (`#conLb`), **plan lightbox** (`#planLb`) — all WCAG-compliant with focus trap, ARIA dialog, ESC handling
- **Lead forms (5):** callback, apartment, catalog, commercial, footer — POST to `/api/submit.php` → Telegram + redirect to `/thanks.html?form=...`
- **Mobile nav** — hamburger menu (`<nav>` with aria-expanded)

### CSS Design System
- Colors: `--em` (#0F4C3A emerald), `--gold` (#C5A55A), `--gold-aa` (#85661F — WCAG AA contrast for CTAs), `--gold-l` (#D4BA7A — light gold for dark backgrounds)
- Border radius: `--r` (16px), `--r2` (24px)
- Responsive: mobile-first, breakpoints 768px / 600px
- Animations: scroll-reveal via IntersectionObserver; respects `prefers-reduced-motion`
- Skip-link, `:focus-visible` outlines, aria-labels everywhere (Ukrainian)

## File Structure

```
/
├── index.html                     # The entire site (~1880 lines)
├── thanks.html                    # Post-submit page (noindex)
├── privacy.html                   # Privacy policy (noindex)
├── favicon.svg                    # Gold L on emerald
├── site.webmanifest               # PWA manifest
├── robots.txt                     # AI bots explicitly allowed
├── sitemap.xml                    # Single URL with image extensions
├── llms.txt + llms-full.txt       # AI citation summary
├── .htaccess                      # HTTPS+www, security headers, cache, gzip
├── .deployignore                  # rsync excludes for deploy.sh
├── deploy.sh                      # Production deploy script (env-driven)
├── .deploy-env.example            # Template for SFTP creds
│
├── api/
│   ├── submit.php                 # Universal form handler (5 forms → Telegram)
│   ├── config.example.php         # Placeholders for token + chat ID
│   ├── config.php                 # LOCAL ONLY — gitignored, real Telegram secrets
│   └── .htaccess                  # Block all PHP except submit.php
│
├── logs/
│   ├── .htaccess                  # Deny all
│   ├── .gitkeep
│   ├── submissions.log            # Form submissions (gitignored)
│   └── rate/                      # Per-IP rate-limit JSON cache (gitignored)
│
├── img/
│   ├── renders/                   # 7 renders × {jpg, webp, avif} + hero responsive 640/1280/1920
│   ├── og-cover.jpg               # Dedicated 1200×630 social share
│   ├── plans/                     # Floor plan images (s1-039-1k-53m2.jpg pattern)
│   └── construction/              # Monthly photo galleries (jpg + webp)
│       ├── dec-2025/  jan-2026/  feb-2026/  mar-2026/
│
└── icons/README.md                # TODO: PNG fallbacks before final iOS Safari support
```

## Key Business Facts

- **Brand:** ЖК Lakeview
- **Developer brand:** Вигода
- **Legal entity:** ПП «ДІК "Вигода +"», ЄДРПОУ 44876801
- **Address (object):** вул. Володимира Великого, 2а, Львів
- **Sales office:** вул. В. Великого, 4, кабінет 406, Львів
- **Phone:** +38 096 990 03 90 (`tel:+380969900390`)
- **Email:** vygoda.sales@gmail.com
- **Instagram:** @lakeviewlviv
- **Price:** from $1600/m²
- **Apartments:** 44–183 m² (1/2/3-room)
- **4 sections**, up to 15 floors
- **Parking:** 2 underground levels, 138 spots
- **Completion:** 2027
- **Included in price:** plastered walls, armored doors, energy-efficient windows, meters, electrical wiring
- **Payment:** 30% down, interest-free installment during construction

## Forms backend (PHP)

- `POST /api/submit.php` accepts: `_form` (callback|apartment|catalog|commercial|footer), `name`, `phone`, `messenger`, `apt_meta`, `website` (honeypot), `ts` (timestamp ms)
- Validation: honeypot + time-trap + Origin allowlist + per-IP rate-limit (5/h) + phone/name format
- On success: curl to Telegram Bot API, log to `logs/submissions.log`, return JSON `{ok:true, redirect:"/thanks.html?form=..."}`
- Honeypot/time-trap reject silently with fake-success (no info leak to bots)
- Telegram bot: `@vugodaform_bot`, group "Заявки LAKEVIEW"
- Bot token + chat ID in `api/config.php` (gitignored, exists locally and on server only)

## Deploy

**One-time setup (local):**
1. Copy `.deploy-env.example` → `.deploy-env` and fill in SFTP credentials
2. Ensure `api/config.php` exists locally with real Telegram token (copy from `config.example.php`)

**Deploy:**
```bash
source .deploy-env && ./deploy.sh
```

**What it does:**
1. First run: backs up existing WordPress (or any prior site) to `~/lakeview.com.ua/www-wp-backup/`
2. Rsync local files to `~/lakeview.com.ua/www/` (respects `.deployignore` + `--delete-excluded`)
3. Uploads `api/config.php` with chmod 600
4. Smoke-tests all critical endpoints

**Manual rollback:** SSH to host, `mv www www-broken && mv www-wp-backup www` (only if WP backup still relevant; for incremental rollback, deploy from a tagged git commit).

## Conventions

- Language: Ukrainian (lang="uk")
- CSS class naming: short abbreviated classes (`.ctn`, `.sec`, `.sl`, `.st`, `.sd`, `.rv`, `.bp`, `.bs`)
- All styles inline in `<style>` block within `index.html` (small site — split is overkill)
- All JS inline in `<script>` block at bottom
- Image naming: `{section}-{number}-{rooms}-{area}.jpg` for plans, `{month}-{number}.jpg` for construction
- Headings: single `<h1>` (hero), `<h2>` per section, `<h3>` sub-sections, no h5+
- All inputs have `name=`, `autocomplete=`, label or `aria-label`

## Quality bars (post pre-launch audit)

- **SEO:** ~8/10. Title/meta optimized, OG, JSON-LD @graph (7 entities), canonical, robots.txt, sitemap.xml, llms.txt
- **AI search:** ~8/10. FAQ section + FAQPage schema, llms.txt + llms-full.txt, Quick Facts citable passage, all major AI bots explicitly allowed
- **Accessibility:** 8.5/10. 0 axe-core violations. Focus traps, semantic buttons, aria-labels, skip-link, prefers-reduced-motion, contrast AA across all CTAs
- **Performance:** LCP 544ms (mobile hero AVIF 29 KB at 640w). All renders + 50 construction photos in WebP/AVIF
- **Security:** CSP-equivalent via meta+headers, HSTS preload, honeypot+time-trap+rate-limit on forms, no secrets in repo

## TODOs (post-launch)

- [ ] **Cloudflare Turnstile** — enable for stronger bot protection (requires CF account + site_key + secret_key, then `TURNSTILE_ENABLED=true` in `api/config.php`)
- [ ] **GA4 + Facebook Pixel** — populate placeholders in `thanks.html`, set up conversion events
- [ ] **Google Search Console** — verify domain, submit sitemap, monitor indexing
- [ ] **Google Business Profile** — create for Lakeview/Vygoda for local SEO + Maps
- [ ] **Real Google Maps API key** — current basic iframe embed
- [ ] **PNG favicon fallbacks** — see `icons/README.md` for 32×32, 180×180, 192×192, 512×512 maskable
- [ ] **OG cover (1200×630)** — current is auto-cropped from hero; produce a dedicated branded one
- [ ] **GitHub Pages → primary domain redirect** — set CNAME or 301 from old yaroslavpetrukha.github.io URL
- [ ] **Rotate Telegram bot token + SFTP password** — both were shared in chat during setup
- [ ] **Privacy / cookie banner** — when GA4/Pixel go live (Ukrainian law / GDPR)
- [ ] **PHP backups + monitoring** — set up nightly backup of `logs/submissions.log` + simple uptime check
