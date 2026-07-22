---
name: ui-ux-pro-max
description: "Complete UI/UX design suite for building beautiful, accessible digital products. Handles: brand identity & voice, logo design (55+ AI-generated styles), corporate identity programs (50+ deliverables with mockups), responsive UI components (shadcn/ui + Tailwind CSS), design systems with semantic tokens, presentations & pitch decks (HTML with Chart.js), banner design (22 styles for social/ads/web/print), icon generation (15 SVG styles), and social media visuals (Instagram, Facebook, LinkedIn, Twitter, YouTube, Pinterest, TikTok, Google Ads). Use this whenever the user mentions design, branding, logo, UI, layout, presentation, website styling, social media graphics, design system, component library, or wants to create any visual digital asset. Auto-triggers on design-related requests—don't wait for explicit skill mention."
compatibility: "Requires: Python 3.8+, Gemini API key (for logo/CIP/icon generation). Optional: Chrome DevTools (for banner export)."
metadata:
  author: claudekit
  version: "1.0.0"
  license: MIT
---

# UI/UX Pro Max — Complete Design Suite

Unified, AI-powered design skill for brand, components, visual systems, and multimedia assets. Build beautiful, accessible digital products end-to-end.

## When to Use This Skill

**Auto-triggers on:**
- Brand identity, logos, visual style, color palettes, typography
- UI components, responsive layouts, accessibility patterns
- Design systems, tokens, specifications, component libraries
- Website/app styling with Tailwind CSS or shadcn/ui
- Presentations, pitch decks, data visualization slides
- Banners, social media graphics, promotional images
- Corporate identity programs (business cards, letterhead, etc.)
- Icon design, illustration, SVG generation
- Web design, landing pages, page layouts

**Also use when:**
- Starting a new design project and need system from scratch
- Building a design-to-code workflow
- Creating marketing collateral or brand assets
- Preparing presentations with visual design
- Establishing consistent styling across product
- Need AI-generated design variations to choose from

---

## Core Capabilities (5 Domains)

### 1. Brand & Identity System
- Brand guidelines, tone of voice, messaging frameworks
- Logo design with 55+ AI-generated styles (Gemini)
- Color psychology, palette creation, contrast validation
- Typography systems, font pairing
- Brand voice profiles, founder messaging, visual identity
- Asset organization and brand compliance checklists

**When to start here:** New company, rebrand, inconsistent brand presence, need brand guidelines

**Key outputs:**
- Brand guidelines document
- Logo variations (multiple styles)
- Color palette with hex codes
- Typography specs
- Voice & messaging framework
- Asset library

---

### 2. Design System & Tokens
- Semantic token architecture (primitive → component → semantic layers)
- Design token generation (colors, spacing, typography, shadows, radii)
- Component specifications and token mappings
- State and variant definitions
- Tailwind CSS integration
- Token validation and consistency checks
- Multi-brand token systems

**When to use:** Building scalable product, need consistency layer, establishing design foundations

**Key outputs:**
- `design-tokens.json` (semantic layer)
- Component token specs
- Tailwind config with custom tokens
- Token documentation
- Token validation reports

---

### 3. UI Components & Styling
- **shadcn/ui**: 50+ accessible, pre-built components (Radix UI + Tailwind)
  - Forms, dialogs, tables, data visualization, navigation, overlays
  - Full TypeScript support, copy-paste distribution model
- **Tailwind CSS**: Utility-first styling (responsive, dark mode, custom)
- **Accessibility-first**: ARIA patterns, keyboard navigation, screen reader support
- **Canvas-based visual design**: Museum-quality compositions, minimal text
- **Dark mode implementation**: CSS variables, theme toggle, comprehensive coverage
- **Responsive patterns**: Mobile-first, all breakpoints (sm/md/lg/xl/2xl)

**When to use:** Building web apps, need accessible components, want rapid prototyping, need dark mode

**Quick setup:**
```bash
npx shadcn@latest init
npx shadcn@latest add button card dialog form
```

**Key outputs:**
- React components with full styling
- Responsive layouts
- Accessible patterns
- Theme customization
- Dark mode support

---

### 4. AI-Generated Design Assets

#### Logo Design (55+ Styles)
- Minimalist, modern, vintage, geometric, luxury, playful, tech, organic styles
- 30+ color palettes, 25+ industry guides
- Design brief generation with industry context
- Generated as high-quality images (white background)
- Perfect for startups, rebrandsExecution:
```bash
python ~/.claude/skills/ui-ux-pro-max/scripts/logo/search.py "tech startup modern" --design-brief
python ~/.claude/skills/ui-ux-pro-max/scripts/logo/generate.py --brand "TechFlow" --style minimalist --industry tech
```

