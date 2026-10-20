# Contributing

Keep the skill reusable across projects. Match example UI to its source, label simulated states, preserve stable screen IDs, and never discard unresolved feedback during a revision.

## Development

Python 3.10+ builds boards with no third-party Python packages. Node 22+ is used for browser tests.

```sh
npm ci
npm test
npm run build:example
npx playwright install chromium
npm run test:browser
```

The example HTML is generated from the checked-in engine and starter model. Rebuild it when those change. CI checks that it is current.

For changes to drag, resize, pan, zoom, annotations, or export, verify observable behavior in browser tests. Do not substitute screenshots for feedback round-trip checks. Include a screenshot of the changed workflow when it helps a reviewer.

The skill template is `skills/flow-review-canvas/assets/canvas.html`; the builder and model reference live alongside it. Keep their behavior in sync. Browser code is embedded directly so generated boards remain standalone.

## Screenshots

README screenshots are actual browser captures of the working canvas. Mockup account states and permission prompts are illustrative. The native msgblast Demo image in the origin section is an app capture with simulated data. Do not publish personal information, account identifiers, or feedback from someone else’s review.

`scripts/capture.mjs` can capture a local board and record a short interaction. It accepts a local HTML file as an argument. Use only a sanitized demo board for public documentation. Project icon artwork is not distributed as a reusable asset pack.
