# py-ego Mini Program

Uni-app frontend for the py-ego WeChat mini program.

The interface follows the design spec in `docs/superpowers/specs/2026-03-24-wechat-mini-program-design.md` and borrows the visual language of mails.dev:

- warm paper background
- strict black hairline grid
- large editorial serif headings
- mono text for system state and command-like data
- compact controls with almost no shadow or rounded decoration
- a single green status accent

## Development

```bash
npm install
npm run dev:mp-weixin
```

Open the generated WeChat mini program output in WeChat DevTools.

## API

Set the backend base URL in `src/api/request.js` during local development. The frontend expects the backend routes under `/api`, matching `py-ego-miniapp/app/api`.
