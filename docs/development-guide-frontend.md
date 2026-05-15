# Development Guide — Frontend

_Generated: 2026-05-15 | Scan: deep | Part: frontend_

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Node.js | 18+ | LTS recommended |
| Yarn | 1.x | `npm install -g yarn` |
| Backend | Running on :8000 | Required for API calls |

---

## Setup

```bash
cd frontend
yarn install
yarn start      # Dev server on http://localhost:3000
```

The dev server proxies `/api/*` to `http://localhost:8000` (configured in `craco.config.js`).

---

## Environment Variables

Create `frontend/.env.local`:

```bash
REACT_APP_API_URL=http://localhost:8000
```

In production (Amplify), set:
```bash
REACT_APP_API_URL=https://api.yourdomain.com
```

---

## Build

```bash
yarn build      # Produces frontend/build/
```

**Important:** Use `craco build` (via the `yarn build` script) — NOT `react-scripts build` directly. CRACO applies path alias resolution (`@/` → `src/`).

---

## Path Aliases

`@/` resolves to `frontend/src/`. Always use this for imports:

```js
// Correct
import { Button } from '@/components/ui/button'
import api from '@/lib/api'

// Wrong — fragile relative paths
import { Button } from '../../components/ui/button'
```

Defined in `craco.config.js` + `jsconfig.json`.

---

## Adding a New Tool Panel

1. Create `frontend/src/components/tools/MyNewTool.js`:

```jsx
import { useState, useContext } from 'react'
import { UserContext } from '@/contexts/UserContext'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'

export default function MyNewTool() {
  const { user, token } = useContext(UserContext)
  const [data, setData] = useState([])

  const load = async () => {
    const res = await api.myDomain.list(token)
    setData(res.items)
  }

  return (
    <div>
      <Button onClick={load}>Load</Button>
      {/* render data */}
    </div>
  )
}
```

2. Register in `ToolPage.js` (route → component map).

3. Add to `Sidebar.js` for the appropriate roles.

---

## Adding API Calls

Add to `frontend/src/lib/api.js`:

```js
// For JSON endpoints — use native fetch()
export const myDomain = {
  list: async (token) => {
    const res = await fetch(`${API_BASE}/api/my-domain`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return res.json()
  },

  // File uploads only — use axios
  upload: async (token, file) => {
    const form = new FormData()
    form.append('file', file)
    const res = await axios.post(`${API_BASE}/api/uploads`, form, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return res.data
  }
}
```

---

## Using shadcn/ui Components

All Radix UI components are already installed. Import from `@/components/ui/`:

```jsx
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
```

Do NOT install new UI libraries. Check `frontend/src/components/ui/` first.

---

## Icon Usage

Only **Lucide React** is the approved icon library:

```jsx
import { Users, BookOpen, ChevronRight } from 'lucide-react'
```

Never import from heroicons, react-icons, or any other icon set.

---

## Toast Notifications

Use the sonner toast system:

```jsx
import { toast } from 'sonner'

// In your handler:
toast.success('Student enrolled successfully')
toast.error('Failed to load data')
toast.loading('Processing...')
```

---

## Date Handling

Use **date-fns v3** (pinned):

```js
import { format, parseISO, differenceInDays } from 'date-fns'

format(new Date(), 'yyyy-MM-dd')
parseISO('2026-01-15')
```

**Do NOT upgrade** to date-fns v4 — it breaks `react-day-picker 8.x`.

---

## Forms

Use **React Hook Form + Zod**:

```jsx
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Form, FormField, FormItem, FormLabel, FormControl, FormMessage } from '@/components/ui/form'

const schema = z.object({
  name: z.string().min(2),
  email: z.string().email(),
})

function MyForm() {
  const form = useForm({ resolver: zodResolver(schema) })

  const onSubmit = async (data) => { /* ... */ }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)}>
        <FormField
          control={form.control}
          name="name"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Name</FormLabel>
              <FormControl><Input {...field} /></FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
      </form>
    </Form>
  )
}
```

---

## Code Conventions

| Convention | Rule |
|-----------|------|
| Files | `.js` / `.jsx` only — never `.ts` / `.tsx` |
| Imports | Use `@/` alias — never relative `../../` |
| HTTP | `fetch()` for all endpoints; `axios` for file uploads only |
| Icons | Lucide React only |
| Styling | Tailwind v3 utility classes; do not write custom CSS except for `App.css`/`index.css`/`theme.css` |
| State | `useState`/`useReducer` locally; `useContext` for global (UserContext, ThemeContext) |
| Auth | Read `user` and `token` from `useContext(UserContext)` |
| No TypeScript | No type annotations, no `tsc`, no `@types/*` packages |

---

## Testing

E2E tests use Playwright:

```bash
# From repo root
npx playwright test
```

Config: `playwright.config.js` at repo root.
