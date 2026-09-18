# Peak web (consultant workspace)

Next.js App Router + React + TypeScript + Tailwind CSS v4. Phase 201: sign-in, Admin/Consultant
roles, Admin-only consultant accounts, and the responsive workspace shell.

- Design tokens: `app/tokens.css` (palette + semantic roles) → Tailwind utilities in `app/globals.css`.
- The browser talks only to Next.js. Server Actions and server components call the Python API
  (`peak/consultant_api/app.py`) at `PEAK_API_BASE_URL`, forwarding the HttpOnly `peak_session` cookie.
  The Python API authenticates every request and enforces the Admin role.

Local run: see `docs/PHASE201_CONSULTANT_WEB_SHELL_AUTH.md`.

```bash
npm install
npm run dev      # http://localhost:3000
npm run build && npm run lint
```
