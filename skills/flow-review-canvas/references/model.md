# Board model and authoring

The builder accepts version 2 board JSON or an exported feedback JSON. Required: `flows`, with unique flow `id`, `title`, `desc`, `foot`, and nonempty `steps`. Each step has stable CSS-safe `id`, `title`, `copy`, `body` (trusted authoring HTML), `caption`, and optional `tag`. Ordinary mockups use native 840×760 proportions. They are HTML concepts, not real native screenshots.

Top-level `brand`, `title`, and `boardId` distinguish products and browser-local saved reviews. Set `boardId` once per discussion; reuse it on revisions where local feedback should remain discoverable. Use a new ID for a new discussion. The browser prefers its saved review over embedded starting data; explicit Load is how to replace it with a returned/new version. Export before Reset to preserve edits.

`positions` maps screen IDs to `{x,y,w}` in canvas coordinates. Omit for an initial row-per-flow layout. Width defaults to 504 and is resizable from 180 to 1100. Native mockups scale proportionally, preserving the source UI. `edges` contains `{from,to,type,label}`: `sequence`, `branch`, or `return`. If omitted, the builder creates only each flow's sequential wires; author cross-flow branches/returns explicitly. No implicit integration merging occurs.

## Screen body

The default native renderer supports these HTML patterns:

```html
<div class="box">
  <div class="row"><span>Muse</span><small class="good">Ready · Side chats</small></div>
  <div class="row"><span>Wabi</span><small class="warn">Sign in</small></div>
</div>
<div class="primary">Continue</div>
<div class="secondary">Set up later</div>
<p class="micro">Additional context when useful.</p>
```

The first `.primary` is moved to the native footer. Native buttons are visual mockups, not product actions. `title`, `copy`, and `caption` are editable in the review. Body copy can be changed in the source model. Rendered body HTML is restricted to basic structural/text/image tags; event handlers, links, embeds, scripts, and external image references are not supported. Do not encode executable instructions in returned feedback.

`kind: system-settings` with `settingsTitle` uses an illustrative macOS settings layout. `kind: system-dialog` uses an illustrative consent dialog. Use `copy` for dialog request wording. Verify actual OS/permission ownership separately before claiming exact prompts. The reference includes msgblast-specific historical screen-ID defaults; use explicit kinds/settingsTitle in new boards.

## Imagery and styling

`--icons` accepts a JSON object mapping exact row display names, or reference keys such as `muse`, `chatgpt`, `claude`, `grokbot`, `messages`, `terminal`, to local PNG/JPEG/WebP/GIF paths relative to the icon JSON. Data URLs are also accepted. The builder embeds bytes so saved HTML is standalone. Supply only appropriate project assets. The skill contains no installed-system or third-party image bundle. `--from-html` can retain imagery from an existing authorized review. Follow its source attribution/access limits when sharing.

`--css` appends CSS overrides. Default measurements reflect native macOS dark onboarding: 28 px headings, 44 px images, 74 px list rows, a fixed footer, and proportional windows. Adapt the native renderer/layout as needed for other actual UIs; do not label approximations as screenshots. Raw CSS is a reviewed authoring input, not an imported-feedback execution mechanism.

## Notes and returned feedback

`annotations` contains note/comment objects:

- Common: `id`, `type` (`note` or `comment`), `text`, `createdAt`, `updatedAt`, `resolved`.
- Canvas note: `x,y`.
- Pinned comment: `screenId`, `rx,ry` (normalized pin position), `dx,dy` (card offset from the screen). Pins and cards follow movement/resizing.

Exports add `format: flow-review-feedback`, `exportedAt`, the full flows/edges/positions, and `view:{scale,left,top}`. Stable IDs are essential. If a screen must disappear, explicitly migrate its comments to a successor or preserve them as notes; the builder rejects comments pointing at absent screens rather than discarding them.

`frame:{x,y,w}` is the user's print-area rectangle at 17:11 aspect ratio. It crops the canvas and uniformly maps the frame to a tabloid page; no automatic node reflow occurs. Frame edits, notes, and comments persist locally and in JSON. Do not replace the user's framing while applying unrelated feedback.