#### Corporate Identity Program (50+ Deliverables)
- Business cards, letterhead, envelopes, folders, packaging, signage
- 20+ style variations, 20+ industry templates
- Mockup generation with brand context
- HTML presentation rendering
- Full brand ecosystem in one system

```bash
python ~/.claude/skills/ui-ux-pro-max/scripts/cip/search.py "tech startup" --cip-brief
python ~/.claude/skills/ui-ux-pro-max/scripts/cip/generate.py --brand "TopGroup" --logo /path/to/logo.png --set
```

#### Icon Design (15 SVG Styles)
- Outlined, filled, duotone, rounded, sharp, flat, gradient
- Multi-size export (16, 24, 32, 48, 64px)
- Batch generation for icon sets
- Pure SVG output (no image generation needed)

```bash
python ~/.claude/skills/ui-ux-pro-max/scripts/icon/generate.py --prompt "settings gear" --style outlined
python ~/.claude/skills/ui-ux-pro-max/scripts/icon/generate.py --prompt "cloud upload" --batch 4
```

---

### 5. Marketing & Presentation Assets

#### Banner Design (22 Art Styles)
- Social media (Facebook, Twitter, Instagram, LinkedIn, Pinterest, TikTok)
- Ads (Google Ads, display networks)
- Web (hero banners, header images)
- Print (300 DPI, CMYK, bleed)
- Styles: minimalist, bold typography, gradient, photo-based, geometric, glassmorphism, neon/cyberpunk
- Exact dimensions for all platforms
- Safe zone and text sizing guidelines

**Common sizes:**
| Platform | Dimension | Type |
|----------|-----------|------|
| Instagram Post | 1080×1080 | Feed |
| Instagram Story | 1080×1920 | Story |
| Facebook Cover | 820×312 | Timeline |
| Twitter/X Header | 1500×500 | Banner |
| LinkedIn | 1584×396 | Banner |
| YouTube Channel | 2560×1440 | Art |
| Google Ads | 300×250 | Rectangle |
| Website Hero | 1920×600-1080 | Full-width |

#### Presentations & Pitch Decks
- HTML-based with Chart.js integration
- Data visualization with charts, graphs, tables
- Layout patterns: 2-column, hero + sidebar, full-width sections, card grids
- Copywriting formulas for compelling narrative
- Strategic slide frameworks
- Color-coded sections, typography hierarchy
- Responsive design, presenter notes

**Key patterns:**
- Title slide with context
- Problem statement (1-2 slides)
- Solution overview (1-2 slides)
- Key benefits (1-3 slides)
- Data/proof points with charts
- Call to action
- Q&A / Contact slide

#### Social Media Visuals
- Multi-platform templates (Instagram, Facebook, LinkedIn, Twitter, YouTube, Pinterest, TikTok)
- HTML/CSS → screenshot export workflow
- Consistent branding across platforms
- Content-specific layouts (quotes, announcements, case studies, testimonials)
- Optimal sizing and safe zones
- Color psychology and visual hierarchy

---

## Quick Start Workflows

### 🎨 Brand New Project
1. **Define brand** → colors, typography, voice, personality
2. **Create logo** → search styles → generate variants
3. **Build CIP** → add logo → generate deliverables
4. **Design system** → tokens → components → implementation
5. **Launch marketing** → banners + social content

### 🏢 Corporate Identity Program (CIP)
1. Start with logo (existing or generate)
2. Define industry + style preference
3. Generate full CIP set (50+ items)
4. Review mockups
5. Export as HTML presentation for client review

### 💻 Product Design System
1. Define brand colors, typography
2. Generate semantic tokens
3. Set up Tailwind config
4. Install shadcn/ui components
5. Build responsive layouts
6. Implement dark mode
7. Add accessibility patterns

### 📊 Presentation Deck
1. Outline key messages (problem → solution → benefit → ask)
2. Choose layout patterns
3. Create slides with charts/data
4. Apply brand colors and typography
5. Add presenter notes
6. Export to HTML or PDF

### 📱 Social Media Campaign
1. Define platforms + content pillars
2. Create content templates per platform
3. Design 3-5 variations per asset
4. Export at exact dimensions
5. Organize by platform + content type

---

## Component Library (shadcn/ui)

### Form & Input
- Button (variants: default, secondary, ghost, outline, destructive)
- Input (text, email, password, number)
- Select (dropdown, multi-select)
- Checkbox & Radio
- Switch, Toggle, Toggle Group
- Date Picker (calendar-based)
- Form validation with React Hook Form + Zod

### Layout & Navigation
- Card (container with header, title, content, footer)
- Tabs (vertical/horizontal, keyboard navigation)
- Accordion (collapsible sections)
- Navigation Menu (mega menu patterns)
- Breadcrumbs, Pagination
- Sidebar, Sheet (off-canvas)

