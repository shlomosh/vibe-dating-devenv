# Testing Guide

## Overview

Two layers of testing are set up for the frontend:

| Layer | Tool | Scope |
|---|---|---|
| Unit / Component | Vitest + React Testing Library | Logic, hooks, context, isolated components |
| End-to-End | Playwright | Full user flows in a real browser |

```
src/
  test/
    setup.ts                  # Global mocks and environment bootstrapping
    render.tsx                # renderWithProviders helper
    language-context.test.tsx # Example unit tests
e2e/
  splash.spec.ts              # Example E2E test
playwright.config.ts
vite.config.ts                # test block added
```

---

## Running Tests

```bash
# Unit tests — single pass (CI)
npm test

# Unit tests — watch mode (development)
npm run test:watch

# Unit tests — browser UI with coverage
npm run test:ui

# E2E tests — headless
npm run test:e2e

# E2E tests — interactive UI
npm run test:e2e:ui
```

> First-time E2E setup: run `npx playwright install` once to download browser binaries.

---

## Unit / Component Tests (Vitest + RTL)

### Configuration

Vitest runs inside Vite's pipeline, so it shares `vite.config.ts` automatically — path aliases (`@/`), env variables, and plugins all work without extra setup.

Key settings in `vite.config.ts`:

```ts
test: {
  globals: true,          // describe / it / expect available without imports
  environment: 'jsdom',   // DOM APIs
  setupFiles: ['./src/test/setup.ts'],
  css: true,              // process CSS imports (e.g. mapbox-gl/dist/mapbox-gl.css)
  include: ['src/**/*.test.{ts,tsx}'],
}
```

### Global Mocks (`src/test/setup.ts`)

Three categories of globals are mocked so tests run outside the Telegram environment:

**`@telegram-apps/sdk-react`** — the app depends on Telegram initData, openLink, and viewport insets. All are replaced with inert stubs:

```ts
vi.mock('@telegram-apps/sdk-react', () => ({
  initData: { user: () => null },
  openLink: vi.fn(),
  viewportSafeAreaInsets: { top: 0, bottom: 0, left: 0, right: 0 },
  useSignal: (val) => val,
}));
```

**`mapbox-gl`** — Mapbox initialises a WebGL canvas which jsdom cannot render. The Map and Marker constructors are replaced with vi.fn() stubs:

```ts
vi.mock('mapbox-gl', () => ({
  default: {
    Map: vi.fn(() => ({ on: vi.fn(), remove: vi.fn(), addControl: vi.fn(), flyTo: vi.fn() })),
    Marker: vi.fn(() => ({ setLngLat: vi.fn().mockReturnThis(), addTo: vi.fn().mockReturnThis(), remove: vi.fn() })),
    NavigationControl: vi.fn(),
    accessToken: '',
  },
}));
```

**`ResizeObserver`** — not available in jsdom, added as a no-op class.

### `renderWithProviders` (`src/test/render.tsx`)

All components that use contexts (language, theme, routing, data fetching) need their provider tree. Use `renderWithProviders` instead of plain `render`:

```tsx
import { renderWithProviders, screen } from '@/test/render';

it('renders the button', () => {
  renderWithProviders(<MyComponent />);
  expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
});
```

The wrapper provides:
- `QueryClientProvider` (retries disabled to avoid hanging tests)
- `AppProvider`
- `LanguageProvider`
- `MemoryRouter`

To test a component that depends on the current route:

```tsx
renderWithProviders(<ProfileNavigationBar />, { route: '/profile' });
```

### Testing Hooks

Use `renderHook` from `@testing-library/react`. Async context initialisation (e.g. loading from localStorage) needs `waitFor`:

