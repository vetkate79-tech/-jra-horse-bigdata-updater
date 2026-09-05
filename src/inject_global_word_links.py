#!/usr/bin/env python3
from pathlib import Path

DOCS=Path('docs')
TAG='<script src="/-jra-horse-bigdata-updater/word-links.js"></script>'
NAV_TAG='<script src="/-jra-horse-bigdata-updater/global-bottom-nav.js"></script>'
SKIP_DIRS={'words'}
SKIP_FILES={Path('index.html')}

changed=0
scanned=0
for p in DOCS.rglob('*.html'):
    rel=p.relative_to(DOCS)
    is_admin=bool(rel.parts and rel.parts[0]=='admin')
    skip_words=bool(rel.parts and rel.parts[0] in SKIP_DIRS)
    if rel in SKIP_FILES:
        text=p.read_text(encoding='utf-8',errors='ignore')
        if TAG in text:
            p.write_text(text.replace(TAG,''),encoding='utf-8')
            changed+=1
        text=p.read_text(encoding='utf-8',errors='ignore')
    else:
        text=p.read_text(encoding='utf-8',errors='ignore')
    scanned+=1
    tags=[]
    if not skip_words and rel not in SKIP_FILES and 'word-links.js' not in text:
        tags.append(TAG)
    if not is_admin and 'global-bottom-nav.js' not in text:
        tags.append(NAV_TAG)
    if tags:
        addition=''.join(tags)
        if '</body>' in text:
            text=text.replace('</body>',addition+'</body>',1)
        elif '</html>' in text:
            text=text.replace('</html>',addition+'</html>',1)
        else:
            text+=addition
        p.write_text(text,encoding='utf-8')
        changed+=1
print({'scanned':scanned,'changed':changed})
