"""Souvenirs (avis 74d36b93e7bd, maquette v2 validée le 24.11.2026), écrans web du module Événements dans un vrai navigateur,
Supabase et relais du serveur SIMULÉS (`/api/account/souvenirs/rpc`, `/api/account/souvenirs/photo`) :
- fiche pendant la soirée : avis « 📸 Souvenirs actif · L'organisation peut voir… », appareil jetable (poses), « Prendre une
  photo · N restantes », envoi par <input capture>, « Annuler » 5 s SANS jamais montrer la photo, compteur commun ;
- CGU exigées au premier envoi : la feuille, puis la même photo repart ;
- relecture de l'organisation : signalée en tête avec son motif, Retirer / Remettre, ✕ en deux touchers, mes photos absentes ;
- story (?souvenirs=1) : barres, gauche / droite, « Visible encore X h », ⭐ Garder, ⋯ Signaler (motif my_image, merci) ;
- enregistrement coupé : la story se regarde dans l'app iPhone ; après la story, l'état vide de la maquette ;
- « Mes souvenirs » : filtre Toutes / Prises par moi / Gardées, auteur, lien de téléchargement, Supprimer / Retirer ;
- app iPhone : PartyNative.souvenirs.camera / story / save, window.PartySouvenirs.changed(id) relit l'état ;
- formulaire : « 📸 Souvenirs » éteint, « Autoriser l'enregistrement » allumé, avertissement orange, figé après la 1re photo ;
- lien de notification ?souvenirs=1 / review (events-shell.js).
Captures : PARTY_SHOTS=<dossier> (sinon le dossier temporaire)."""
import base64
import io
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import pytest
from PIL import Image, ImageDraw

from tests.test_events_browser import EVENT, USER, browser, events_origin, mock_services, pw  # noqa: F401 (fixtures)
from tests.test_groups_browser import CORS, SUPABASE, phone, signed_in  # noqa: F401 (fixtures)

ROOT = Path(__file__).resolve().parents[1]
SHOTS = Path(os.environ.get('PARTY_SHOTS') or tempfile.gettempdir())
MAE, LEO, INES = (f'7b1c2b3d-0000-4000-8000-00000000002{i}' for i in range(3))
P = [f'5d000000-0000-4000-8000-00000000000{i}' for i in range(1, 8)]
NOW = datetime.now(timezone.utc)
REPORTED_LABEL = 'Je suis sur la photo et je ne veux pas qu’elle soit montrée'


def iso(d: datetime) -> str:
    return d.isoformat()


def picture(a: str, b: str) -> str:
    """Une « photo » de soirée (dégradé et formes) en data: URI, pour des captures lisibles."""
    img = Image.new('RGB', (360, 480), a)
    draw = ImageDraw.Draw(img)
    for i in range(480):
        draw.line([(0, i), (360, i)], fill=tuple(int(int(a[j:j + 2], 16) * (1 - i / 480) + int(b[j:j + 2], 16) * i / 480) for j in (1, 3, 5)))
    draw.ellipse((90, 140, 270, 320), fill='#FFE08A')
    draw.ellipse((140, 200, 160, 220), fill='#3a2300')
    draw.ellipse((200, 200, 220, 220), fill='#3a2300')
    draw.arc((140, 220, 220, 290), 20, 160, fill='#3a2300', width=8)
    out = io.BytesIO()
    img.save(out, 'JPEG', quality=80)
    return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()


COLORS = [('#FF4F9A', '#5B2E8C'), ('#FFB547', '#9B6BFF'), ('#2bd4c4', '#5B2E8C'), ('#9B6BFF', '#FF4F9A'), ('#3d7bff', '#9B6BFF'),
          ('#ff6b7a', '#2a1a52'), ('#5B2E8C', '#2bd4c4')]
PICS = [picture(a, b) for a, b in COLORS]


def author(uid: str, name: str) -> dict:
    return {'id': uid, 'name': name, 'avatar_url': None, 'photo': None}


