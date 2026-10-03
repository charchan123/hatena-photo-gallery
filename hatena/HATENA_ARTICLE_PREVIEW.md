# Hatena article-page preview patch — Phase 4C.11

## Purpose

This patch visually aligns normal Hatena article pages with the new-top design while preserving Hatena-native article authoring, existing comments, Hatena Star/bookmark controls, article metadata, categories, and sidebar modules.

It is **not active automatically**. The repository file is a preview/deployment artifact only.

## Current Hatena setup assumed

- Existing header HTML keeps the `.header1` / `.header2` image containers and current menu markup.
- Current Design CSS already scopes the GitHub Pages portal override to `body.static-page-new-top`.
- The new article patch is scoped to `body.page-entry:not(.static-page-new-top)`, so it does not change /new-top.

## Preview procedure

1. Open Hatena Blog → Design → Customize → Design CSS.
2. Keep the current CSS unchanged.
3. Append the entire contents of `hatena-article-newtop-preview.css` to the **end**.
4. Use Hatena's Preview. Do not save/publish yet.
5. Check at least:
   - normal article hero on desktop and mobile;
   - article title/date/category;
   - article body headings, links, tables and photos;
   - Hatena Star/bookmark area;
   - an article with existing comments and the comment form;
   - right sidebar modules on desktop;
   - mobile menu open/close;
   - PAGE TOP;
   - /new-top remains visually unchanged.
6. If any native Hatena selector differs in the active theme, adjust only the scoped preview patch.
7. After visual approval, keep the final patch ready and apply it when new-top is officially released.

## Visual intent

- Same #f7fcf4 paper background as new-top.
- Reuse the new-top forest background and Amanita cutout.
- White article cards with green headings, soft borders and restrained shadows.
- Existing navigation remains functional but changes from the old blue bar to a green/white treatment.
- Sidebar remains visible and becomes a set of white/green modules.
- Existing comments and native Hatena controls remain present.

## Rollback

Because this is an append-only patch, rollback is simply removing the appended Phase 4C.11 block and restoring the saved pre-change Design CSS.

## Important

Do not copy this patch into production before preview approval. It deliberately does not alter the header HTML or blog content data.
