# ЖК Lakeview — Project Brain

## What is this?

Promotional one-page website for **ЖК Lakeview** — a business-class residential complex near a lake in Lviv, Ukraine (вул. Володимира Великого, 2а). Developer: **Vygoda (Вигода)**.

**Live demo:** https://yaroslavpetrukha.github.io/Lakeview/
**Repo:** https://github.com/YaroslavPetrukha/Lakeview

## Tech Stack

- **Pure static HTML/CSS/JS** — single `index.html` file (~1000 lines)
- Fonts: Cormorant Garamond (headings) + Outfit (body) via Google Fonts
- No build tools, no frameworks, no npm
- Deployed via **GitHub Pages** with Actions workflow (`.github/workflows/deploy.yml`)
- Every `git push` to `main` auto-deploys

## Architecture

Single-page site with sections:
1. **Hero** — full-screen with render bg, CTAs, key stats (4 sections, 44-183m2, from $1600/m2, 2-level parking, 2027 completion)
2. **Apartments** — features grid (security, gym, heating, all-inclusive) + plan cards with tabs (1/2/3-room filter) + apartment modal with lead form
3. **Catalog CTA** — split-layout lead form to receive PDF with all plans
4. **Conditions** — pricing ($1600/m2), installment, legal contract + trust bar
5. **Location** — map embed (Google Maps iframe) + distance badges
6. **Construction** — monthly photo grid (Dec 2025 — Mar 2026) with lightbox
7. **Commercial** — ground floor commercial spaces with type cards + lead form
8. **Gallery** — horizontal scroll of 6 renders
9. **Footer** — nav, contacts, mini lead form

### Key Components
- **Callback modal** (`#cbModal`) — "order a call" popup
- **Apartment modal** (`#aptModal`) — detailed view with lead form per apartment
- **Construction lightbox** (`#conLb`) — full-screen photo viewer with swipe
- **Lead forms** — 5 forms total (callback, apartment, catalog, commercial, footer), all log to console (`[LEAD]` / `[LEAD-APT]`), no real backend yet
- **Mobile nav** — hamburger menu with full-screen overlay

### CSS Design System
- Color palette: `--em` (emerald #0F4C3A), `--gold` (#C5A55A), neutrals
- Border radius: `--r` (16px), `--r2` (24px)
- Responsive: mobile-first breakpoints at 768px, 600px
- Animations: scroll-reveal via IntersectionObserver, hover transforms

## File Structure

```
/
├── index.html              # The entire site
├── .gitignore
├── .github/workflows/
│   └── deploy.yml          # GitHub Pages deploy
├── img/
│   ├── renders/            # Optimized site renders (hero, aerial, etc.)
│   ├── plans/              # Floor plan images (s1-039-1k-53m2.jpg pattern)
│   └── construction/       # Monthly photo galleries
│       ├── dec-2025/       # 12 photos
│       ├── jan-2026/       # 11 photos
│       ├── feb-2026/       # 12 photos
│       └── mar-2026/       # 15 photos
├── assets/                 # Source/backup assets (not used by site directly)
│   ├── instagram/          # Instagram content library (29 posts, categorized)
│   ├── plans/              # Higher-res plan images
│   └── renders/            # Additional render variants
├── Рендера/                # Original hi-res renders (10-18MB each, git-ignored)
└── Планування/             # Source floor plans by section (git-ignored)
    ├── Квартири/           # Sections 1-4, all apartments
    └── Паркомісця/         # Parking levels -1, -2
```

## Key Business Facts

- **Developer:** Вигода (Vygoda)
- **Address:** вул. Володимира Великого, 2а, Львів
- **Price:** from $1600/m2
- **Apartments:** 44 — 183 m2 (1/2/3-room)
- **4 sections**, up to 15 floors
- **2-level underground parking**
- **Completion:** 2027
- **Included in price:** plastered walls, armored doors, quality windows, meters, electrical wiring
- **Payment:** 30% down payment, installment during construction
- **Phone:** +38 066 990 03 90
- **Email:** vygoda.plus@gmail.com
- **Instagram:** @lakeviewlviv

## Conventions

- Language: Ukrainian (lang="uk")
- CSS class naming: short abbreviated classes (`.ctn`, `.sec`, `.sl`, `.st`, `.sd`, `.rv`, `.bp`, `.bs`)
- All styles inline in `<style>` block within `index.html`
- All JS inline in `<script>` block at bottom of `index.html`
- Image naming: `{section}-{number}-{rooms}-{area}.jpg` for plans
- Construction photos: `{month}-{number}.jpg` in monthly folders

## TODOs

- [ ] Connect lead forms to real backend (currently console.log only)
- [ ] Add real Google Maps API key (currently basic iframe embed)
- [ ] SEO: add Open Graph meta tags for social sharing
- [ ] Add favicon
- [ ] Consider splitting CSS/JS into separate files if site grows
