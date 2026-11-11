# Eudokia website timeline

Client-facing timeline for the Eudokia Shopify Plus build. It is generated from the private GitHub project and published with GitHub Pages.

- `scripts/build.py` reads the project and writes `dist/index.html`.
- `template.html` is the page design. Data is filled in at build time.
- `.github/workflows/build.yml` rebuilds and deploys every day at 6am Eastern, on every push to `main`, and from **Actions → Build timeline → Run workflow**.

The workflow needs a repo secret named `PROJECT_TOKEN`: a classic personal access token with the `repo` and `read:project` scopes.

## Hiding an item from the client

Add the `internal` label to the issue, or add its number to `HIDE_ISSUES` in `scripts/build.py`. Unlabeled issues are hidden too, and sub-issues show as progress on their parent.

## Building locally

```bash
PROJECT_TOKEN=$(gh auth token) python3 scripts/build.py
```
