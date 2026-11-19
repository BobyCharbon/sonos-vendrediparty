"""Données de démonstration des captures App Store, sur la base de TEST seulement (jamais la production).

    .venv/bin/python tools/appstore_visuels/demo_data.py create <dossier des images de demo_assets.py>
    .venv/bin/python tools/appstore_visuels/demo_data.py clean

Personnes inventées (aucune vraie personne) : la spectatrice « Léa » se connecte avec le numéro de test 41790000210
(code fixe 123456) ; les autres sont des comptes sans téléphone, repérés par leur adresse visuels-…@demo.invalid.
Tout est écrit dans UNE transaction qui efface à la fin les notifications qu'elle a créées : aucun vrai membre de la
base de test n'est prévenu. `clean` retire tout (événements, groupes, discussions, photos, comptes).
"""
import json
import pathlib
import sys
import time
import urllib.request

import httpx

REF = "ewromqfsmcqsthftyhzm"  # base de TEST
URL = f"https://{REF}.supabase.co"
KEY = (pathlib.Path.home() / ".config/supabase-claude/test-publishable-key").read_text().strip()
TOKEN = (pathlib.Path.home() / ".config/supabase-claude/token").read_text().strip()
VIEWER_PHONE = "41790000210"
DOMAIN = "demo.invalid"

# clé → (prénom, nom, surnom)
PEOPLE = {
    "lea": ("Léa", "Martin", "Léa"), "hugo": ("Hugo", "Bernard", "Hugo"), "ines": ("Inès", "Moreau", "Inès"),
    "tom": ("Tom", "Girard", "Tom"), "zoe": ("Zoé", "Lambert", "Zoé"), "nathan": ("Nathan", "Roux", "Nathan"),
    "camille": ("Camille", "Fontaine", "Camille"), "yanis": ("Yanis", "Morel", "Yanis"),
    "chloe": ("Chloé", "Dubois", "Chloé"), "malik": ("Malik", "Fournier", "Malik"), "sarah": ("Sarah", "Leroy", "Sarah"),
    "jules": ("Jules", "Perrin", "Jules"),
}


def sql(query: str):
    req = urllib.request.Request(f"https://api.supabase.com/v1/projects/{REF}/database/query",
                                 data=json.dumps({"query": query}).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                                          "User-Agent": "party-claude"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"SQL refusé : {e.read().decode()[:3000]}")


def q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def login(phone: str) -> tuple[str, str]:
    base = {"apikey": KEY, "Content-Type": "application/json"}
    for _ in range(4):
        r = httpx.post(f"{URL}/auth/v1/otp", headers=base, json={"phone": phone}, timeout=30)
        if r.status_code != 429:
            break
        time.sleep(31)
    r.raise_for_status()
    r = httpx.post(f"{URL}/auth/v1/verify", headers=base, json={"type": "sms", "phone": phone, "token": "123456"}, timeout=30)
    r.raise_for_status()
    return r.json()["user"]["id"], r.json()["access_token"]


def upload(jwt: str, bucket: str, path: str, file: pathlib.Path, ctype: str):
    r = httpx.post(f"{URL}/storage/v1/object/{bucket}/{path}", content=file.read_bytes(), timeout=60,
                   headers={"apikey": KEY, "Authorization": f"Bearer {jwt}", "Content-Type": ctype})
    assert r.status_code in (200, 201) or "exists" in r.text, r.text  # déjà là : on le garde


COVER_NAMES = ("disco", "raclette", "karaoke", "chalet", "jeux")


def cover_url(jwt: str, lea: str, assets: pathlib.Path, name: str) -> str:
    path = f"{lea}/visuels-cover-{name}.jpg"
    upload(jwt, "profile-photos", path, assets / f"cover-{name}.jpg", "image/jpeg")
    r = httpx.post(f"{URL}/storage/v1/object/sign/profile-photos/{path}", json={"expiresIn": 7 * 24 * 3600}, timeout=30,
                   headers={"apikey": KEY, "Authorization": f"Bearer {jwt}"})
    r.raise_for_status()
    return f"{URL}/storage/v1{r.json()['signedURL']}"


