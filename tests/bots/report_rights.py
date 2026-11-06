"""Tableau « droit × attendu × observé » (markdown) à partir de rights.json. Usage : BOTS_OUT=… python -m tests.bots.report_rights"""
import json

from tests.bots.bench import OUT


def verdict(r: dict) -> str:
    if r["api"] is True and not r["has"]:
        return "🔴 contournement (la base accepte sans le droit)"
    if r["api"] is False and r["has"]:
        return "🟠 refusé alors que le droit est donné"
    if r["ui"] is True and not r["has"]:
        return "🟡 écran : bouton visible sans le droit (la base refuse)"
    if r["ui"] is False and r["has"]:
        return "🟠 écran : bouton absent avec le droit"
    return "✅"


def mark(v) -> str:
    return "—" if v is None else ("oui" if v else "non")


def main() -> None:
    rows = json.loads((OUT / "rights.json").read_text())
    print("| Droit / cas | Bot | Attendu | Écran (bouton) | Base (API REST, jeton du bot) | Verdict | Détail |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['perm']} | {'avec' if r['has'] else 'sans'} | {'permis' if r['has'] else 'refusé'} | {mark(r['ui'])} | "
              f"{mark(r['api'])} | {verdict(r)} | {r['detail'][:110].replace('|', '/')} |")


if __name__ == "__main__":
    main()
