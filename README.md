# localize_html.py

Builds a JSON catalog from marked HTML and writes catalog strings back into the page.

It does not translate the text. The French strings are already in billing.fr.json.

## Run

```text
python localize_html.py extract billing.html billing.en.json
python localize_html.py build billing.html billing.fr.html --catalog billing.fr.json --lang fr --dir ltr
```

Article: https://htmltranslate.com/blog/extract-translatable-strings-html-to-json