def local(day: str, hm: str) -> str:
    """Heure de Suisse (novembre à mars : UTC+1) → horodatage SQL."""
    return f"timestamptz '{day} {hm}:00+01'"


def create(assets: pathlib.Path):
    lea, jwt = login(VIEWER_PHONE)
    ids = {"lea": lea}
    for k in PEOPLE:
        if k != "lea":
            ids[k] = sql(f"select gen_random_uuid() id")[0]["id"]
    # Photo de profil de Léa seulement : la base n'accepte qu'un fichier du dossier de la personne (guard_profile), et les
    # comptes inventés ne se connectent pas ; ils gardent leurs initiales.
    upload(jwt, "profile-photos", f"{lea}/visuels-lea.png", assets / "avatar-lea.png", "image/png")
    # Couvertures : la fiche n'affiche qu'une adresse https ; elles sont donc rangées dans le dossier de Léa et servies par un
    # lien signé de la base de TEST (7 jours), le temps des captures. `clean` les efface.
    covers = {name: cover_url(jwt, lea, assets, name) for name in COVER_NAMES}
    u = ids
    P = lambda k: q(u[k])  # noqa: E731
    out = ["begin;"]
    for k, (first, last, nick) in PEOPLE.items():
        if k != "lea":
            out.append(f"""insert into auth.users (id, instance_id, aud, role, email, email_confirmed_at, raw_app_meta_data,
              raw_user_meta_data, created_at, updated_at) values ({P(k)}, '00000000-0000-0000-0000-000000000000',
              'authenticated', 'authenticated', 'visuels-{k}@{DOMAIN}', now(), '{{"provider":"email","providers":["email"]}}',
              '{{"visuels_appstore":true}}', now(), now());""")
        out.append(f"""insert into terms_acceptances (user_id, version) select {P(k)}, terms_version
              from private.moderation_settings where id = 1 on conflict do nothing;""")
        out.append(f"""update profiles set first_name={q(first)}, last_name={q(last)}, display_name={q(nick)},
              avatar_url={q(f'{lea}/visuels-lea.png') if k == 'lea' else 'null'}, role={q('member' if k == 'lea' else 'basic')} where id={P(k)};""")

    def event(key, title, desc, start, end, place, addr, cover, by, cat, mode="fixed", deadline="null"):
        out.append(f"""insert into events (id, title, description, cover_url, category_id, created_by, status, date_mode,
              starts_at, ends_at, location_name, location_address, visibility, notify_on_publish, reminders, allow_maybe,
              poll_deadline) values ({q(ids[key])}, {q(title)}, {q(desc)}, {q(covers[cover])},
              (select id from categories where name={q(cat)} limit 1), {P(by)}, 'published', '{mode}', {start or 'null'},
              {end or 'null'}, {q(place)}, {q(addr)}, 'invited', false, '{{}}', true, {deadline});""")

    for k in ("e_disco", "e_raclette", "e_jeux", "e_karaoke", "e_chalet", "g_lucioles", "g_coloc", "g_foot", "g_chorale",
              "d_hugo", "d_ines"):
        ids[k] = sql("select gen_random_uuid() id")[0]["id"]
    event("e_disco", "Anniversaire de Zoé · soirée disco",
          "Ressors tes paillettes : Zoé fête ses 30 ans ! Piste de danse, gâteau à minuit et photomaton. Dress code : disco 🪩",
          local("2026-11-28", "20:00"), local("2026-11-29", "02:00"), "La Fabrique", "Rue de la Fabrique 8, 1003 Lausanne",
          "disco", "zoe", "Soirée")
    event("e_raclette", "Raclette chez Inès", "On sort le four à raclette ! Chacun amène un petit quelque chose 🧀",
          local("2026-11-20", "19:30"), local("2026-11-20", "23:30"), "Chez Inès", "Chemin des Lilas 3, 1205 Genève",
          "raclette", "ines", "Resto")
    event("e_jeux", "Soirée jeux de société", "Jeux de plateau, jeux d'ambiance et tournoi de cartes. Débutants bienvenus 🎲",
          local("2026-11-25", "19:00"), local("2026-11-25", "23:00"), "Le Comptoir à jeux", "Rue du Marché 14, 2000 Neuchâtel",
          "jeux", "hugo", "Activité")
    event("e_karaoke", "Karaoké de décembre", "Échauffe ta voix : salle privée réservée pour toute la bande 🎤",
          local("2026-12-04", "20:30"), local("2026-12-04", "23:59"), "Studio Mélodie", "Avenue de la Gare 21, 1950 Sion",
          "karaoke", "nathan", "Soirée")
    event("e_chalet", "Week-end au chalet", "Deux jours à la montagne : luge, fondue et soirées au coin du feu. Vote pour tes dates !",
          None, None, "Chalet des Mélèzes", "Route des Mayens 5, 1936 Verbier", "chalet", "tom", "Voyage", mode="poll",
          deadline=local("2026-11-30", "20:00"))
    rsvps = {"e_disco": ({"zoe", "lea", "hugo", "ines", "tom", "nathan", "camille", "yanis", "chloe", "malik"}, {"sarah", "jules"}),
             "e_raclette": ({"ines", "lea", "sarah", "hugo", "chloe", "tom"}, {"camille"}),
             "e_jeux": ({"hugo", "tom", "yanis", "camille"}, {"malik"}),
             "e_karaoke": ({"nathan", "zoe", "chloe", "malik"}, {"lea", "jules"}),
             "e_chalet": (set(), set())}
    for e, (yes, maybe) in rsvps.items():
        for k in PEOPLE:
            out.append(f"insert into event_invites (event_id, user_id, invited_by) values ({P(e)}, {P(k)}, {P(k)}) on conflict do nothing;")
        for k in yes | maybe:
            out.append(f"insert into rsvps (event_id, user_id, status) values ({P(e)}, {P(k)}, '{'yes' if k in yes else 'maybe'}') on conflict do nothing;")
    for i, (label, who) in enumerate([("Gâteau d'anniversaire", "lea"), ("Ballons et guirlandes", "ines"), ("Playlist", "hugo"),
                                       ("Jus et softs", "camille"), ("Photomaton", None), ("Chips et biscuits salés", None)]):
        out.append(f"insert into bring_items (event_id, label, claimed_by, sort, added_by, quantity) values ({P('e_disco')}, "
                   f"{q(label)}, {P(who) if who else 'null'}, {i}, {P('zoe')}, null);")
    for day, votes in (("2027-01-16", {"tom": "yes", "hugo": "yes", "ines": "if_needed", "zoe": "yes"}),
                       ("2027-01-23", {"tom": "yes", "hugo": "no", "ines": "yes", "zoe": "yes", "nathan": "yes"}),
                       ("2027-01-30", {"tom": "if_needed", "ines": "yes", "nathan": "no"})):
        out.append(f"""with o as (insert into date_options (event_id, starts_at, ends_at, proposed_by) values ({P('e_chalet')},
              {local(day, '10:00')}, {local(day, '10:00')} + interval '2 days', {P('tom')}) returning id)
              insert into date_votes (option_id, user_id, vote) select o.id, v.u::uuid, v.vote::date_vote from o,
              (values {', '.join(f'({P(k)}, {q(v)})' for k, v in votes.items())}) v(u, vote);""")
    # Groupes (emoji et couleur de la liste fermée) et leurs messages.
    groups = {"g_lucioles": ("Les Lucioles", "🪩", "pink", "zoe", ["lea", "hugo", "ines", "tom", "nathan", "camille", "chloe"]),
              "g_coloc": ("Coloc du 12", "🏡", "mint", "sarah", ["lea", "ines"]),
              "g_foot": ("Foot du jeudi", "⚽", "sky", "malik", ["lea", "yanis", "jules", "tom", "nathan"]),
              "g_chorale": ("Chorale du lundi", "🎤", "lavender", "chloe", ["lea", "camille", "sarah"])}
    for g, (name, emoji, color, by, members) in groups.items():
        out.append(f"insert into member_groups (id, name, created_by, emoji, color) values ({P(g)}, {q(name)}, {P(by)}, {q(emoji)}, {q(color)});")
        for m in [by] + members:
            out.append(f"insert into member_group_members (group_id, user_id) values ({P(g)}, {P(m)}) on conflict do nothing;")
    msgs = [("g_lucioles", "zoe", "2026-11-19", "08:02", "Coucou la bande ! 🎉 Samedi 28, c'est ma soirée disco : vous venez ?"),
            ("g_lucioles", "hugo", "2026-11-19", "08:05", "Évidemment ! Je m'occupe de la playlist 🎶"),
            ("g_lucioles", "ines", "2026-11-19", "08:07", "Je ramène des ballons et des guirlandes ✨"),
            ("g_lucioles", "tom", "2026-11-19", "08:15", "Quelqu'un passe par Renens ? Il me reste 2 places dans la voiture 🚗"),
            ("g_lucioles", "lea", "2026-11-19", "08:21", "Moi ! Et je fais le gâteau 🎂"),
            ("g_lucioles", "zoe", "2026-11-19", "08:24", "Vous êtes les meilleurs 🥹"),
            ("g_lucioles", "nathan", "2026-11-19", "08:30", "Dress code paillettes obligatoire 😎"),
            ("g_lucioles", "chloe", "2026-11-19", "09:12", "J'ai déjà trouvé ma tenue 🪩"),
            ("g_lucioles", "camille", "2026-11-19", "09:31", "Trop hâte ! On répète la choré vendredi ? 💃"),
            ("g_coloc", "sarah", "2026-11-19", "09:05", "Qui a pris la dernière part de tarte ? 😇"),
            ("g_foot", "malik", "2026-11-19", "08:48", "Ce soir 19 h au terrain du parc, on est 9 ⚽"),
            ("g_chorale", "chloe", "2026-11-18", "19:40", "Répétition lundi : on attaque le nouveau morceau 🎶")]
    for g, who, day, hm, body in msgs:
        out.append(f"insert into group_messages (group_id, user_id, body) values ({P(g)}, {P(who)}, {q(body)});")
        # La base date le message à l'envoi : on lui redonne son heure (après l'insertion, comme une conversation passée).
        out.append(f"update group_messages set created_at = {local(day, hm)} where group_id = {P(g)} and body = {q(body)};")
    for d, k in (("d_hugo", "hugo"), ("d_ines", "ines")):
        a, b = sorted([u["lea"], u[k]])
        out.append(f"insert into direct_chats (id, user_a, user_b, created_by, status) values ({P(d)}, {q(a)}, {q(b)}, {P(k)}, 'active');")
    for d, who, day, hm, body in (("d_hugo", "hugo", "2026-11-19", "09:25", "Tu passes me prendre samedi ? 🚗"),
                                  ("d_ines", "lea", "2026-11-18", "21:14", "Je ramène le fromage pour vendredi 🧀"),
                                  ("d_ines", "ines", "2026-11-18", "21:16", "Parfait, merci ! 🙌")):
        out.append(f"insert into direct_messages (chat_id, user_id, body) values ({P(d)}, {P(who)}, {q(body)});")
        out.append(f"update direct_messages set created_at = {local(day, hm)} where chat_id = {P(d)} and body = {q(body)};")
    for who, hm, body, ann in (("zoe", "07:40", "Rendez-vous à 20 h, entrée par la cour 🪩", True),
                               ("tom", "07:55", "Je peux prendre 2 personnes depuis Renens 🚗", False),
                               ("ines", "08:10", "Qui s'occupe de la déco de la table ?", False)):
        out.append(f"insert into messages (event_id, user_id, body, created_at, announcement, pinned) values ({P('e_disco')}, "
                   f"{P(who)}, {q(body)}, {local('2026-11-19', hm)}, {str(ann).lower()}, {str(ann).lower()});")
    # La soirée disco et le karaoké sont des événements des Lucioles (page du groupe : « Prochains événements »).
    for e in ("e_disco", "e_karaoke"):
        out.append(f"insert into event_groups (event_id, group_id, status, announce) values ({P(e)}, {P('g_lucioles')}, 'approved', false);")
    # Réponses données ces derniers jours (pas toutes à l'instant de la création).
    out.append("update rsvps r set updated_at = timestamptz '2026-11-12 18:00+01' + (abs(hashtext(r.user_id::text)) % 140) "
               f"* interval '1 hour' where r.event_id in ({', '.join(P(e) for e in rsvps)});")
    out.append(read_state(ids))
    out.append("delete from notifications where created_at = now();")  # personne n'est prévenu
    out.append("commit;")
    sql("\n".join(out))
    extras(ids, jwt, assets)
    state = pathlib.Path(__file__).with_name(".demo-state.json")
    state.write_text(json.dumps({"ids": ids, "covers": covers}, indent=1))
    print(json.dumps({"ids": ids, "covers": covers}))


