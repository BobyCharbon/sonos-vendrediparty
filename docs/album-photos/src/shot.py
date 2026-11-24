import sys
from playwright.sync_api import sync_playwright
d='/private/tmp/claude-502/-Users-ludovictrombert-sonos-vendrediparty/2593be6d-12b9-4238-a528-30280e4e74a6/scratchpad/album-photos'
name=sys.argv[1]
with sync_playwright() as p:
    b=p.chromium.launch()
    pg=b.new_page(viewport={'width':4700,'height':1250})
    errs=[]; pg.on('pageerror',lambda e:errs.append(str(e))); pg.on('console',lambda m: m.type=='error' and errs.append(m.text))
    pg.goto(f'file://{d}/{name}'); pg.wait_for_timeout(1500)
    pg.screenshot(path=f'{d}/shots/{name}-all.png')
    for a in sys.argv[2:]:
        exec(a)
    m=b.new_page(viewport={'width':375,'height':812})
    m.goto(f'file://{d}/{name}'); m.wait_for_timeout(600)
    m.screenshot(path=f'{d}/shots/{name}-375.png'); print('scrollW',m.evaluate('document.documentElement.scrollWidth'))
    print('errs',errs)
    b.close()
