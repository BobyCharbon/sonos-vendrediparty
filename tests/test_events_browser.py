"""Parcours du module local. Supabase/Twilio sont simulés : aucun SMS réel."""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

pw = pytest.importorskip('playwright.sync_api')
ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(not (ROOT / 'web/events/dist/index.html').exists(), reason='Construire web/events avant les tests navigateur')
USER = 'dd6a80f1-cc84-4fc2-8764-770b45786c04'
EVENT = '32f18a3b-827f-4123-8cf4-33de06c9a51c'


@pytest.fixture(scope='module')
def events_origin(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    env = {**os.environ, 'DATA_DIR': str(tmp_path_factory.mktemp('party-events-data')),
           'EVENTS_WEB_DIR': str(ROOT / 'web/events/dist'), 'ADMIN_PIN': '8462',
           'SPOTIFY_CLIENT_ID': '', 'SPOTIFY_CLIENT_SECRET': '', 'PYTHONDONTWRITEBYTECODE': '1'}
    process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port), '--lifespan', 'off'], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    origin = f'http://127.0.0.1:{port}'
    try:
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            try:
                if httpx.get(origin, timeout=1).status_code == 200: break
            except httpx.HTTPError: pass
            time.sleep(.05)
        else: raise AssertionError('Le serveur Party de test ne démarre pas')
        yield origin
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.fixture(scope='module')
def browser(request):
    # Les jeux peuvent déjà avoir ouvert la boucle Playwright via pytest-playwright.
    # Réutiliser cette instance permet aussi de lancer la suite complète.
    owned = False
    try:
        p = request.getfixturevalue('playwright')
    except pytest.FixtureLookupError:
        p = pw.sync_playwright().start()
        owned = True
    b = p.chromium.launch(headless=True)
    try:
        yield b
    finally:
        b.close()
        if owned:
            p.stop()