```tsx
import { renderHook, act, waitFor } from '@testing-library/react';
import { LanguageProvider, useLanguage } from '@/contexts/LanguageContext';

it('persists language to localStorage', async () => {
  const { result } = renderHook(() => useLanguage(), {
    wrapper: ({ children }) => <LanguageProvider>{children}</LanguageProvider>,
  });

  // Wait for async init (localStorage load)
  await waitFor(() => expect(result.current.translations).toBeDefined());

  act(() => { result.current.setLanguage('he-IL' as Language); });

  await waitFor(() =>
    expect(JSON.parse(localStorage.getItem('vibe/config/v1/language')!)).toBe('he-IL')
  );
});
```

> **Note:** `LocalStorage` util JSON-serialises values. Always `JSON.parse` when reading raw `localStorage` in assertions.

### What to Unit Test

| ✅ Good candidates | ❌ Skip |
|---|---|
| Context logic (`LanguageContext`, `AppContext`) | Components that are pure Tailwind wrappers |
| Custom hooks (`useChatPage`, `useInfiniteScroll`) | Third-party component behaviour |
| `NavigationBar` item order based on `dominantHand` | Pixel-perfect styling |
| Dialog open/close and form submission | Anything covered by E2E |
| Locale key persistence and retrieval | |
| Utility functions (`formatDistance`, `isSingleEmojiOnly`) | |

### File Placement

Co-locate test files with the source they test:

```
src/
  contexts/
    LanguageContext.tsx
    LanguageContext.test.tsx   ← co-located
  utils/
    location.ts
    location.test.ts           ← co-located
```

Shared test utilities stay in `src/test/`.

---

## End-to-End Tests (Playwright)

### Configuration (`playwright.config.ts`)

- Base URL: `http://localhost:5173` (Vite dev server, auto-started via `webServer`)
- Default viewport: `390×844` (iPhone 14) — matches the Telegram Mini-App context
- Projects: `chromium` (desktop) and `mobile-chrome` (Pixel 5)
- Traces captured on first retry for debugging

### Writing E2E Tests

E2E tests live in `e2e/` and target real browser behaviour. Prefer role-based selectors to keep tests resilient to UI changes:

```ts
import { test, expect } from '@playwright/test';

test.describe('Splash page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('shows accept terms button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /accept terms/i })).toBeVisible();
  });

  test('language dialog opens from nav bar', async ({ page }) => {
    await page.locator('#content-navigation').getByRole('button').last().click();
    await expect(page.getByRole('dialog')).toBeVisible();
  });
});
```

### What to E2E Test

| ✅ Good candidates | ❌ Skip |
|---|---|
| Login / accept terms flow | Internals already covered by unit tests |
| Language + dominant hand persistence across reload | Implementation details |
| Navigation bar routing | Third-party SDK behaviour |
| Chat: send message → bubble appears | |
| Feed: pull-to-refresh updates the list | |
| Dialog open/close triggered from the UI | |

### Mocking the Telegram SDK in E2E

The app reads `window.Telegram.WebApp` on startup. Inject it via `page.addInitScript` in a `beforeEach`:

```ts
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    (window as any).Telegram = {
      WebApp: {
        initData: '',
        initDataUnsafe: { user: { id: 1, language_code: 'en' } },
        ready: () => {},
        expand: () => {},
        close: () => {},
        MainButton: { show: () => {}, hide: () => {} },
      },
    };
  });
  await page.goto('/');
});
```

---

## Environment Variables in Tests

Vitest exposes `import.meta.env.*` from `.env` files. For tests that touch Mapbox (even mocked), define a placeholder in `.env.test`:

```
VITE_MAPBOX_ACCESS_TOKEN=test-token
```

Create `.env.test` at the project root — Vitest picks it up automatically.

---

## CI Integration

Add to your CI pipeline:

```yaml
- name: Unit tests
  run: npm test

- name: Install Playwright browsers
  run: npx playwright install --with-deps chromium

- name: E2E tests
  run: npm run test:e2e
  env:
    VITE_MAPBOX_ACCESS_TOKEN: ${{ secrets.MAPBOX_TOKEN }}
```