def photo(i: int, who: dict, minutes: int, **extra) -> dict:
    return {'id': P[i], 'event_id': EVENT, 'path': f'{EVENT}/{who["id"]}/{P[i]}.jpg', 'taken_at': iso(NOW - timedelta(hours=30, minutes=-minutes)),
            'mine': who['id'] == USER, 'author': who, 'url': PICS[i], **extra}


ME, MAE_A, LEO_A, INES_A = author(USER, 'Compte de démonstration'), author(MAE, 'Maé'), author(LEO, 'Léo'), author(INES, 'Inès')


# Ce que le formulaire relit de l'événement (loadDraft) : listes vides dans la base simulée.
FORM_ROWS = {'event_tags': [], 'event_invites': [], 'event_groups': [], 'event_phone_invites': [], 'date_options': [], 'public_link': True}


def counter(phase: str, **extra) -> dict:
    base = {'enabled': True, 'keep': True, 'locked': True, 'phase': phase, 'count': 5,
            'take_from': iso(NOW - timedelta(hours=1)), 'take_until': iso(NOW + timedelta(hours=3)),
            'reveal_at': iso(NOW + timedelta(hours=25)), 'story_until': iso(NOW + timedelta(hours=49)),
            'can_reveal_now': False, 'member': True, 'staff': True, 'max': 3, 'taken': 0, 'left': 3, 'can_take': True, 'seen': False}
    if phase == 'story':
        base.update(reveal_at=iso(NOW - timedelta(hours=1)), story_until=iso(NOW + timedelta(hours=23)), can_take=False)
    if phase == 'after':
        base.update(reveal_at=iso(NOW - timedelta(hours=30)), story_until=iso(NOW - timedelta(hours=6)), can_take=False)
    base.update(extra)
    return base


def souvenir_services(page, phase='open', keep=True, staff=True, event_extra=None, photo_status=None):
    """Base simulée des Souvenirs, posée par-dessus mock_services ; state['calls'] : (fonction, arguments)."""
    mock_services(page, event_extra={'souvenirs_enabled': True, 'souvenirs_keep': keep, 'souvenirs_locked': True,
                                     **({} if staff else {'created_by': MAE}), **(event_extra or {})})
    state = {'calls': [], 'counter': counter(phase, keep=keep, staff=staff), 'uploads': [],
             'photo_status': list(photo_status or []),
             'story': [photo(0, MAE_A, 0, kept=False, can_keep=keep), photo(1, LEO_A, 16, kept=False, can_keep=keep),
                       photo(2, ME, 32, kept=False, can_keep=False), photo(3, INES_A, 49, kept=True, can_keep=keep)],
             'mine': [photo(0, MAE_A, 0, origin='kept'), photo(2, ME, 32, origin='taken'), photo(4, ME, 95, origin='taken')],
             'review': [photo(0, MAE_A, 0), photo(1, LEO_A, 16), photo(2, ME, 32), photo(3, INES_A, 49)],
             'reported': [photo(5, LEO_A, 70, hidden_at=iso(NOW), reasons=['my_image'])]}

    def relay(route):
        request = route.request
        if request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        path = urlparse(request.url).path
        if path.endswith('/photo'):
            state['uploads'].append((request.headers.get('authorization', ''), request.headers.get('content-type'), len(request.post_data_buffer or b'')))
            status = state['photo_status'].pop(0) if state['photo_status'] else 200
            if status != 200:
                return route.fulfill(status=status, content_type='application/json', body=json.dumps(
                    {'code': 'terms_required', 'detail': 'Accepte les conditions d’utilisation pour publier.'}))
            c = state['counter']
            c.update(taken=c['taken'] + 1, left=c['left'] - 1, count=c['count'] + 1, can_take=c['left'] > 1)
            return route.fulfill(status=200, content_type='application/json',
                                 body=json.dumps({'id': P[6], 'path': 'x', 'taken': c['taken'], 'left': c['left'], 'cancel_until': iso(NOW)}))
        body = json.loads(request.post_data or '{}')
        fn, args = body['fn'], body['args']
        assert body['token'], 'le relais reçoit le jeton de la session'
        state['calls'].append((fn, args))
        c = state['counter']
        if fn == 'souvenir_counter':
            result = c
        elif fn == 'souvenir_cancel':
            c.update(taken=c['taken'] - 1, left=c['left'] + 1, count=c['count'] - 1, can_take=True)
            result = {'cancelled': True, 'left': c['left']}
        elif fn == 'souvenir_story':
            result = {'event_id': EVENT, 'title': 'Vendredi chez Maé', 'keep': keep, 'until': c['story_until'], 'photos': state['story']}
        elif fn == 'souvenir_mine':
            result = {'keep': keep, 'phase': c['phase'], 'photos': state['mine'] if keep else []}
        elif fn == 'souvenir_review':
            result = {'phase': c['phase'], 'photos': state['review'], 'reported': state['reported']}
        elif fn in ('souvenir_remove', 'souvenir_delete'):
            state['review'] = [p for p in state['review'] if p['id'] != args['id']]
            state['reported'] = [p for p in state['reported'] if p['id'] != args['id']]
            state['mine'] = [p for p in state['mine'] if p['id'] != args['id']]
            result = {'removed': True}
        elif fn == 'souvenir_unkeep':
            state['mine'] = [p for p in state['mine'] if p['id'] != args['id']]
            result = {'kept': False}
        elif fn == 'souvenir_restore':
            back = [p for p in state['reported'] if p['id'] == args['id']]
            state['reported'] = [p for p in state['reported'] if p['id'] != args['id']]
            state['review'] += [{**p, 'hidden_at': None} for p in back]
            result = {'restored': True}
        else:  # souvenir_keep, souvenir_mark_seen, report_content, souvenir_reveal_now
            result = {'ok': True}
        route.fulfill(status=200, content_type='application/json', body=json.dumps({'result': result}))

    page.route('**/api/account/souvenirs/**', relay)
    return state


