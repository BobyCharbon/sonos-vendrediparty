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


def mock_services(page, pending=False, events=1):
    calls = []
    profile = {'id': USER, 'display_name': 'Compte de démonstration', 'phone': '41791234567', 'role': 'guest' if pending else 'admin', 'status': 'active', 'avatar_url': f'{USER}/photo.jpg', 'first_name': 'Camille', 'last_name': 'Demo', 'created_at': '2026-10-19T08:00:00Z'}
    category = {'id': 'ed69d11e-34dd-43fe-b211-10d0dd158ba9', 'name': 'Soirée', 'color': '#FFB347', 'sort': 0, 'archived': False, 'icon': None}
    event = {'id': EVENT, 'title': 'Sortie de démonstration (test local)', 'description': 'Données fictives réservées aux tests.', 'created_by': USER,
             'status': 'published', 'date_mode': 'fixed', 'starts_at': '2030-11-14T18:00:00Z', 'ends_at': None,
             'created_at': '2026-10-19T08:00:00Z', 'updated_at': '2026-10-19T08:00:00Z', 'location_name': 'Lieu de démonstration',
             'category_id': category['id'], 'category': category, 'event_tags': [], 'date_options': [], 'rsvps': [],
             'event_organizers': [], 'polls': [], 'bring_items': [], 'author': {'display_name': profile['display_name']},
             'show_participants': True, 'allow_maybe': True, 'allow_plus_ones': False, 'max_plus_ones': 0, 'max_participants': None,
             'rsvp_deadline': None, 'forum_enabled': True, 'all_day': False, 'price_chf': None, 'visibility': 'all'}
    # Droits du compte (catalogue réel : migration 20261020160100) ; un invité ne voit pas les sorties.
    perms = ['games.create', 'music.add'] if pending else ['events.view', 'events.rsvp', 'events.plus_ones', 'events.create', 'events.publish_direct',
             'events.edit_own_published', 'events.manage_all', 'events.approve', 'events.see_participants', 'polls.create', 'chat.write', 'chat.moderate',
             'taxonomy.manage', 'announcements.publish', 'group.settings', 'members.approve', 'members.view_identity', 'members.roles', 'members.ban',
             'roles.manage', 'games.create', 'music.add']
    join = {}
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
        elif path.endswith('/rpc/my_permissions'): result=perms
        elif path.endswith('/rpc/my_rank'): result=0 if pending else 99
        elif path.endswith('/rpc/request_join'): join.update(message=json.loads(request.post_data)['note'] or None, status='pending', created_at='2026-10-20T08:00:00Z'); result=None
        elif path.endswith('/permissions'): result=[{'key':'events.view','grp':'Événements','label':'Voir les événements','hint':None,'sort':10},{'key':'events.publish_direct','grp':'Événements','label':'Publier sans validation','hint':None,'sort':14}]
        elif path.endswith('/role_permissions'): result=[{'role':'member','perm':'events.view'}]
        elif path.endswith('/rpc/set_role_permission'): result=None
        elif path.endswith('/join_requests'):
            if 'vnd.pgrst.object' in (request.headers.get('accept') or ''):
                if not join: return route.fulfill(status=406,content_type='application/json',body=json.dumps({'code':'PGRST116','message':'0 rows'}),headers=headers)
                result=join
            else: result=[join] if join else []
        elif path.endswith('/categories'): result=[category]
        elif path.endswith('/events'):
            result=event if 'id' in parse_qs(urlparse(request.url).query) else [event]+[
                {**event,'id':f'{EVENT[:-2]}{i:02d}','title':f'Sortie de démonstration {i}'} for i in range(1,events)]
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
        # Même modèle que le reste de Party : barre d’onglets fixée en bas, page jamais figée.
        assert page.evaluate("getComputedStyle(document.body).position") == 'static'
        # Le module descend jusqu’à la barre d’onglets, sans bande vide entre les deux.
        tabs=page.locator('#tabs').bounding_box()
        if width<900: assert abs(box['y']+box['height']-tabs['y'])<=1 and abs(tabs['y']+tabs['height']-page.viewport_size['height'])<=1
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


