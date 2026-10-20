# Privacy

The generated canvas runs locally in your browser. It contains no analytics, remote fonts, upload endpoint, or automatic feedback submission. Images supplied to the builder are embedded in the output rather than fetched by the canvas at runtime.

The browser stores your review in local storage under a board-specific key. Notes, comments, screen copy, layout, and camera position stay in that browser until you export them or clear its storage. File and localhost previews have separate storage contexts.

JSON exports contain the board’s flows, screen copy, layout, wires, notes, comment text and anchors, resolution state, camera position, and timestamps. Markdown exports contain readable feedback and screen references. HTML exports include the review and any embedded imagery. Review exports before sharing them, especially when your project contains private data.

The builder reads the model, optional existing board, optional image files, and optional CSS you explicitly provide. It writes the requested HTML file. It does not contact providers, change system permissions, or send messages.

Installing through a third-party package manager may involve that manager’s network requests or telemetry; those are separate from the canvas. See the installer’s own documentation.

README badges may make image requests when you view the GitHub page. They are not part of the standalone canvas.