def mock_services(page, pending=False):
    calls = []
    profile = {'id': USER, 'display_name': 'Compte de démonstration', 'phone': '41791234567', 'role': 'admin', 'status': 'pending' if pending else 'active', 'avatar_url': None, 'created_at': '2026-10-19T08:00:00Z'}
    category = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Soirée', 'color': '#FFB347', 'sort': 0, 'archived': False, 'icon': None}
    event = {'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'description': 'Données fictives réservées aux tests.', 'created_by': USER,
             'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None,
             'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'location_name': 'Lieu de démonstration',
             'category_id': category['id'], 'category': category, 'event_tags': [], 'date_options': [], 'rsvps': [],
             'event_organizers': [], 'polls': [], 'bring_items': [], 'author': {'display_name': profile['display_name']},
             'show_participants': True, 'allow_maybe': True, 'allow_plus_ones': False, 'max_plus_ones': 0, 'max_participants': None,
             'rsvp_deadline': None, 'forum_enabled': True, 'all_day': False, 'price_chf': None, 'visibility': 'all'}
    def token():
        encode=lambda v:base64.urlsafe_b64encode(json.dumps(v).encode()).decode().rstrip('=')
        return '.'.join([encode({'alg':'HS256','typ':'JWT'}),encode({'sub':USER,'aud':'authenticated','role':'authenticated','exp':int(time.time())+3600}), 'test-signature'])
    def handle(route):
        request=route.request
        path=urlparse(request.url).path
        calls.append((request.method,path,request.post_data))
        headers={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile','Access-Control-Allow-Methods':'GET, POST, PATCH, DELETE, OPTIONS'}
        if request.method=='OPTIONS': return route.fulfill(status=204,headers=headers)
        result=[]
        if path.endswith('/auth/v1/otp'): result={}
        elif path.endswith('/auth/v1/verify') or path.endswith('/auth/v1/token'):
            result={'access_token':token(),'refresh_token':'local-test-refresh-token','expires_in':3600,'token_type':'bearer','user':{'id':USER,'aud':'authenticated','phone':profile['phone'],'app_metadata':{'provider':'phone'},'user_metadata':{},'created_at':profile['created_at']}}
        elif path.endswith('/auth/v1/user'): result={'id':USER,'phone':profile['phone'],'app_metadata':{},'user_metadata':{}}
        elif path.endswith('/auth/v1/logout'): result={}
        elif path.endswith('/rpc/get_member_directory'): result=profile
        elif path.endswith('/categories'): result=[category]
        elif path.endswith('/events'):
            result=event if 'id' in parse_qs(urlparse(request.url).query) else [event]
        elif path.endswith('/rsvps') and request.method=='POST':
            row=json.loads(request.post_data); event['rsvps']=[{**row,'waitlisted':False}];result=None
        elif path.endswith('/group_settings'): result={'organizers_can_edit_published':True,'name':'Groupe de démonstration','timezone':'Europe/Zurich','require_approval':True,'coadmins_skip_approval':True,'members_can_create_tags':False}
        elif path.endswith('/profiles'): result=[{'id':USER,'display_name':profile['display_name']}]
        route.fulfill(status=200,content_type='application/json',body=json.dumps(result),headers=headers)
    page.route('https://gsuetixzobooggeaubvb.supabase.co/**', handle)
    page.route_web_socket('wss://gsuetixzobooggeaubvb.supabase.co/**', lambda ws:ws.on_message(lambda _message: None))
    page.route('https://fonts.googleapis.com/**', lambda route:route.fulfill(status=200,body=''))
    return calls


def login(frame, country='CH'):
    if country=='FR': frame.get_by_role('radio',name='France +33').click()
    frame.get_by_label('Ton numéro de téléphone',exact=True).fill('06 12 34 56 78' if country=='FR' else '079 123 45 67')
    frame.get_by_role('button',name='Recevoir un code par SMS').click()
    frame.get_by_placeholder('123456',exact=True).fill('123456')
    frame.get_by_role('button',name='Se connecter',exact=True).click()


def test_events_require_sms_and_games_remain_available(browser, events_origin):
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();calls=mock_services(page)
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        page.get_by_role('button',name='Événements',exact=True).click()
        pw.expect(page.get_by_role('button',name='Événements',exact=True)).to_have_attribute('aria-current','page')
        frame=page.frame_locator('#eventsFrame')
        pw.expect(frame.get_by_role('button',name='Recevoir un code par SMS')).to_be_visible(timeout=15000)
        assert not any('/rest/v1/' in path for _,path,_ in calls)
        page.get_by_role('button',name='Jeux',exact=True).click()
        pw.expect(page.locator('[data-view="games"]')).to_be_visible()
        page.get_by_role('button',name='Événements',exact=True).click()
        pw.expect(frame.get_by_role('button',name='Recevoir un code par SMS')).to_be_visible()
        assert page.locator('#eventsFrame').get_attribute('src')=='/events/'
    finally: context.close()


@pytest.mark.parametrize('country,width',[('CH',390),('FR',1280),('CH',320),('CH',1051)])
def test_sms_login_events_details_and_rsvp(browser,events_origin,country,width):
    context=browser.new_context(viewport={'width':width,'height':1154 if width==1051 else 900 if width>400 else 568 if width==320 else 844})
    page=context.new_page();calls=mock_services(page)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto(events_origin,wait_until='domcontentloaded')
        page.get_by_role('button',name='Événements',exact=True).click()
        frame=page.frame_locator('#eventsFrame')
        login(frame,country)
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)',exact=True)).to_be_visible(timeout=15000)
        expected='+33612345678' if country=='FR' else '+41791234567'
        otp=next(json.loads(body) for method,path,body in calls if method=='POST' and path.endswith('/auth/v1/otp'))
        assert otp['phone']==expected
        event_frame=page.frame(url=events_origin+'/events/')
        assert event_frame.evaluate('document.documentElement.scrollWidth <= innerWidth')
        tabs=[frame.get_by_role('tab',name=label,exact=True).bounding_box() for label in ('À venir','Sondages','Propositions','Passés')]
        assert all(tab and tab['height']>=44 for tab in tabs)
        for left,right in zip(tabs,tabs[1:]):
            assert left['y']!=right['y'] or left['x']+left['width']<=right['x']
        # Plein écran : le module commence en haut de l’écran, sans le titre de Party.
        box=page.locator('#eventsFrame').bounding_box()
        assert box['y']<=1 and not page.locator('.top-head').is_visible()
        # Verrou façon app : la page Party ne défile plus derrière le module.
        assert page.evaluate("document.documentElement.classList.contains('tab-events') && getComputedStyle(document.body).position === 'fixed'")
        # Une sortie sans réponse : pastille sur l’onglet Événements.
        pw.expect(page.locator('[data-tab="events"] [data-events-badge]')).to_have_text('1',timeout=10000)
        folder=ROOT/'.impeccable/review';folder.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(folder/({1280:'desktop.png',390:'mobile.png',320:'mobile-320.png',1051:'user-1051.png'}[width])),full_page=True)
        frame.get_by_text('Sortie de démonstration (test local)',exact=True).click()
        pw.expect(frame.get_by_text('Tu viens ?',exact=True)).to_be_visible(timeout=15000)
        frame.get_by_role('button',name='Présent',exact=True).click()
        pw.expect(frame.get_by_text('C’est noté, tu viens !',exact=True)).to_be_visible(timeout=10000)
        pw.expect(frame.get_by_text('PRÉSENTS · 1',exact=True)).to_be_visible()
        pw.expect(frame.get_by_text('Toi',exact=True)).to_be_visible()
        # Les accompagnants ne sont pas autorisés sur cette sortie : un message remplace le compteur.
        pw.expect(frame.get_by_text('Pas d’accompagnant pour cette sortie',exact=False)).to_be_visible()
        # Plus de réponse attendue : la pastille de l’onglet Événements disparaît.
        pw.expect(page.locator('[data-tab="events"] [data-events-badge]')).to_be_hidden(timeout=10000)
        assert any(method=='POST' and path.endswith('/rsvps') for method,path,_ in calls)
        assert not errors
    finally: context.close()


