# Icons — TODO

Generated SVG favicon at `/favicon.svg` (gold "L" lettermark on emerald background).

## Before final launch

Generate raster fallbacks from `favicon.svg`:

- `/favicon-32.png` — 32×32 PNG (legacy browsers)
- `/favicon-192.png` — 192×192 PNG (Android home screen)
- `/favicon-512.png` — 512×512 PNG (Android splash)
- `/apple-touch-icon-180.png` — 180×180 PNG (iOS home screen)

After generation, add to `index.html` `<head>`:

```html
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon-180.png">
```

And update `site.webmanifest` to include the 192/512 PNG entries.

Modern browsers handle SVG favicons natively, so the current setup works for ~95% of users. PNG fallbacks are for legacy/iOS edge cases.
