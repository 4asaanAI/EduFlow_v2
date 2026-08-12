# Development Guide - Frontend

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

Set `DEV_API_TARGET=http://localhost:8000` to proxy `/api/*` through Vite. Without it,
the browser calls the backend URL configured below.

---

## Environment Variables

Create `frontend/.env.local`:

```bash
VITE_BACKEND_URL=http://localhost:8000
```

In production (Amplify), set:
```bash
VITE_BACKEND_URL=https://api.yourdomain.com
```

---

## Build

```bash
yarn build      # Produces frontend/build/
```

`yarn build` runs the hooks lint gate and Vite production build. AWS Amplify continues
to publish `frontend/build/`.

---

## Path Aliases

`@/` resolves to `frontend/src/`. Always use this for imports:

```js
// Correct
import { Button } from '@/components/ui/button'
import api from '@/lib/api'

// Wrong - fragile relative paths
import { Button } from '../../components/ui/button'
```

Defined in `vite.config.js`, `jest.config.js`, and `jsconfig.json`.

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
// For JSON endpoints - use native fetch()
export const myDomain = {
  list: async (token) => {
    const res = await fetch(`${API_BASE}/api/my-domain`, {
      headers: { Authorization: `Bearer ${token}` }
    })
    return res.json()
  },

  // File uploads only - use axios
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

**Do NOT upgrade** to date-fns v4 - it breaks `react-day-picker 8.x`.

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
| Files | `.js` / `.jsx` only - never `.ts` / `.tsx` |
| Imports | Use `@/` alias - never relative `../../` |
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

## Tables: lists, filters, downloads and scrolling (Release 3, 2026-08-12)

There are **two** table components and they are not interchangeable.

| | `components/ui/DataTable.js` | `components/tools/ToolPage.js` → `DataTable` |
|---|---|---|
| Rows | one server page at a time | the screen's COMPLETE result set |
| Sorting | **server-side** (`onSortChange` refetches from page 1) | client-side, which is correct here because it holds everything |
| Filtering | the SCREEN owns it and sends it to the server | built in, automatic |
| Used by | the long paginated lists | ~70 tool-screen tables |

If you find yourself adding `rows.sort(...)` inside `ui/DataTable`, the bug is upstream:
sorting the 20 rows on screen looks identical on a 20-row table and is a lie on a
1,876-row one.

### Every table has a download, and it must never be short

Screens on `ui/DataTable` pass `exportTable={{ title, getRows }}`. **`getRows` must return
every row matching the filters in force, not the page on screen.** Someone on page 3 of the
unpaid fees who presses Download means "the unpaid fees". Use `collectAllRows` from
`lib/exportTable.js`, which walks the pages and turns each way a walk can come back short
into a sentence a person can act on.

`ExportButton` compares what came back against the total the table is showing and
**refuses to save a short file**. That safety net is central rather than per screen, so
wiring a table wrongly fails loudly instead of producing a normal-looking file with
fifteen rows in it.

Tool-screen tables get the button automatically. Pass `exportable={false}` for a table
that is a control panel rather than a record, or `exportRows` to hand over plain values
where the cells are drawn (a `Badge`, a coloured amount) rather than written.

Columns support `exportValue` (different wording in the file), `exportLabel`, and
`exportSkip` (leave a column of action buttons out entirely - a column of empty cells
reads as missing data).

### Filters

Automatic on any tool-screen table with 8 rows or more: a search box that reads every
cell, plus a dropdown on each column whose values repeat enough to be worth choosing
between. Columns of names get no dropdown, because twenty names in a menu is worse than
typing. `filterable={false}` turns it off.

**Whatever filter you add to a screen, pass it into the download as well.** A file that
quietly holds the whole roll when the screen was filtered is the same fault as a short
file, in the other direction: it leaves the building under the wrong name.

The row count is always on screen ("Showing 24 of 1,876"), and a table filtered to nothing
says how many rows are hidden rather than "No data found", which reads as an empty school.

### "All" and scrolling

`fetchAllRows` (`lib/fetchAllRows.js`) walks every page. It **fails rather than returning
a short list**, and never sends the "All" sentinel (-1) as a page size: the server refuses
a size below 1 with a 400, and before Release 3 it coerced it to 1, so picking "All"
showed exactly one row.

`ui/DataTable` paints long lists in batches of 100 as you scroll. Every row is still
fetched and held; only the painting is spread out. The line under the table says how many
are **drawn** and how many are **loaded**, so a part-painted list can never be mistaken
for a short one, and there is a "Show more" button as well as the scroll in case the
scroll watcher never fires.

### Person-pickers must speak up

Never write `getAllStudents().then(r => { if (r.success) setStudents(r.data) })`. With no
`else`, a failed load leaves an empty picker, and on a school of 1,876 children an empty
picker reads as "there are no children" or "this is broken". Use `loadStudentsInto` and
render `<PeopleLoadNotice error={...} />` from `components/ui/PeopleLoadNotice.js`.

### Phone and tablet are the primary devices

- **Form fields must compute to at least 16px.** Safari force-zooms the page when a
  smaller field takes focus and never zooms back out, so one tap leaves the whole site
  magnified. The floors live in `index.css` §7 (≤768px) and §7c (touch, ≥769px) and use
  `!important`, because this codebase styles inline and only `!important` outranks an
  inline style. Do not "fix" a zoom with `maximum-scale=1` or `user-scalable=no`: that
  takes zoom away from people who need it to read.
- **Anything a thumb hits must be at least 40px tall.** Prefer fixing the shared helper
  (`ActionBtn`, `Btn`, `ActionButton`, `Button`) over the individual screen.
- A wide table scrolls **inside its own wrapper**. The page around it must never scroll
  sideways, or the right-hand edge is simply lost.
- Check your work with the real device projects, not a narrow desktop window:
  `npx playwright test --project=phone-pixel --project=tablet-ipad`.