### Overlays & Dialogs
- Dialog (modal, form submission, confirmation)
- Drawer (slide-out panel)
- Popover (floating menu)
- Toast (notifications)
- Command Palette (keyboard-driven search)

### Feedback & Status
- Alert (info, success, warning, error)
- Progress (linear, circular, indeterminate)
- Skeleton (loading placeholders)
- Badge, Label, Hint text

### Display
- Table (data table with sorting, filtering, pagination)
- Avatar (user images, fallbacks)
- Badge, Label
- Tooltip
- Carousel, Slider
- Code block with syntax highlighting

---

## Design System Foundation

### Token Architecture (3 Layers)

**Layer 1: Primitive Tokens**
```json
{
  "color-neutral-50": "#fafafa",
  "color-neutral-900": "#0a0a0a",
  "space-4": "1rem",
  "font-size-base": "1rem"
}
```

**Layer 2: Component Tokens**
```json
{
  "button-background": "color-neutral-900",
  "button-text": "color-neutral-50",
  "input-border": "color-neutral-200",
  "input-focus": "color-blue-500"
}
```

**Layer 3: Semantic Tokens**
```json
{
  "background-primary": "color-neutral-50",
  "background-secondary": "color-neutral-100",
  "text-primary": "color-neutral-900",
  "border-default": "color-neutral-200"
}
```

### Tailwind CSS Integration
- Custom colors from design tokens
- Custom spacing scale
- Custom typography scales
- Custom shadows and borders
- Custom breakpoints
- Dark mode CSS variables
- Layer organization (@layer base, components, utilities)
- Custom utility functions

---

## Accessibility Patterns

### Keyboard Navigation
- Tab through all interactive elements
- Escape to close dialogs/popovers
- Arrow keys for menus and tabs
- Enter/Space for activation

### Screen Reader Support
- Semantic HTML (button, nav, main, etc.)
- ARIA labels for icon-only buttons
- ARIA live regions for dynamic content
- Form labels linked to inputs
- Table headers marked correctly

### Visual Accessibility
- ≥4.5:1 contrast ratio (normal text)
- ≥3:1 contrast ratio (large text)
- Focus indicators visible (2px outline)
- Color not sole information carrier
- Readable font sizes (≥16px base)

### Radix UI Primitives
- Built-in ARIA attributes
- Focus management
- Keyboard event handling
- Dismissible patterns (outside clicks)

---

## AI-Powered Workflow

### Logo Generation
```bash
# Search existing styles
python scripts/logo/search.py "minimalist tech" --domain style

# Generate new logo
python scripts/logo/generate.py --brand "MyBrand" --style minimalist --industry tech --output ./logo.png
```

### CIP Mockups
```bash
# Generate with logo
python scripts/cip/generate.py \
  --brand "TopGroup" \
  --logo ./logo.png \
  --industry consulting \
  --set

# Render HTML presentation
python scripts/cip/render-html.py \
  --brand "TopGroup" \
  --industry consulting \
  --images ./cip-output
```

### Icon Generation
```bash
# Single icon
python scripts/icon/generate.py --prompt "settings gear" --style outlined

# Batch with multiple sizes
python scripts/icon/generate.py --prompt "cloud upload" --batch 4 --sizes "24,32,48"
```

---

## Best Practices

### Brand Consistency
1. Define core brand attributes (personality, values, visual language)
2. Create comprehensive brand guidelines document
3. Establish approved color palettes and typography
4. Build reusable component library
5. Create style guide for all deliverable types
6. Version control all brand assets
7. Regular brand audits (quarterly)

### Design System Maturity
- **Level 1**: Ad-hoc designs, no system → Create token foundation
- **Level 2**: Token foundation → Document component specs
- **Level 3**: Component specs → Build Storybook/component catalog
- **Level 4**: Component catalog → Establish governance + update process
- **Level 5**: Governance + process → Cross-product system adoption

### UI Implementation
1. Mobile-first responsive design (start with sm breakpoint)
2. Accessibility first (semantic HTML, ARIA, contrast)
3. Dark mode from day one (use CSS variables)
4. Component composition over utility classes
5. TypeScript for type safety
6. Performance: lazy loading, code splitting, tree-shaking
7. Testing: unit tests for logic, visual regression for styles

### Content Design for Marketing
1. One primary message per asset
2. Visual hierarchy guides attention
3. Max 20% text on ads (Meta penalizes)
4. Clear CTA, bottom-right positioning
5. Optimal sizing for platform (safe zones)
6. A/B test color + copy combinations
7. Track engagement metrics per platform

---

## Setup & Configuration