def shot(page, name: str):
    page.wait_for_timeout(700)
    page.screenshot(path=str(SHOTS / name))


def open_event(page, origin, query=''):
    signed_in(page, origin, f'/event/{EVENT}{query}')
    pw.expect(page.get_by_test_id('souvenirs')).to_be_visible(timeout=15000)


def names(state):
    return [f for f, _ in state['calls']]


def jpeg() -> bytes:
    out = io.BytesIO()
    Image.new('RGB', (40, 30), '#ff4f9a').save(out, 'JPEG')
    return out.getvalue()


def test_during_the_party_a_photo_goes_to_the_lab_unseen_and_can_be_cancelled_for_five_seconds(phone, events_origin):
    page, errors = phone
    state = souvenir_services(page, phase='open')
    open_event(page, events_origin)
    pw.expect(page.get_by_text('📸 Souvenirs actif · L’organisation peut voir les photos avant le dévoilement.', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('Chacun pourra garder ses préférées dans ses souvenirs.', exact=False).first).to_be_visible()
    pw.expect(page.get_by_text('Ton appareil jetable', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('🧪 Au labo :', exact=False)).to_contain_text('5 photos')
    pw.expect(page.get_by_role('button', name='Relire les photos (5), organisation seulement')).to_be_visible()
    page.get_by_test_id('souvenirs').scroll_into_view_if_needed()
    shot(page, 'souvenirs-fiche-open.png')

    shoot = page.get_by_role('button', name='📸 Prendre une photo · 3 restantes')
    with page.expect_file_chooser() as chooser:
        shoot.click()
    chooser.value.set_files(files=[{'name': 'photo.jpg', 'mimeType': 'image/jpeg', 'buffer': jpeg()}])
    undo = page.get_by_test_id('souvenir-undo')
    pw.expect(undo).to_contain_text('🧪 Partie au labo')
    pw.expect(undo).to_contain_text('Encore 2 poses · tu ne la reverras qu’au dévoilement.')
    assert state['uploads'][0][0].startswith('Bearer ') and state['uploads'][0][2] > 100
    # Jamais d'aperçu de sa propre photo : aucune image tirée du fichier choisi.
    assert page.locator('img[src^="blob:"], img[src^="data:image/jpeg"]').count() == 0
    shot(page, 'souvenirs-annuler.png')
    page.get_by_role('button', name='Annuler la photo', exact=False).click()
    pw.expect(undo).to_contain_text('↩︎ Photo annulée')
    assert ('souvenir_cancel', {'id': P[6]}) in state['calls']
    pw.expect(page.get_by_role('button', name='📸 Prendre une photo · 3 restantes')).to_be_visible()
    assert not errors, errors


def test_terms_are_asked_at_the_first_photo_then_the_same_photo_leaves(phone, events_origin):
    page, errors = phone
    state = souvenir_services(page, phase='open', photo_status=[403])
    accepted = {'v': False}

    def terms(route):
        if route.request.method == 'OPTIONS':
            return route.fulfill(status=204, headers=CORS)
        if route.request.url.endswith('/accept_terms'):
            accepted['v'] = True
        body = {'version': '2026-11-18', 'accepted': accepted['v'], 'accepted_at': None, 'contact_email': None, 'enforced': True}
        route.fulfill(status=200, content_type='application/json', headers=CORS, body=json.dumps(body))
    page.route('**/rest/v1/rpc/my_terms', terms)
    page.route('**/rest/v1/rpc/accept_terms', terms)
    open_event(page, events_origin)
    with page.expect_file_chooser() as chooser:
        page.get_by_role('button', name='📸 Prendre une photo · 3 restantes').click()
    chooser.value.set_files(files=[{'name': 'photo.jpg', 'mimeType': 'image/jpeg', 'buffer': jpeg()}])
    pw.expect(page.get_by_text('Avant ta première photo', exact=True)).to_be_visible()
    page.get_by_role('button', name='J’accepte').click()
    pw.expect(page.get_by_test_id('souvenir-undo')).to_contain_text('🧪 Partie au labo')
    assert len(state['uploads']) == 2 and accepted['v']
    assert not errors, errors


def test_the_organization_reviews_reported_photos_first_with_the_reason(phone, events_origin):
    page, errors = phone
    state = souvenir_services(page, phase='waiting')
    state['counter'].update(can_reveal_now=True)
    open_event(page, events_origin)
    pw.expect(page.get_by_text('avant le dévoilement', exact=False).first).to_be_visible()
    page.get_by_test_id('souvenirs').scroll_into_view_if_needed()
    shot(page, 'souvenirs-attente.png')
    page.get_by_role('button', name='Relire les photos (5), organisation seulement').click()
    pw.expect(page.get_by_text('🚩 Signalée', exact=True)).to_be_visible()
    pw.expect(page.get_by_text(REPORTED_LABEL, exact=True)).to_be_visible()
    # Mes propres photos n'y sont pas (je les découvre au dévoilement) : 3 photos des autres + 1 signalée.
    pw.expect(page.get_by_test_id('review-photo')).to_have_count(3)
    pw.expect(page.get_by_test_id('review-reported')).to_have_count(1)
    shot(page, 'souvenirs-relecture.png')
    page.get_by_role('button', name='Retirer la photo de Léo').first.click()
    pw.expect(page.get_by_test_id('review-reported')).to_have_count(0)
    assert ('souvenir_remove', {'id': P[5]}) in state['calls']
    rm = page.get_by_role('button', name='Retirer la photo de Maé', exact=False)
    rm.click()
    page.get_by_role('button', name='Retirer ?').click()
    pw.expect(page.get_by_test_id('review-photo')).to_have_count(2)
    review = page.get_by_label('Relire les photos', exact=True)
    review.get_by_role('button', name='Dévoiler maintenant').click()
    review.get_by_role('button', name='Oui, dévoiler').click()
    pw.expect(page.get_by_text('📸 Dévoilé : tout le monde est prévenu.', exact=False)).to_be_visible()
    assert 'souvenir_reveal_now' in names(state)
    assert not errors, errors


def test_the_story_link_opens_the_player_keeps_a_photo_and_reports_my_image(phone, events_origin):
    page, errors = phone
    state = souvenir_services(page, phase='story')
    open_event(page, events_origin, '?souvenirs=1')
    pw.expect(page.get_by_test_id('story-photo')).to_be_visible(timeout=10000)
    page.wait_for_timeout(300)
    assert ('souvenir_mark_seen', {'e': EVENT}) in state['calls']
    viewer = page.get_by_label('Story des souvenirs')
    pw.expect(viewer.get_by_text('Maé', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('⏳ Visible encore 23 h', exact=True)).to_be_visible()
    pw.expect(page.get_by_text('1 / 4', exact=True)).to_be_visible()
    page.get_by_role('button', name='⭐ Garder dans mes souvenirs').click()
    pw.expect(page.get_by_role('button', name='⭐ Gardée')).to_be_visible()
    assert ('souvenir_keep', {'id': P[0]}) in state['calls']
    shot(page, 'souvenirs-story.png')
    page.get_by_role('button', name='Photo suivante').click()
    pw.expect(viewer.get_by_text('Léo', exact=True)).to_be_visible()
    page.get_by_role('button', name='Photo précédente').click()
    pw.expect(page.get_by_text('1 / 4', exact=True)).to_be_visible()
    page.get_by_role('button', name='Plus d’options').click()
    pw.expect(page.get_by_text('Bloquer Maé', exact=True)).to_be_visible()
    page.get_by_role('menuitem').filter(has_text='Signaler').click()
    pw.expect(page.get_by_role('radio', name=REPORTED_LABEL)).to_be_visible()
    page.get_by_role('radio', name=REPORTED_LABEL).click()
    shot(page, 'souvenirs-signaler.png')
    sheet = page.get_by_label('Signaler', exact=True)
    sheet.get_by_role('button', name='Envoyer', exact=True).click()
    pw.expect(page.get_by_text('Merci. La photo est masquée ; l’organisation et la modération de Party sont prévenues.', exact=True)).to_be_visible()
    report = next(a for f, a in state['calls'] if f == 'report_content')
    assert report['p_kind'] == 'souvenir' and report['p_target'] == P[0] and report['p_reason'] == 'my_image'
    sheet.get_by_role('button', name='Fermer', exact=True).click()
    pw.expect(page.get_by_text('🚩 Photo signalée et masquée', exact=True)).to_be_visible()
    # Ma propre photo : pas de ⋯ ni de ⭐, « déjà dans tes souvenirs ».
    page.get_by_role('button', name='Photo suivante').click()
    page.get_by_role('button', name='Photo suivante').click()
    pw.expect(page.get_by_text('📸 Ta photo · déjà dans tes souvenirs', exact=True)).to_be_visible()
    pw.expect(page.get_by_role('button', name='Plus d’options')).to_have_count(0)
    page.get_by_role('button', name='Fermer la story').click()
    pw.expect(page.get_by_test_id('story-photo')).to_have_count(0)
    pw.expect(page.get_by_text('Les souvenirs sont arrivés', exact=True)).to_be_visible()
    page.get_by_text('Les souvenirs sont arrivés', exact=True).scroll_into_view_if_needed()
    shot(page, 'souvenirs-fiche-story.png')
    assert not errors, errors


def test_without_recording_the_story_is_for_the_iphone_app_and_nothing_stays(phone, events_origin):
    page, errors = phone
    souvenir_services(page, phase='story', keep=False)
    open_event(page, events_origin, '?souvenirs=1')
    pw.expect(page.get_by_text('📱 Cette story se regarde dans l’app iPhone (captures bloquées).', exact=True)).to_be_visible()
    pw.expect(page.get_by_role('button', name='▶︎ Voir la story')).to_have_count(0)
    pw.expect(page.get_by_test_id('story-photo')).to_have_count(0)
    pw.expect(page.get_by_text('📸 Mes souvenirs', exact=True)).to_have_count(0)
    page.get_by_test_id('souvenirs').scroll_into_view_if_needed()
    shot(page, 'souvenirs-story-sans-enregistrement.png')
    assert not errors, errors


def test_after_the_story_without_recording_the_empty_state_of_the_mockup(phone, events_origin):
    page, errors = phone
    souvenir_services(page, phase='after', keep=False)
    open_event(page, events_origin)
    pw.expect(page.get_by_text('Les photos de cette soirée ne se gardent pas', exact=False)).to_be_visible()
    pw.expect(page.get_by_text('L’organisateur n’a pas autorisé l’enregistrement.', exact=False)).to_be_visible()
    pw.expect(page.get_by_text('Souvenirs actif', exact=False)).to_have_count(0)
    page.get_by_test_id('souvenirs').scroll_into_view_if_needed()
    shot(page, 'souvenirs-apres-sans-enregistrement.png')
    assert not errors, errors


def test_my_souvenirs_filter_save_delete_and_remove(phone, events_origin):
    page, errors = phone
    state = souvenir_services(page, phase='after')
    open_event(page, events_origin)
    pw.expect(page.get_by_text('📸 Mes souvenirs', exact=True)).to_be_visible()
    items = page.get_by_test_id('souvenir-item')
    pw.expect(items).to_have_count(3)
    pw.expect(page.get_by_role('tab', name='Prises par moi 2')).to_be_visible()
    pw.expect(page.get_by_text('⭐ Gardée', exact=True)).to_have_count(1)
    save = page.get_by_role('link', name='⬇︎ Enregistrer').first
    assert 'download=souvenir-' in (save.get_attribute('href') or '')
    page.get_by_text('📸 Mes souvenirs', exact=True).scroll_into_view_if_needed()
    shot(page, 'souvenirs-mes-souvenirs.png')
    page.get_by_role('tab', name='Gardées 1').click()
    pw.expect(items).to_have_count(1)
    page.get_by_role('button', name='Retirer de mes souvenirs la photo de Maé').click()
    pw.expect(page.get_by_text('Aucune photo gardée. Pendant la story, touche ⭐ sur celles que tu aimes.', exact=True)).to_be_visible()
    assert ('souvenir_unkeep', {'id': P[0]}) in state['calls']
    page.get_by_role('tab', name='Prises par moi 2').click()
    page.get_by_role('button', name='Supprimer ma photo de', exact=False).first.click()
    page.get_by_role('button', name='Supprimer pour de bon ?').click()
    pw.expect(items).to_have_count(1)
    assert ('souvenir_delete', {'id': P[2]}) in state['calls']
    assert not errors, errors


def test_in_the_iphone_app_camera_story_and_save_are_native(phone, events_origin):
    page, errors = phone
    page.add_init_script("""window.__native = []; window.PartyNative = { souvenirs: {
      camera: (id) => window.__native.push(['camera', id]), story: (id) => window.__native.push(['story', id]),
      save: (url) => window.__native.push(['save', url.slice(0, 10)]) } };""")
    state = souvenir_services(page, phase='open')
    open_event(page, events_origin)
    page.get_by_role('button', name='📸 Prendre une photo · 3 restantes').click()
    assert page.evaluate('window.__native') == [['camera', EVENT]]
    assert page.locator('input[type=file]').count() == 0
    # L'appareil natif s'est refermé après une photo : la page relit le compteur.
    state['counter'].update(left=2, taken=1, count=6)
    page.evaluate(f"window.PartySouvenirs.changed('{EVENT}')")
    pw.expect(page.get_by_role('button', name='📸 Prendre une photo · 2 restantes')).to_be_visible()
    assert not errors, errors


def test_in_the_iphone_app_the_story_link_opens_the_native_player(phone, events_origin):
    page, errors = phone
    page.add_init_script("""window.__native = []; window.PartyNative = { souvenirs: {
      camera: (id) => window.__native.push(['camera', id]), story: (id) => window.__native.push(['story', id]),
      save: (url) => window.__native.push(['save', url.slice(0, 10)]) } };""")
    souvenir_services(page, phase='story', keep=False)
    open_event(page, events_origin, '?souvenirs=1')
    page.wait_for_function('window.__native.length > 0')
    assert page.evaluate('window.__native') == [['story', EVENT]]
    pw.expect(page.get_by_test_id('story-photo')).to_have_count(0)
    page.get_by_role('button', name='▶︎ Voir la story').click()
    assert page.evaluate('window.__native')[-1] == ['story', EVENT]
    assert not errors, errors


def test_the_form_has_souvenirs_off_recording_on_and_the_orange_warning(phone, events_origin):
    page, errors = phone
    souvenir_services(page, phase='open', event_extra={**FORM_ROWS, 'souvenirs_enabled': False, 'souvenirs_locked': False})
    sent = []
    page.on('request', lambda r: sent.append(r.post_data) if r.method == 'PATCH' and r.url.split('?')[0].endswith('/events') else None)
    signed_in(page, events_origin, f'/event/{EVENT}/edit')
    box = page.get_by_test_id('souvenirs-settings')
    pw.expect(box).to_be_visible(timeout=15000)
    souvenirs = box.get_by_role('switch', name='📸 Souvenirs')
    pw.expect(souvenirs).not_to_be_checked()
    pw.expect(box.get_by_role('switch', name='Autoriser l’enregistrement')).to_have_count(0)
    souvenirs.click()
    keep = box.get_by_role('switch', name='Autoriser l’enregistrement')
    pw.expect(keep).to_be_checked()
    pw.expect(box.get_by_text('Chacun pourra garder ses préférées dans ses souvenirs (13 mois).', exact=False)).to_be_visible()
    keep.click()
    warn = box.get_by_role('alert')
    pw.expect(warn).to_contain_text('Enregistrement désactivé')
    pw.expect(warn).to_contain_text('Captures bloquées dans l’app iPhone seulement ; ailleurs, rien ne peut l’empêcher.')
    box.scroll_into_view_if_needed()
    shot(page, 'souvenirs-reglages.png')
    page.get_by_role('button', name='Enregistrer', exact=True).first.click()
    page.wait_for_timeout(1500)
    body = next((json.loads(b) for b in sent if b and 'souvenirs_enabled' in b), None)
    assert body and body['souvenirs_enabled'] is True and body['souvenirs_keep'] is False, sent
    assert not errors, errors


def test_settings_are_frozen_after_the_first_photo(phone, events_origin):
    page, errors = phone
    souvenir_services(page, phase='open', event_extra={**FORM_ROWS, 'souvenirs_locked': True})
    signed_in(page, events_origin, f'/event/{EVENT}/edit')
    box = page.get_by_test_id('souvenirs-settings')
    pw.expect(box).to_be_visible(timeout=15000)
    pw.expect(box.get_by_role('switch', name='📸 Souvenirs')).to_be_disabled()
    pw.expect(box.get_by_text('🔒 Réglages figés depuis la première photo', exact=False)).to_be_visible()
    assert not errors, errors


@pytest.mark.skipif(not shutil.which('node'), reason='Node absent')
def test_notification_links_open_the_story_or_the_review():
    shell = ROOT / 'app/static/events-shell.js'
    script = ("globalThis.window = { addEventListener() {} }; globalThis.document = { readyState: 'loading', addEventListener() {} }; "
              "import(process.argv[1]).then(() => console.log(JSON.stringify("
              "JSON.parse(process.argv[2]).map((q) => window.PartyEvents.target(new URLSearchParams(q))))))")
    queries = [f'tab=events&event={EVENT}&souvenirs=1', f'tab=events&event={EVENT}&souvenirs=review', f'tab=events&event={EVENT}&souvenirs=x']
    out = subprocess.run(['node', '-e', script, shell.as_uri(), json.dumps(queries)], capture_output=True, text=True, check=True, timeout=30)
    assert json.loads(out.stdout) == [f'/events/event/{EVENT}?souvenirs=1', f'/events/event/{EVENT}?souvenirs=review', f'/events/event/{EVENT}']
    page = (ROOT / 'app/static/index.html').read_text(encoding='utf-8')
    assert 'window.PartySouvenirs = {' in page and 'contentWindow.PartySouvenirs?.changed(eventId)' in page


def test_the_moderation_screens_read_the_souvenirs_bucket():
    web = (ROOT / 'web/events/src/app/admin/reports.tsx').read_text(encoding='utf-8')
    assert "supabase.storage.from(SOUVENIRS).createSignedUrls" in web and "souvenir: 'Photo Souvenirs'" in web
    server = (ROOT / 'app/moderation_api.py').read_text(encoding='utf-8')
    assert 'self.admin._photos(souvenirs, token, "souvenirs")' in server