# Pot commun du week-end au chalet : (titre, catégorie, montant en centimes, payé par).
POT = [("Location du chalet", "lodging", 64000, "tom"), ("Courses du week-end", "food", 18640, "lea"),
       ("Essence aller-retour", "transport", 7200, "hugo"), ("Luges et bonnets", "leisure", 9600, "ines")]


def extras(ids: dict, jwt: str, assets: pathlib.Path):
    """Billet QR (raclette), photo du groupe « Coloc du 12 » (gérée par Léa), discussion de la soirée disco, pot commun."""
    P = lambda k: q(ids[k])  # noqa: E731
    lea = ids["lea"]
    sql(f"update member_groups set created_by = {P('lea')} where id = {P('g_coloc')};"
        f"insert into member_group_members (group_id, user_id) values ({P('g_coloc')}, {P('sarah')}) on conflict do nothing;")
    photo = f"{ids['g_coloc']}/visuels-coloc.jpg"
    upload(jwt, "group-photos", photo, assets / "cover-coloc.jpg", "image/jpeg")
    out = ["begin;", f"update member_groups set photo_path = {q(photo)} where id = {P('g_coloc')};",
           f"update events set tickets_enabled = true where id = {P('e_raclette')};",
           f"select private.ensure_ticket({P('e_raclette')}, {P('lea')});",
           f"update event_tickets set issued_at = {local('2026-11-18', '20:15')}, issued_by = {P('ines')} "
           f"where event_id = {P('e_raclette')} and user_id = {P('lea')};"]
    chat = [("hugo", "08:20", "J'ai fini la playlist : 4 heures de disco 🕺"), ("lea", "08:26", "Le gâteau sera au chocolat 🎂"),
            ("chloe", "08:33", "Je prends des paillettes pour tout le monde ✨"), ("zoe", "08:41", "Vous êtes trop forts, j'ai hâte 🥹")]
    for who, hm, body in chat:
        out.append(f"insert into messages (event_id, user_id, body) values ({P('e_disco')}, {P(who)}, {q(body)});")
        out.append(f"update messages set created_at = {local('2026-11-19', hm)} where event_id = {P('e_disco')} and body = {q(body)};")
    out.append(f"""with g as (insert into tc_groups (name, emoji, currency, created_by) values ('Week-end au chalet', '🏔️', 'CHF',
                 {P('tom')}) returning id)
               insert into tc_members (group_id, user_id, name) select g.id, m.u::uuid, m.n from g,
               (values {', '.join(f'({P(k)}, {q(PEOPLE[k][2])})' for k in ('lea', 'tom', 'hugo', 'ines', 'zoe'))}) m(u, n);""")
    for title, cat, cents, by in POT:
        out.append(f"""with g as (select id from tc_groups where created_by = {P('tom')} and name = 'Week-end au chalet'),
               e as (insert into tc_expenses (group_id, title, amount_cents, paid_by, category, created_by, spent_on)
                 select g.id, {q(title)}, {cents}, (select id from tc_members where group_id = g.id and user_id = {P(by)}), {q(cat)},
                 {P(by)}, date '2026-11-15' from g returning id, group_id)
               insert into tc_shares (expense_id, member_id, weight, amount_cents)
               select e.id, m.id, 1, {cents} / 5 from e join tc_members m on m.group_id = e.group_id;""")
    out += ["delete from notifications where created_at = now();", "commit;"]
    sql("\n".join(out))


