# Privacy

The generated canvas runs locally in your browser. It contains no analytics, remote fonts, or automatic feedback submission. Images supplied to the builder are embedded in the output rather than fetched by the canvas at runtime.

The browser stores your review in local storage under a board-specific key. Notes, comments, screen copy, layout, and camera position stay in that browser until you export, explicitly publish, or clear its storage. File and localhost previews have separate storage contexts.

Clicking **Copy feedback JSON** writes the full review to your system clipboard, replacing its previous contents. The canvas does not read the clipboard or send copied feedback to a service. Clipboard managers and other applications may retain or access copied text.

Copied JSON and JSON exports contain the board’s flows, screen copy, layout, wires, notes, comment text and anchors, resolution state, camera position, and timestamps. Markdown exports contain readable feedback and screen references. HTML exports include the review and any embedded imagery. Review exports before sharing them, especially when your project contains private data.

The builder reads the model, optional existing board, optional image files, and optional CSS you explicitly provide. It writes the requested HTML file. It does not contact providers, change system permissions, or send messages.

The optional local publishing server serves only the selected canvas on loopback. Pressing **here.now** opens a confirmation; pressing **Publish snapshot** uploads the current standalone HTML to here.now and its storage service. This includes all screen copy and imagery, layout, notes, comments, resolution states, and camera position, even feedback outside the current viewport. Anyone with the public link can view the snapshot. Anonymous links expire after 24 hours unless claimed on here.now. See [here.now's privacy policy](https://here.now/privacy).

The publisher uses no API keys or existing account credentials. Its per-session request token and the owner-only here.now claim link are removed from public HTML and exports. Publishing results and claim links are saved separately in the publishing preview's browser storage; keep the claim link private and use it to keep a site permanently. The publisher does not serve neighboring files or expose a cross-origin API.

Published reviews are snapshots. Later edits by you or a visitor remain local to that browser until explicitly exported or published again. No shared comment database or live synchronization is enabled.

Installing through a third-party package manager may involve that manager’s network requests or telemetry; those are separate from the canvas. See the installer’s own documentation.

README badges may make image requests when you view the GitHub page. They are not part of the standalone canvas.
