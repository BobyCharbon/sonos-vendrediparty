import sys
from playwright.sync_api import sync_playwright
from PIL import Image
jobs=[('header.html',3840,1646,'en-tete-3840x1646.png'),('search.html',3840,2560,'recherche-3840x2560.png')]
with sync_playwright() as p:
    b=p.chromium.launch()
    for f,w,h,out in jobs:
        pg=b.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
        pg.goto('file://'+__import__('os').path.abspath(f)); pg.wait_for_timeout(500)
        pg.screenshot(path=out,full_page=False)
        Image.open(out).convert('RGB').save(out)
    b.close()