def read_state(ids: dict) -> str:
    """Léa a tout lu, sauf le dernier message des Lucioles et celui de Hugo (pastilles « non lu » modestes) ;
    la discussion de Membres Vendredi Party (messages des recettes de la base de TEST) est lue aussi."""
    lea, read = q(ids["lea"]), local("2026-11-19", "09:40")
    lucioles = local("2026-11-19", "09:20")
    groups = [(q(ids[g]), read) for g in ("g_coloc", "g_foot", "g_chorale")] + [(q(ids["g_lucioles"]), lucioles)]
    rows = ", ".join(f"({g}, {lea}, {t})" for g, t in groups)
    return f"""
      insert into group_chat_settings (group_id, user_id, read_at) values {rows}
        on conflict (group_id, user_id) do update set read_at = excluded.read_at;
      insert into group_chat_settings (group_id, user_id, read_at) select id, {lea}, {read} from member_groups
        where system_key is not null on conflict (group_id, user_id) do update set read_at = excluded.read_at;
      insert into direct_chat_settings (chat_id, user_id, read_at) values ({q(ids['d_ines'])}, {lea}, {read}),
        ({q(ids['d_hugo'])}, {lea}, {local('2026-11-19', '09:00')})
        on conflict (chat_id, user_id) do update set read_at = excluded.read_at;
      insert into chat_list_state (user_id, kind, chat_id, read_at) values ({lea}, 'direct', {q(ids['d_ines'])}, {read}),
        ({lea}, 'direct', {q(ids['d_hugo'])}, {local('2026-11-19', '09:00')}), ({lea}, 'event', {q(ids['e_disco'])}, {read})
        on conflict (user_id, kind, chat_id) do update set read_at = excluded.read_at;
      insert into event_chat_prefs (event_id, user_id, last_read_at) values ({q(ids['e_disco'])}, {lea}, {read})
        on conflict (event_id, user_id) do update set last_read_at = excluded.last_read_at;"""


