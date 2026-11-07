"""Fin de campagne (base de TEST) : supprime les événements des bots, retire la quarantaine des notifications, remet
terms_enforced à sa valeur d'origine (state.json). Les comptes bots restent (pour relancer).
Usage : BOTS_OUT=<dossier> .venv/bin/python -m tests.bots.cleanup"""
from tests.bots import quarantine
from tests.bots.bench import load_state, save_state
from tests.bots.common import phones_sql, sql


def main() -> None:
    state = load_state()
    gone = sql(f"""delete from public.events e using public.profiles p
                   where p.id = e.created_by and p.phone in {phones_sql()} returning e.title""") or []
    print(f"{len(gone)} événement(s) de bots supprimé(s)")
    sql(f"""delete from public.notifications n using public.profiles p where p.id = n.user_id and p.phone in {phones_sql()}""")
    sql(f"""delete from public.content_reports r using public.profiles p where p.id = r.reporter_id and p.phone in {phones_sql()}""")
    try:
        held = quarantine.held()
    except RuntimeError:  # quarantaine déjà retirée
        held = []
    print("notifications retenues pendant la campagne :", held)
    save_state(quarantine_held=held)
    quarantine.remove()
    was = state.get("terms_enforced_was")
    if was is not None:
        sql(f"update private.moderation_settings set terms_enforced = {'true' if was else 'false'} where id = 1")
    now = sql("select terms_enforced from private.moderation_settings where id = 1")[0]["terms_enforced"]
    print(f"terms_enforced remis à {now} (origine : {was})")
    save_state(cleaned=True, terms_enforced_now=now)


if __name__ == "__main__":
    main()
