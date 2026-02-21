Purpose
- Stores the Tailwind-driven CSS source plus the generated bundle that styles the server-rendered templates.

Key Files
- `static/css/styles.css` imports Tailwind, declares utility classes for buttons, cards, grids, filters, and enhanced empty states, and includes `@source` hints so Tailwind can scan `templates/**/*.html`.
- `static/css/app.css` is the compiled output produced by the Tailwind CLI; it contains the full token set and base resets that `templates/` rely on.
- Root `package.json` (devDependencies) and `tailwind.config.js` define the build toolchain (`npx @tailwindcss/cli`) and the template sources scanned for utility classes.

Main Interfaces/Behaviors
- Running `npm run dev` (alias for `npx @tailwindcss/cli -i ./static/css/styles.css -o ./static/css/app.css --watch`) or the manual `tailwindcss` command rebuilds `app.css` whenever `styles.css` or referenced templates change.
- Templates served by FastAPI (under `templates/`) import `static/css/app.css`, so updates to the component classes in `styles.css` immediately change the UI once the build task is rerun.

Dependencies & Coupling
- Tailwind depends on the Node toolchain (`@tailwindcss/cli`, `tailwindcss`) declared in `package.json`; the output path is under `static/css/` so that the Docker images and scripts can copy it along with the rest of `static/`.
- The CSS files are bundled into Docker images (see `Dockerfile.server` etc.), so any naming changes would need to be mirrored in `templates/base.html` or whichever HTML imports the stylesheet.

Refactor Opportunities
- The build command could be encapsulated in a Makefile or shell script so CI/production builds do not rely on `npm` availability; this would also allow `uv` to manage Node dependencies in lockstep with Python ones.
- Consider breaking `styles.css` into multiple partials (buttons, cards, responsive sections) and importing them so the Tailwind compiler can be more selective and easier to maintain as the component library grows.

Reviewed files: 2
