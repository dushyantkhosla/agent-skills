# Pywikibot API Reference

## Site

```python
site = pywikibot.Site('en', 'wikipedia')   # language, family
site = pywikibot.Site('commons', 'commons')
site = pywikibot.Site('wikidata', 'wikidata')
repo = site.data_repository()              # returns the Wikidata DataSite
```

## Page

```python
page = pywikibot.Page(site, 'Page Title')
page.text                    # raw wikitext (str)
page.title()                 # page title (str)
page.exists()                # bool
page.isRedirectPage()        # bool
page.getRedirectTarget()     # Page
page.categories()            # generator of Category objects
page.revision_count()        # int
```

## Category

```python
cat = pywikibot.Category(site, 'Category:Name')
cat.articles(total=50)       # generator of Pages (excludes subcats)
cat.subcategories()          # generator of Category objects
cat.members()                # generator of all members (pages + subcats + files)
cat.categoryinfo             # dict: {'pages': n, 'subcats': n, 'files': n}
```

## ItemPage (Wikidata)

```python
# From a Wikipedia page
item = pywikibot.ItemPage.fromPage(page)

# Directly by QID
repo = site.data_repository()
item = pywikibot.ItemPage(repo, 'Q42')

item.get()                   # must call before accessing data
item.labels                  # dict: {'en': 'label', ...}
item.descriptions            # dict: {'en': 'desc', ...}
item.aliases                 # dict: {'en': ['alias1', ...], ...}
item.sitelinks               # dict: {'enwiki': SiteLink, ...}
item.claims                  # dict: {'P31': [Claim, ...], ...}
```

### Navigating claims

```python
claims = item.claims
if 'P31' in claims:                          # P31 = instance of
    for claim in claims['P31']:
        target = claim.getTarget()           # ItemPage, str, WbTime, etc.
        if isinstance(target, pywikibot.ItemPage):
            target.get()
            print(target.labels.get('en'))
```

### Common property IDs

| PID | Meaning |
|-----|---------|
| P31 | instance of |
| P21 | sex or gender |
| P27 | country of citizenship |
| P569 | date of birth |
| P570 | date of death |
| P161 | cast member |
| P585 | point in time |
| P179 | part of the series |
| P166 | award received |
| P1346 | winner |

## SPARQL

```python
from pywikibot.data import sparql

q = sparql.SparqlQuery()
results = q.select("""
    SELECT ?item ?itemLabel WHERE {
      ?item wdt:P31 wd:Q5 .
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    } LIMIT 10
""")
# results: list of dicts, keys match SELECT variables
for row in results:
    print(row['itemLabel']['value'])
```

### SPARQL tips

- `wdt:Pxxx` — direct claim (most common)
- `ps:Pxxx` — statement value (use inside `?statement`)
- `wd:Qxxx` — entity reference
- `OPTIONAL { ... }` — left join, avoids dropping rows with missing fields
- `SERVICE wikibase:label` — auto-resolves `?xLabel` for any `?x` entity

## pagegenerators

```python
from pywikibot import pagegenerators

# Pages linking to a given page
gen = pagegenerators.LinkedPageGenerator(page)

# Pages in a category (alternative to Category.articles)
gen = pagegenerators.CategorizedPageGenerator(cat, recurse=True, total=100)

# Search results
gen = pagegenerators.SearchPageGenerator('Grammy Award', total=10, site=site)
```

## Exceptions

```python
pywikibot.exceptions.NoPageError          # page doesn't exist
pywikibot.exceptions.IsRedirectPageError  # page is a redirect
pywikibot.exceptions.InvalidTitleError    # malformed title
pywikibot.exceptions.ServerError          # HTTP/API error
pywikibot.exceptions.TimeoutError         # request timed out
```
