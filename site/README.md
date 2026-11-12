# GHOSTTRACE website

Static site for the Google OAuth branding page and GitHub Pages deployment.

## Files
- `index.html` — landing page
- `privacy.html` — privacy policy (matches the app's real data handling)
- `terms.html` — terms of service
- `logo.svg` — mark + favicon
- `logo.png` — 512×512 for the Google Cloud Console logo upload

## Deploy to GitHub Pages (2 minutes)
```bash
cd site
git init && git add . && git commit -m "GHOSTTRACE site"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ghosttrace-site
git push -u origin main
```
Then: repo → Settings → Pages → Source: **Deploy from a branch** → `main` / root → Save.
Your site is live at `https://YOUR_USERNAME.github.io/ghosttrace-site/`.

## Fill the Google Cloud Console (Auth → Branding / Google Auth Platform)
| Field | Value |
|---|---|
| App name | GHOSTTRACE |
| User support email | your Gmail |
| Developer contact | your Gmail |
| Application home page | `https://YOUR_USERNAME.github.io/ghosttrace-site/` |
| Privacy policy link | `https://YOUR_USERNAME.github.io/ghosttrace-site/privacy.html` |
| Terms of service link | `https://YOUR_USERNAME.github.io/ghosttrace-site/terms.html` |
| Logo | upload `logo.png` |
| Authorized domains | leave empty (only needed to leave Testing mode) |
| Test users | add your Gmail address |

## Test locally
```bash
python -m http.server 8090   # then open http://localhost:8090
```