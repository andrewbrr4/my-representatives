# Frontend ELI5 — A Python Developer's Guide

This doc explains the frontend stack in terms a Python backend developer already understands.

---

## The Big Picture

| Frontend concept | Python equivalent |
|-----------------|-------------------|
| Node.js | The Python interpreter — runs JavaScript outside the browser |
| npm | pip — installs packages |
| `package.json` | `requirements.txt` + `pyproject.toml` combined |
| `node_modules/` | Your virtualenv's `site-packages/` |
| npx | `pipx` — runs a package's CLI without installing globally |
| Vite | uvicorn — a dev server that serves your app with hot reload |
| `npm run dev` | `uvicorn main:app --reload` |
| `npm run build` | Compiles everything into static files (no equivalent in Python since Python isn't compiled) |

---

## React in 60 Seconds

React is a library for building UIs out of **components**. A component is just a function that returns HTML-like syntax (called JSX).

```tsx
// This is a component. It's just a function.
function Greeting({ name }: { name: string }) {
  return <h1>Hello, {name}!</h1>;
}

// You use it like an HTML tag:
<Greeting name="Andrew" />
```

**Props** = function arguments. The parent passes data down to children.

**State** = mutable data that lives inside a component. When state changes, React re-renders the component.

```tsx
function Counter() {
  // useState returns [currentValue, setterFunction]
  const [count, setCount] = useState(0);

  return (
    <button onClick={() => setCount(count + 1)}>
      Clicked {count} times
    </button>
  );
}
```

**Hooks** (functions starting with `use`) = reusable chunks of state + logic. Our `useRepresentatives()` hook manages the loading/error/data state for the API call. Think of it like a service class that also manages its own state.

---

## TypeScript in 30 Seconds

TypeScript = JavaScript + type hints. It's like Python with type annotations, but **enforced at build time**.

```typescript
// This is basically a Pydantic model
interface Representative {
  name: string;
  office: string;
  party: string | null;  // Same as Optional[str] in Python
}
```

The `tsconfig.json` files configure the TypeScript compiler — what syntax to allow, where to find files, etc.

---

## Tailwind CSS

Instead of writing CSS in separate files like:

```css
/* styles.css */
.my-card {
  background: white;
  padding: 16px;
  border-radius: 8px;
}
```

You put utility classes directly on elements:

```html
<div class="bg-white p-4 rounded-lg">...</div>
```

Common patterns:
- `p-4` = padding (4 units = 16px)
- `m-2` = margin
- `flex` = flexbox layout
- `gap-3` = space between flex children
- `text-sm` = small text
- `bg-blue-600` = blue background
- `w-full` = width: 100%
- `md:grid-cols-2` = 2 columns on medium+ screens (responsive)

---

## shadcn/ui

Most UI libraries are npm packages you install and import. shadcn is different — it **copies actual component files into your project**.

When you run `npx shadcn add button`, it creates `src/components/ui/button.tsx` — a real file you own and can edit. This means:
- Full control over the component code
- No fighting with library CSS overrides
- You can read and understand exactly what each component does

The components use Tailwind for styling and a utility called `cn()` (from `src/lib/utils.ts`) to merge CSS classes.

---

## Project Structure Explained

```
frontend/
├── public/              # Static files served as-is (favicon, etc.)
├── src/
│   ├── components/
│   │   ├── ui/          # shadcn components (Button, Card, etc.) — don't edit often
│   │   ├── AddressSearch.tsx   # Our search form component
│   │   ├── RepCard.tsx         # Card showing one representative
│   │   └── SkeletonCard.tsx    # Loading placeholder card
│   ├── hooks/
│   │   └── useRepresentatives.ts  # API call logic + state management
│   ├── types/
│   │   └── index.ts       # TypeScript interfaces (like Pydantic models)
│   ├── lib/
│   │   └── utils.ts       # cn() utility from shadcn
│   ├── App.tsx            # Main app component — the "page"
│   ├── main.tsx           # Entry point — mounts React into the HTML page
│   └── index.css          # Tailwind imports + shadcn theme variables
├── index.html             # The single HTML page React mounts into
├── package.json           # Dependencies and scripts
├── vite.config.ts         # Vite configuration
├── tsconfig.json          # TypeScript configuration
└── components.json        # shadcn configuration
```

---

## How Data Flows

```
User types address
    ↓
AddressSearch component calls onSearch(address)
    ↓
App component calls lookup(address) from useRepresentatives hook
    ↓
Hook does fetch("http://localhost:8000/api/representatives", { body: { address } })
    ↓
Sets loading=true → React re-renders → skeleton cards appear
    ↓
Response arrives → sets representatives array → React re-renders → real cards appear
```

This is basically the same as calling your FastAPI endpoint from `requests`, but React automatically updates the UI when the data changes.

---

## Running It

```bash
cd frontend
npm install    # pip install -r requirements.txt
npm run dev    # uvicorn main:app --reload
```

Then open http://localhost:5173 in your browser.
