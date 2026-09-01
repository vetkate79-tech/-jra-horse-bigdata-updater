#!/usr/bin/env python3
from pathlib import Path

DOCS=Path('docs')
TAG='<script src="/-jra-horse-bigdata-updater/word-links.js"></script>'
SKIP_DIRS={'words'}

changed=0
scanned=0
for p in DOCS.rglob('*.html'):
    rel=p.relative_to(DOCS)
    if rel.parts and rel.parts[0] in SKIP_DIRS:
        continue
    scanned+=1
    text=p.read_text(encoding='utf-8',errors='ignore')
    if 'word-links.js' in text:
        continue
    if '</body>' in text:
        text=text.replace('</body>',TAG+'</body>',1)
    elif '</html>' in text:
        text=text.replace('</html>',TAG+'</html>',1)
    else:
        text+=TAG
    p.write_text(text,encoding='utf-8')
    changed+=1
print({'scanned':scanned,'changed':changed})
