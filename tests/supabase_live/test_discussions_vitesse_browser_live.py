"""Vitesse des Discussions (demande de l'admin du 18.11 : « le plus rapide possible »), recette RÉELLE : base de TEST,
vrai navigateur, connexion normale de deux comptes de test, aucun faux. Mesures prises dans la page (du geste à la
première image où le résultat est à l'écran), avec des bornes larges (réseau du banc d'essai) :
  * la conversation s'ouvre EN BAS du fil (dernier message à l'écran) ;
  * Envoyer : la bulle est à l'écran en moins de 300 ms (avant toute réponse de la base) ;
  * le message arrive chez l'autre personne, conversation ouverte, sans recharger, en moins de 2 s ;
  * deuxième ouverture de la conversation (mémoire) : moins de 500 ms.

Lancement : SUPABASE_LIVE_TESTS=1 PARTY_TEST_EVENTS_DIST=<module construit contre la base de TEST> python -m pytest
tests/supabase_live/test_discussions_vitesse_browser_live.py -q -s   (les temps mesurés sont affichés)
"""
import uuid

from tests.supabase_live.test_audiences_live import ADMIN, VIP
from tests.supabase_live.test_bar_soiree_browser_live import browser, party, pw, signed_in_page  # noqa: F401
from tests.supabase_live.test_member_admin_live import pytestmark as live  # noqa: F401
from tests.supabase_live.test_rsvp_digest_live import sql

pytestmark = live

# Outils posés dans la page : heure du dernier geste, attente d'un texte à l'écran (dans la fenêtre visible).
TOOLS = """
(() => {
  if (window.__vt) return;
  const now = () => performance.timeOrigin + performance.now();
  window.__vt = { t0: 0 };
  document.addEventListener('pointerdown', () => { window.__vt.t0 = now(); }, { capture: true });
  const shown = (text) => [...document.querySelectorAll('div,span')].some((el) => {
    if (el.childElementCount || el.textContent !== text) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.top >= 0 && r.bottom <= innerHeight;
  });
  // field : la conversation est ouverte (champ de saisie là), pas seulement l'aperçu de la liste.
  window.__vt.until = (text, field) => new Promise((done) => {
    const end = now() + 15000;
    const ok = () => shown(text) && (!field || !!document.querySelector('textarea[aria-label="Message"]'));
    const tick = () => (ok() ? done(now()) : now() > end ? done(-1) : requestAnimationFrame(tick));
    tick();
  });
})();
"""


def watch(page, text, name, field=False):
    page.evaluate(TOOLS)
    page.evaluate(f"([text, field]) => {{ window.__vt['{name}'] = window.__vt.until(text, field); }}", [text, field])


def seen_at(page, name):
    return page.evaluate(f"() => window.__vt['{name}']")


def ids():
    rows = sql(f"select phone, id::text id from public.profiles where phone in ('{ADMIN}', '{VIP}')")
    return {r['phone']: r['id'] for r in rows}


def test_sending_and_receiving_are_instant(browser, party):  # noqa: F811
    sql("insert into public.terms_acceptances (user_id, version) select p.id, (select terms_version from private.moderation_settings "
        f"where id = 1) from public.profiles p where p.phone in ('{ADMIN}', '{VIP}') on conflict do nothing")
    who = ids()
    a, v = who[ADMIN], who[VIP]
    low, high = sorted([a, v])
    sql(f"delete from public.direct_chats where user_a = '{low}' and user_b = '{high}'")
    chat = sql(f"insert into public.direct_chats (user_a, user_b, created_by, status) values ('{low}', '{high}', '{a}', 'active') "
               "returning id::text id")[0]['id']
    # Un long fil (80 messages) : la fin n'est à l'écran que si la conversation s'ouvre en bas.
    sql(f"insert into public.direct_messages (chat_id, user_id, body, created_at) select '{chat}', "
        f"case when i % 2 = 0 then '{a}'::uuid else '{v}'::uuid end, 'Fil de mesure n°' || i, now() - ((90 - i) || ' minutes')::interval "
        "from generate_series(1, 80) i")
    # La garde de la base date chaque message de son insertion (tous à la même heure ici) : on les étale ensuite.
    sql(f"update public.direct_messages set created_at = now() - ((90 - substring(body from '[0-9]+$')::int) || ' minutes')::interval "
        f"where chat_id = '{chat}'")
    vip_role = sql(f"select role from public.profiles where phone = '{VIP}'")[0]['role']
    sql(f"update public.profiles set role = 'member' where phone = '{VIP}'")
    errors: list = []
    contexts = []
    timings = {}
    try:
        actx, ap = signed_in_page(browser, ADMIN, party, chat, errors)
        contexts.append(actx)
        vctx, vp = signed_in_page(browser, VIP, party, chat, errors)
        contexts.append(vctx)
        vp.goto(f'{party}/events/chats/{chat}')
        pw.expect(vp.get_by_text('Fil de mesure n°80', exact=True)).to_be_in_viewport(timeout=20000)

        # Ouverture : en bas du fil.
        ap.goto(f'{party}/events/chats/{chat}')
        pw.expect(ap.get_by_text('Fil de mesure n°80', exact=True)).to_be_in_viewport(timeout=20000)
        field = ap.get_by_label('Message', exact=True)
        pw.expect(field).to_be_editable()

        for i in range(3):
            text = f'Vitesse {i} · {uuid.uuid4().hex[:6]}'
            field.fill(text)
            watch(ap, text, 'bubble')
            watch(vp, text, 'recv')
            ap.get_by_role('button', name='Envoyer', exact=True).click()
            t0 = ap.evaluate('() => window.__vt.t0')
            bubble, recv = seen_at(ap, 'bubble') - t0, seen_at(vp, 'recv') - t0
            timings.setdefault('bulle', []).append(round(bubble))
            timings.setdefault('reçu', []).append(round(recv))
            assert 0 <= bubble < 300, f'bulle à l’écran en {bubble:.0f} ms'
            assert 0 <= recv < 2000, f'reçu chez l’autre en {recv:.0f} ms'
            pw.expect(field).to_have_value('')

        # Deuxième ouverture (liste puis conversation) : depuis la mémoire, tout de suite.
        ap.goto(f'{party}/events/chats')
        row = ap.locator('[aria-label="Toutes les discussions"]:visible').get_by_text('VIP test', exact=True).first
        pw.expect(row).to_be_visible(timeout=20000)
        ap.wait_for_timeout(1500)
        watch(ap, text, 'reopen', field=True)  # le dernier message envoyé, en bas du fil, conversation ouverte
        row.click()
        reopen = seen_at(ap, 'reopen') - ap.evaluate('() => window.__vt.t0')
        timings['2e ouverture'] = [round(reopen)]
        assert 0 <= reopen < 500, f'2e ouverture en {reopen:.0f} ms'

        rows = sql(f"select count(*) n from public.direct_messages where chat_id = '{chat}' and body like 'Vitesse %'")
        assert rows == [{'n': 3}], rows
        assert not errors, errors
        print('\nTemps mesurés (ms) :', timings)
    finally:
        for context in contexts:
            context.close()
        sql(f"update public.profiles set role = '{vip_role}' where phone = '{VIP}'")
        sql(f"delete from public.direct_chats where id = '{chat}'")