def test_new_account_is_told_it_is_signed_in_without_join_request(browser,events_origin):
    """Première connexion SMS : plus de demande d'adhésion ; le Guest voit la confirmation et ses sorties."""
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();calls=mock_services(page,pending=True)
    try:
        page.goto(events_origin,wait_until='domcontentloaded')
        page.get_by_role('button',name='Événements',exact=True).click()
        frame=page.frame_locator('#eventsFrame');login(frame)
        # Guest au profil complet : il arrive sur les sorties qu'il voit (publiques, invitations), avec la confirmation.
        pw.expect(frame.get_by_text('Tu es connecté à ton compte ✓',exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_text('sorties publiques et celles où on t’invite',exact=False)).to_be_visible()
        pw.expect(frame.get_by_text('Rejoindre le groupe',exact=True)).to_have_count(0)
        pw.expect(frame.get_by_role('button',name='Demander à rejoindre')).to_have_count(0)
        assert not any(path.endswith('/rpc/request_join') or path.endswith('/join_requests') for _,path,_ in calls)
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


def test_account_tab_signs_in_shows_settings_and_crops_a_photo(browser, events_origin, tmp_path):
    """Onglet « Se connecter » : même connexion SMS, puis les Réglages ; une photo choisie s'ouvre dans le recadrage."""
    from PIL import Image
    Image.new('RGB', (1600, 900), (200, 80, 120)).save(tmp_path / 'paysage.png')
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();mock_services(page)
    errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        page.locator('#accountTab').click()
        pw.expect(page.locator('#appTitle')).to_have_text('Se connecter')
        frame=page.frame_locator('#eventsFrame')
        login(frame)
        pw.expect(frame.get_by_text('Mon profil',exact=True)).to_be_visible(timeout=15000)
        pw.expect(frame.get_by_label('Surnom',exact=True)).to_have_value('Compte de démonstration')
        frame.locator('input[type=file]:not([capture])').set_input_files(str(tmp_path / 'paysage.png'))
        dialog=frame.get_by_role('dialog',name='Recadrer ta photo de profil')
        pw.expect(dialog).to_be_visible()
        dialog.get_by_role('button',name='Zoomer',exact=True).click()
        dialog.get_by_role('button',name='Pivoter d’un quart de tour').click()
        dialog.get_by_role('button',name='Valider la photo').click()
        pw.expect(dialog).to_have_count(0)
        pw.expect(frame.get_by_label('Aperçu de ta photo de profil')).to_be_visible()
        pw.expect(frame.get_by_role('button',name='Enregistrer',exact=True)).to_be_enabled()
        # Les Événements reprennent la liste des sorties, sans recharger le module (la pastille reste affichée sur Réglages).
        page.locator('#tabs [data-tab="events"]').click()
        pw.expect(frame.get_by_text('Sortie de démonstration (test local)',exact=True)).to_be_visible(timeout=15000)
        assert not errors, errors
    finally: context.close()


def test_roles_screen_toggles_a_permission_for_the_chosen_role(browser,events_origin):
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();calls=mock_services(page)
    try:
        page.goto(events_origin+'/events/admin/roles',wait_until='domcontentloaded')
        login(page)
        pw.expect(page.get_by_text('Publier sans validation',exact=True)).to_be_visible(timeout=15000)
        page.get_by_text('Organisateur',exact=True).click()
        page.get_by_role('switch',name='Publier sans validation').click()
        for _ in range(50):
            if any(path.endswith('/rpc/set_role_permission') for _,path,_ in calls): break
            page.wait_for_timeout(100)
        sent=[json.loads(b) for _,path,b in calls if path.endswith('/rpc/set_role_permission')]
        assert sent and sent[-1]=={'target':'organizer','perm':'events.publish_direct','granted':True}, sent
    finally: context.close()


def test_end_time_starts_from_start_and_can_be_cleared(browser,events_origin):
    """Fin : s'ouvre sur l'heure de début, rien avant le début, pas de 5 min, et s'efface (iOS n'a pas de bouton pour ça)."""
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();mock_services(page)
    try:
        page.goto(events_origin+'/events/',wait_until='domcontentloaded')
        login(page)
        page.get_by_role('button',name='Proposer un événement').click()
        start=page.get_by_label('Début',exact=True);end=page.get_by_label('Fin (optionnel)',exact=True)
        pw.expect(end).to_be_visible(timeout=15000)
        start.fill('2030-11-14T19:00')
        pw.expect(end).to_have_attribute('min','2030-11-14T19:00')
        pw.expect(end).to_have_attribute('step','300')
        pw.expect(page.get_by_role('button',name='Effacer : Fin (optionnel)')).to_have_count(0)
        end.focus()
        pw.expect(end).to_have_value('2030-11-14T19:00')
        page.get_by_role('button',name='Effacer : Fin (optionnel)').click()
        pw.expect(end).to_have_value('')
        pw.expect(page.get_by_role('button',name='Effacer : Fin (optionnel)')).to_have_count(0)
    finally: context.close()


def test_place_search_fills_name_address_and_google_maps_link(browser,events_origin):
    """Lieu : la recherche Google Maps remplit nom, adresse et lien (dist construit avec EXPO_PUBLIC_GOOGLE_MAPS_KEY)."""
    if b'places.googleapis.com' not in b''.join(p.read_bytes() for p in (ROOT/'web/events/dist/_expo').rglob('*.js')): pytest.skip('dist construit sans clé Google')
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();mock_services(page)
    cors={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'*','Access-Control-Allow-Methods':'GET, POST, OPTIONS'}
    def google(route):
        if route.request.method=='OPTIONS': return route.fulfill(status=204,headers=cors)
        if route.request.url.endswith(':autocomplete'):
            body={'suggestions':[{'placePrediction':{'placeId':'ChIJdemo','structuredFormat':{'mainText':{'text':'Lieu de démonstration'},'secondaryText':{'text':'Rue fictive 1, Lausanne'}}}}]}
        else: body={'displayName':{'text':'Lieu de démonstration'},'formattedAddress':'Rue fictive 1, 1003 Lausanne, Suisse','googleMapsUri':'https://maps.google.com/?cid=1'}
        route.fulfill(status=200,content_type='application/json',body=json.dumps(body),headers=cors)
    page.route('https://places.googleapis.com/**',google)
    try:
        page.goto(events_origin+'/events/',wait_until='domcontentloaded')
        login(page)
        page.get_by_role('button',name='Proposer un événement').click()
        search=page.get_by_label('Chercher un lieu sur Google Maps',exact=True)
        pw.expect(search).to_be_visible(timeout=15000)
        search.fill('demo')
        page.get_by_role('button',name='Lieu de démonstration, Rue fictive 1, Lausanne').click()
        pw.expect(page.get_by_label('Lieu',exact=True)).to_have_value('Lieu de démonstration')
        pw.expect(page.get_by_label('Adresse',exact=True)).to_have_value('Rue fictive 1, 1003 Lausanne, Suisse')
        pw.expect(page.get_by_label('Lien (site, carte…)',exact=True)).to_have_value('https://maps.google.com/?cid=1')
    finally: context.close()


def test_pending_badge_stays_on_when_leaving_the_events_screen(browser, events_origin):
    """Bug du 2026-10-21 : la pastille « 1 » disparaissait en ouvrant Réglages (le compteur vivait dans l'écran des sorties)."""
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();mock_services(page)
    badge=page.locator('#tabs [data-events-badge]')
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        page.get_by_role('button',name='Événements',exact=True).click()
        login(page.frame_locator('#eventsFrame'))
        pw.expect(badge).to_have_text('1'); pw.expect(badge).to_be_visible()
        page.locator('#accountTab').click()
        pw.expect(page.frame_locator('#eventsFrame').get_by_text('Réglages', exact=True).first).to_be_visible()
        page.wait_for_timeout(500)
        pw.expect(badge).to_have_text('1'); pw.expect(badge).to_be_visible()
        page.locator('#tabs [data-tab="games"]').click()
        page.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        page.wait_for_timeout(500)
        pw.expect(badge).to_have_text('1'); pw.expect(badge).to_be_visible()
        page.locator('#tabs [data-tab="events"]').click()
        pw.expect(badge).to_have_text('1')
    finally:
        context.close()


def test_root_account_opens_admin_page_from_settings_without_pin(browser, events_origin):
    """Compte root/admin : Réglages → « Admin de la soirée » → /admin ouvert sans code PIN ; sans compte, le code reste demandé."""
    context=browser.new_context(viewport={'width':390,'height':844})
    page=context.new_page();mock_services(page)
    root_perms=['events.view','events.manage_all','members.roles','party.admin','party.settings','games.lead_all','music.control']
    cors={'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'authorization, apikey, content-type, x-client-info, prefer, accept-profile, content-profile'}
    page.route('https://gsuetixzobooggeaubvb.supabase.co/rest/v1/rpc/my_permissions', lambda route: route.fulfill(
        status=204 if route.request.method=='OPTIONS' else 200, headers=cors, content_type='application/json', body=json.dumps(root_perms)))
    # Le serveur vérifierait le jeton auprès de Supabase : ici, la session admin s'ouvre comme avec le bon code.
    page.route('**/api/account/admin', lambda route: route.fulfill(response=route.fetch(url=f'{events_origin}/api/admin/login', post_data=json.dumps({'pin':'8462'}))))
    try:
        page.goto(events_origin + '/admin', wait_until='domcontentloaded')
        pw.expect(page.locator('#login')).to_be_visible()  # pas de compte sur ce téléphone : code PIN
        page.goto(events_origin, wait_until='domcontentloaded')
        page.locator('#accountTab').click()
        login(page.frame_locator('#eventsFrame'))
        link=page.frame_locator('#eventsFrame').get_by_text('🎛️ Admin de la soirée')
        pw.expect(link).to_be_visible()
        link.click()
        page.wait_for_url('**/admin')
        pw.expect(page.locator('#panel')).to_be_visible(timeout=10000)
        pw.expect(page.locator('#login')).to_be_hidden()
    finally:
        context.close()


ANDROID_PHONE = {'viewport': {'width': 412, 'height': 915}, 'device_scale_factor': 2.6, 'is_mobile': True, 'has_touch': True,
           'user_agent': 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36'}


def test_android_finger_on_an_event_card_scrolls_the_list(browser, events_origin):
    """Retour #10 : sous Android, le doigt posé SUR une carte ne faisait pas défiler la liste des sorties
    (seule une fine bande sans carte, au bord droit, défilait). Geste tactile réel de Chrome (scroll chaining,
    overscroll-behavior, touch-action compris), départ au milieu d'une carte."""
    context = browser.new_context(**ANDROID_PHONE)
    page = context.new_page()
    mock_services(page, events=12)
    try:
        page.goto(events_origin, wait_until='domcontentloaded')
        page.get_by_role('button', name='Événements', exact=True).click()
        frame = page.frame_locator('#eventsFrame')
        login(frame)
        card = frame.get_by_text('Sortie de démonstration 1', exact=True)
        pw.expect(card).to_be_visible(timeout=15000)
        event_frame = page.frame(url=events_origin + '/events/')
        # Conteneur qui défile réellement (ScrollView) : premier ancêtre de la carte plus haut que sa zone visible.
        scroller = """() => { let el = [...document.querySelectorAll('*')].find(e => e.textContent === 'Sortie de démonstration 1' && !e.children.length);
                       while (el && !(el.scrollHeight > el.clientHeight + 50 && /(auto|scroll)/.test(getComputedStyle(el).overflowY))) el = el.parentElement;
                       return el ? el.scrollTop : null; }"""
        before = event_frame.evaluate(scroller)
        assert before is not None, "la liste des sorties devrait pouvoir défiler"
        box = card.bounding_box()
        cdp = context.new_cdp_session(page)
        cdp.send('Input.synthesizeScrollGesture', {'x': box['x'] + box['width'] / 2, 'y': box['y'] + box['height'] / 2,
                                                    'yDistance': -350, 'gestureSourceType': 'touch', 'speed': 1200})
        page.wait_for_timeout(500)
        after = event_frame.evaluate(scroller)
        assert after > before + 100, f"le doigt sur une carte n'a pas fait défiler la liste ({before} → {after})"
    finally:
        context.close()