### Requirements
```bash
# Node.js (for shadcn/ui)
node --version  # v18+

# Python (for AI generation)
python --version  # 3.8+

# Gemini API key
export GEMINI_API_KEY="your-key-from-aistudio.google.com"

# Install dependencies
pip install google-genai pillow
```

### Tailwind + shadcn/ui Setup
```bash
# For Next.js
npx create-next-app@latest my-app
cd my-app
npx shadcn@latest init

# For Vite
npm create vite@latest my-app -- --template react
cd my-app
npm install -D tailwindcss @tailwindcss/vite
npx shadcn@latest init
```

### Design Token Setup
```bash
# Generate initial tokens
python scripts/design-system/generate-tokens.py \
  --colors brand:#2563eb,success:#10b981 \
  --spacing 4,8,12,16,24,32 \
  --output tailwind.config.js
```

---

## Common Patterns

### Responsive Grid Layout
```tsx
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {items.map(item => (
    <Card key={item.id}>
      <CardHeader>
        <CardTitle>{item.title}</CardTitle>
      </CardHeader>
      <CardContent>{item.description}</CardContent>
    </Card>
  ))}
</div>
```

### Form with Validation
```tsx
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"

const schema = z.object({
  email: z.string().email("Invalid email"),
  password: z.string().min(8, "Min 8 characters")
})

export function LoginForm() {
  const form = useForm({ resolver: zodResolver(schema) })
  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        <FormField control={form.control} name="email" render={({ field }) => (
          <FormItem>
            <FormLabel>Email</FormLabel>
            <FormControl><Input {...field} /></FormControl>
            <FormMessage />
          </FormItem>
        )} />
        <Button type="submit">Sign In</Button>
      </form>
    </Form>
  )
}
```

### Dark Mode Implementation
```tsx
import { useTheme } from "next-themes"

export function Header() {
  const { theme, setTheme } = useTheme()

  return (
    <header className="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
      <button onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
        Toggle Dark Mode
      </button>
    </header>
  )
}
```

### Accessible Data Table
```tsx
<Table>
  <TableHeader>
    <TableRow>
      <TableHead className="w-[100px]">ID</TableHead>
      <TableHead>Name</TableHead>
      <TableHead className="text-right">Amount</TableHead>
    </TableRow>
  </TableHeader>
  <TableBody>
    {data.map(row => (
      <TableRow key={row.id}>
        <TableCell>{row.id}</TableCell>
        <TableCell>{row.name}</TableCell>
        <TableCell className="text-right">{row.amount}</TableCell>
      </TableRow>
    ))}
  </TableBody>
</Table>
```

---

## Resources & References

### Documentation
- **shadcn/ui**: https://ui.shadcn.com
- **Tailwind CSS**: https://tailwindcss.com/docs
- **Radix UI**: https://radix-ui.com
- **next-themes**: Dark mode for Next.js
- **React Hook Form**: Form state management
- **Zod**: Schema validation

### Design Tools
- **Figma**: Collaborative design
- **Storybook**: Component showcase
- **v0.dev**: AI-powered UI generator
- **Tailwind UI**: Component templates
- **Headless UI**: Unstyled accessible components

### AI Generation
- **Gemini API**: Logo, CIP, icon generation
- **Anthropic Claude**: Design systems, copy, strategy
- **Replicate**: Image generation alternatives
- **OpenAI DALL-E**: Visual ideation

### Accessibility
- **WCAG 2.1 AA**: Web accessibility guidelines
- **WebAIM**: Accessibility resources
- **Axe DevTools**: Automated accessibility testing
- **NVDA**: Free screen reader

---

## Workflow Summary

```
User Request (design-related)
    ↓
Determine Domain (brand/tokens/UI/AI assets/marketing)
    ↓
Execute Domain Workflow
    ├─ Brand → Guidelines → Voice → Colors
    ├─ Tokens → Primitive → Component → Semantic
    ├─ UI → Components → Layouts → Dark Mode
    ├─ AI Assets → Logo/CIP/Icon Search → Generate
    └─ Marketing → Banner/Slides/Social (by platform)
    ↓
Output Deliverables (files, code, specs)
    ↓
Iterate Based on Feedback
```

---

## Notes for Internal Team & Clients

**For Layaa AI Team:**
- Use this skill for all client deliverables (logos, CIPs, design systems)
- Leverage AI generation (Gemini) to create variations quickly
- Document all design decisions in brand guidelines
- Version control all assets and tokens
- Cross-check brand consistency before client handoff

**For Client Delivery:**
- Start with brand discovery → logo → CIP → design system
- Provide branded asset library for client's internal use
- Train clients on brand usage guidelines
- Create living documentation (component library, token specs)
- Set up governance process for brand consistency
- Schedule quarterly brand audits
- Offer retainers for ongoing support and asset creation

---

*Last updated: March 2026 | UI/UX Pro Max v1.0*
