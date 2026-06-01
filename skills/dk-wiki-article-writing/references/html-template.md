# HTML Template Reference

Self-contained Wikipedia-style HTML page. All CSS inline, zero external dependencies.

## Minimal Structure

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{ARTICLE_TITLE} — Wikipedia-style Article</title>
<style>
/* CSS goes here — see variables below */
</style>
</head>
<body>
  <div class="page">
    <nav class="toc">...</nav>
    <main class="content">
      <h1>{TITLE}</h1>
      <!-- article body with <sup>[N]</sup> citations -->
    </main>
  </div>
</body>
</html>
```

## CSS Variables (Light + Dark Mode)

```css
:root {
  --bg: #f8f9fa;
  --bg-content: #ffffff;
  --bg-toc: #f8f9fa;
  --bg-table-alt: #f2f4f7;
  --bg-table-header: #e8ecf0;
  --border: #c8ccd1;
  --text: #202122;
  --text-secondary: #54595d;
  --link: #0645ad;
  --link-visited: #0b0080;
  --accent: #36c;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a2e;
    --bg-content: #16213e;
    --bg-toc: #1a1a2e;
    --bg-table-alt: #1c2541;
    --bg-table-header: #243154;
    --border: #3a4a6b;
    --text: #e0e0e0;
    --text-secondary: #b0b8c4;
    --link: #6ea8fe;
    --link-visited: #a78bfa;
    --accent: #6ea8fe;
  }
}
```

## Key CSS Rules

```css
body {
  font-family: 'Linux Libertine', Georgia, 'Times New Roman', serif;
  line-height: 1.6;
  color: var(--text);
  background: var(--bg);
}

h1, h2, h3, h4 {
  font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
  border-bottom: 1px solid var(--border);
  padding-bottom: 0.25em;
}

.page {
  max-width: 960px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: 220px 1fr;
  gap: 2rem;
}

/* Citation superscripts */
sup {
  background: var(--accent-bg, #eaf3ff);
  padding: 0 3px;
  border-radius: 2px;
  font-size: 0.75em;
}
sup a { text-decoration: none; color: var(--accent); }

/* Comparison table */
table {
  width: 100%;
  border-collapse: collapse;
  margin: 1em 0;
}
th {
  background: var(--bg-table-header);
  text-align: left;
  padding: 8px 12px;
  border: 1px solid var(--border);
}
td {
  padding: 8px 12px;
  border: 1px solid var(--border);
}
tr:nth-child(even) { background: var(--bg-table-alt); }

/* Responsive */
@media (max-width: 960px) {
  .page { grid-template-columns: 1fr; }
  .toc { display: none; } /* or collapsible */
}
@media (max-width: 600px) {
  body { font-size: 0.95em; }
  .page { padding: 0 1rem; }
}

/* Print */
@media print {
  .toc { display: none; }
  body { background: #fff; color: #000; }
  a[href]::after { content: " (" attr(href) ")"; font-size: 0.8em; }
}
```

## Workflow Steps Styling

```html
<ol class="workflow">
  <li>
    <span class="step-num">1</span>
    <div class="step-content">
      <strong>Step title</strong>
      <p>Description...</p>
    </div>
  </li>
</ol>
```

```css
.workflow {
  counter-reset: step;
  list-style: none;
  padding: 0;
}
.workflow li {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  align-items: flex-start;
}
.step-num {
  flex-shrink: 0;
  width: 2em;
  height: 2em;
  background: var(--accent);
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
}
```

## Infobox Sidebar

```html
<aside class="infobox">
  <h3>{TOPIC}</h3>
  <table>
    <tr><th>First proposed</th><td>{DATE}</td></tr>
    <tr><th>Key proponents</th><td>{NAMES}</td></tr>
    <tr><th>Related to</th><td>{RELATED}</td></tr>
  </table>
</aside>
```

```css
.infobox {
  background: var(--bg-table-alt);
  border: 1px solid var(--border);
  padding: 1rem;
  border-radius: 4px;
  font-size: 0.9em;
}
.infobox h3 {
  border-bottom: 2px solid var(--accent);
  margin-bottom: 0.5rem;
}
```