def fix():
    """Rejoue l'heure des messages et l'état « lu » sur des données déjà créées."""
    ids = json.loads(pathlib.Path(__file__).with_name(".demo-state.json").read_text())["ids"]
    sql("begin;" + read_state(ids) + "\ndelete from notifications where created_at = now(); commit;")


def clean():
    demo = "(select id from auth.users where email like '%@" + DOMAIN + "' or phone = '" + VIEWER_PHONE + "')"
    lea = sql(f"select id from auth.users where phone = '{VIEWER_PHONE}'")
    if lea:
        _, jwt = login(VIEWER_PHONE)
        # Toutes les images de démonstration du dossier de Léa (y compris d'anciennes versions : une par personne).
        names = [f"{lea[0]['id']}/visuels-{k}.png" for k in PEOPLE] + [f"{lea[0]['id']}/visuels-cover-{n}.jpg" for n in COVER_NAMES]
        httpx.request("DELETE", f"{URL}/storage/v1/object/profile-photos", json={"prefixes": names}, timeout=60,
                      headers={"apikey": KEY, "Authorization": f"Bearer {jwt}"})
        state = pathlib.Path(__file__).with_name(".demo-state.json")
        if state.exists():  # photo du groupe « Coloc du 12 » (Léa le gère)
            gid = json.loads(state.read_text())["ids"]["g_coloc"]
            httpx.request("DELETE", f"{URL}/storage/v1/object/group-photos", json={"prefixes": [f"{gid}/visuels-coloc.jpg"]},
                          timeout=60, headers={"apikey": KEY, "Authorization": f"Bearer {jwt}"})
    sql(f"""begin;
      delete from events where created_by in {demo};
      delete from member_groups where created_by in {demo};
      delete from direct_chats where user_a in {demo} or user_b in {demo};
      delete from tc_expenses where group_id in (select id from tc_groups where created_by in {demo});
      delete from tc_groups where created_by in {demo};
      delete from auth.users where id in {demo};
      delete from notifications where created_at = now();
      commit;""")
    left = sql(f"select count(*) n from auth.users where email like '%@{DOMAIN}' or phone = '{VIEWER_PHONE}'")
    print("reste", left)


if __name__ == "__main__":
    if sys.argv[1] == "create":
        create(pathlib.Path(sys.argv[2]))
    elif sys.argv[1] == "fix":
        fix()
    elif sys.argv[1] == "clean":
        clean()
