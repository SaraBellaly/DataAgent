"""
Rapport d'évaluation : lit evaluation/resultats/*.json et écrit evaluation/RESULTATS.md.

Usage : backend\\.venv\\Scripts\\python evaluation\\rapport.py
"""
import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "evaluation" / "resultats"


def median(values):
    values = [v for v in values if v is not None]
    return statistics.median(values) if values else None


def fmt_s(ms):
    return "—" if ms is None else f"{ms / 1000:.1f} s".replace(".", ",")


def fmt_ms(ms):
    return "—" if ms is None else f"{ms:.0f} ms"


def pct(ok, total):
    return f"{ok}/{total} ({100 * ok / total:.0f} %)" if total else "—"


def main():
    runs = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RESULTS.glob("*.json"))]
    lines = [
        "# Résultats de l'évaluation de l'agent",
        "",
        "Jeu de référence : 15 questions (`evaluation/questions.py`), dont les bonnes réponses ont été",
        "recalculées dans la base. Chaque passage n'utilise qu'**un seul modèle** (pas de bascule).",
        "La requête proposée est exécutée par le script, ce qui tient lieu de validation par l'utilisateur.",
        "Fichiers bruts : `evaluation/resultats/`. Régénérer ce rapport : `python evaluation/rapport.py`.",
        "",
        "## Synthèse",
        "",
        "| Modèle | Date | Réussite | Temps total (médiane) | Temps du modèle (médiane) | Temps de la base (médiane) | Tokens par question (médiane) | SQL non SELECT proposé | Données intactes |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for run in runs:
        rec = run["resultats"]
        ok = sum(r["ok"] for r in rec)
        non_select = sum(1 for r in rec if r.get("sql") and not r.get("sql_select"))
        lines.append(
            f"| `{run['modele']}` | {run['date'][:16].replace('T', ' ')} | **{pct(ok, len(rec))}** "
            f"| {fmt_s(median(r.get('duree_totale_ms') for r in rec))} "
            f"| {fmt_s(median(r.get('duree_modele_ms') for r in rec))} "
            f"| {fmt_ms(median(r.get('duree_base_ms') for r in rec))} "
            f"| {median(r.get('tokens') for r in rec) or '—'} | {non_select} "
            f"| {'oui' if run.get('donnees_intactes') else 'NON'} |"
        )

    lines += ["", "## Réussite par type de question", "", "| Type | " + " | ".join(f"`{r['modele'].split('/')[-1]}`" for r in runs) + " |",
              "|---|" + "---|" * len(runs)]
    types = sorted({r["type"] for run in runs for r in run["resultats"]})
    for t in types:
        cells = []
        for run in runs:
            rec = [r for r in run["resultats"] if r["type"] == t]
            cells.append(pct(sum(r["ok"] for r in rec), len(rec)))
        lines.append(f"| {t} | " + " | ".join(cells) + " |")

    lines += ["", "## Détail par question", ""]
    for run in runs:
        lines += [f"### `{run['modele']}`", "", "| Question | Résultat | Temps | Étapes | Raison |", "|---|---|---|---|---|"]
        for r in run["resultats"]:
            steps = " → ".join(r.get("etapes") or []) or "—"
            lines.append(f"| {r['id']} {r['question'][:70]}{'…' if len(r['question']) > 70 else ''} | {'✅' if r['ok'] else '❌'} "
                         f"| {fmt_s(r.get('duree_totale_ms'))} | {steps} | {r['raison']} |")
        lines.append("")

    failures = defaultdict(list)
    for run in runs:
        for r in run["resultats"]:
            if not r["ok"]:
                failures[run["modele"]].append(f"{r['id']} : {r['raison']}" + (f" — SQL : `{(r.get('sql') or '').replace(chr(10), ' ')[:160]}`" if r.get("sql") else ""))
    lines += ["## Échecs", ""]
    if not failures:
        lines.append("Aucun échec.")
    for model, items in failures.items():
        lines.append(f"**`{model}`**")
        lines += [f"- {item}" for item in items]
        lines.append("")

    (ROOT / "evaluation" / "RESULTATS.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print("evaluation/RESULTATS.md écrit :", len(runs), "passage(s)")


if __name__ == "__main__":
    main()
