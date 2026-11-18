# contributing

## product copy and typography

Owned product copy uses lowercase except proper nouns. This includes headings,
body copy, links, buttons, error messages and accessibility labels. Preserve user
content, formulas, case-sensitive mathematical symbols, code/API identifiers,
link destinations and exact bibliographic/legal attribution. Write lowercase
source text; never apply a blanket CSS `text-transform` to user content.

Run `make check-brand-copy` after editing the public-home pages. It also runs
inside `make test`. The dependency-free check extracts the supported Markdown
subset in `README.md`, `PRIVACY.md` and `SUPPORT.md`, including HTML image alt text,
titles and accessibility labels. It excludes fenced/inline code and link targets.
Proper names have an explicit rationale in `tools/check-brand-copy.py`; research
titles and unresolved publication markers are exact, finite exclusions. Add an
exception only after checking its ownership and spelling, with a rationale and
negative control. Prefer plain words such as “interface”, “links” and “operating
system” over ambiguous initialisms. New public-facing pages must be added to the
explicit page inventory. This is not a general Markdown parser or a check of
rendered OS/platform-owned labels, user graphs, C source, licenses or research
provenance. It does not establish publication readiness.

The app's actual interface font is **Source Code Pro**, registered from
`apps/flet/src/assets/fonts/SourceCodePro-Regular.ttf` in the graphing repository.
GitHub controls README Markdown typography. Keep normal Markdown paragraphs and
headings; do not wrap prose in code blocks or invent a custom site to force a
font. The README screenshots carry the app's branding. Preserve them unless a
verified stale screenshot needs a targeted update. Screenshot refreshes must
respect active app/device sessions.

The user's 2026-10-26 clarification identifies this README as the intended site
and explicitly relaxes matching its prose font to the app. No website deployment
or publication is part of these local branding changes. Privacy/support pages
remain drafts with their existing publication decisions unresolved.
