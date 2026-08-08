# EduFlow Frontend

React 19, Vite 6, Tailwind CSS v3, and plain JavaScript.

```bash
yarn install
VITE_BACKEND_URL=http://localhost:8000 yarn start
```

The dev server runs at `http://localhost:3000`. To proxy cookies and `/api` calls
through Vite instead, set `DEV_API_TARGET=http://localhost:8000`.

```bash
yarn test --runInBand
yarn build
```

The production build is written to `build/` for AWS Amplify. `yarn build` runs the
React hooks lint gate before bundling. The `@/` alias resolves to `src/` in Vite and
Jest. Use `.js` and `.jsx` only; this project does not use TypeScript.