def test_pending_member_waits_for_approval(browser,events_origin):
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();calls=mock_services(page,pending=True)
    try:
        page.goto(events_origin,wait_until='domcontentloaded')
        page.get_by_role('button',name='Événements',exact=True).click()
        frame=page.frame_locator('#eventsFrame');login(frame)
        pw.expect(frame.get_by_text('Demande envoyée',exact=True)).to_be_visible(timeout=15000)
        assert not any(path.endswith('/events') for _,path,_ in calls)
    finally: context.close()


IPHONE='Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1'
ANDROID='Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36'


@pytest.mark.parametrize('agent',['iphone','android'])
def test_add_to_calendar_opens_native_calendar_flow(browser,events_origin,agent):
    context=browser.new_context(viewport={'width':390,'height':844},user_agent=IPHONE if agent=='iphone' else ANDROID,accept_downloads=True)
    page=context.new_page();mock_services(page)
    google=[]
    context.route('https://calendar.google.com/**',lambda route:(google.append(route.request.url),route.fulfill(status=200,body='ok')))
    try:
        page.goto(events_origin,wait_until='domcontentloaded')
        page.get_by_role('button',name='Événements',exact=True).click()
        frame=page.frame_locator('#eventsFrame');login(frame)
        frame.get_by_text('Sortie de démonstration (test local)',exact=True).click()
        button=frame.get_by_role('button',name='Ajouter à mon agenda',exact=True)
        pw.expect(button).to_be_visible(timeout=15000)
        if agent=='iphone':
            # Safari iOS reçoit un vrai text/calendar au niveau de la page et affiche « Ajouter ».
            with page.expect_download() as info: button.click()
            download=info.value
            assert download.suggested_filename=='sortie-de-demonstration-test-local.ics'
            body=open(download.path(),encoding='utf-8').read()
            assert 'DTSTART:20301114T180000Z' in body and 'SUMMARY:Sortie de démonstration (test local)' in body
            assert 'LOCATION:Lieu de démonstration' in body
            pw.expect(frame.get_by_text('Autre choix :',exact=False)).to_be_visible()
        else:
            with context.expect_page() as info: button.click()
            info.value.wait_for_load_state()
            query=parse_qs(urlparse(google[0]).query)
            assert query['action']==['TEMPLATE'] and query['text']==['Sortie de démonstration (test local)']
            assert query['dates']==['20301114T180000Z/20301114T210000Z']
        assert page.frame(url=events_origin+'/events/event/'+EVENT) or page.locator('#eventsFrame').is_visible()
    finally: context.close()
