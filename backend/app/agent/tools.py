"""
Outils de l'agent, tous en lecture seule avec le rôle analyst_ro (fiche, Q5) :

- read_schema          : tables, vues et colonnes du schéma immo, avec leurs commentaires ;
- find_commune         : code INSEE d'une commune à partir de son nom (évite d'inventer un code) ;
- costly_queries       : requêtes les plus coûteuses (pg_stat_statements) ;
- explain_select       : plan d'exécution (EXPLAIN, sans exécuter la requête par défaut) ;
- execute_select       : exécution d'un SELECT vérifié. Le modèle ne peut PAS l'appeler :
                         seule la route de validation, déclenchée par l'utilisateur, l'utilise.

Chaque requête vérifiée passe par sql_guard.check_select, puis s'exécute dans une transaction
READ ONLY, annulée à la fin, sous le statement_timeout de 30 s d'analyst_ro.
"""
import re
import time
import unicodedata
from functools import lru_cache
from typing import Any

import psycopg
from psycopg import errors, sql as pgsql

from app.agent.sql_guard import CheckedSql, check_select
from app.db.connection import pool_ro

ROLE_TIMEOUT_MS = 30_000


class ToolError(Exception):
    """Erreur d'outil présentable au modèle et à l'utilisateur (aucun détail interne)."""


def _db_error(exc: psycopg.Error) -> ToolError:
    if isinstance(exc, errors.QueryCanceled):
        return ToolError("Requête annulée : délai maximal dépassé (30 s pour analyst_ro). Consultez le plan "
                         "d'exécution, ou demandez à l'agent une version plus légère de la requête.")
    if isinstance(exc, errors.InsufficientPrivilege):
        return ToolError("Accès refusé par la base (rôle en lecture seule).")
    diag = getattr(exc, "diag", None)
    message = (diag.message_primary if diag and diag.message_primary else str(exc)).strip()
    hint = diag.message_hint if diag and diag.message_hint else None
    return ToolError(f"Erreur PostgreSQL : {message}" + (f" (indice : {hint})" if hint else ""))


def _read_only(conn: psycopg.Connection, timeout_ms: int | None) -> None:
    conn.execute("SET TRANSACTION READ ONLY")
    if timeout_ms is not None:
        # Jamais au-delà de la limite du rôle
        conn.execute(pgsql.SQL("SET LOCAL statement_timeout = {}").format(
            pgsql.Literal(f"{min(timeout_ms, ROLE_TIMEOUT_MS)}ms")))


# ---------------------------------------------------------------------------
# Schéma
# ---------------------------------------------------------------------------
_SCHEMA_SQL = """
SELECT c.relname,
       CASE c.relkind WHEN 'r' THEN 'table' WHEN 'v' THEN 'vue' WHEN 'm' THEN 'vue matérialisée' END,
       obj_description(c.oid, 'pg_class'),
       a.attname, format_type(a.atttypid, a.atttypmod), col_description(c.oid, a.attnum)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
WHERE n.nspname = 'immo' AND c.relkind IN ('r', 'v', 'm') AND has_table_privilege(c.oid, 'SELECT')
ORDER BY c.relkind DESC, c.relname, a.attnum
"""


_INDEXES_SQL = """
SELECT tablename, indexname, regexp_replace(indexdef, '^.* USING ', '')
FROM pg_indexes WHERE schemaname = 'immo' ORDER BY tablename, indexname
"""


@lru_cache(maxsize=1)
def _schema_rows() -> tuple[tuple, ...]:
    with pool_ro.connection() as conn:
        _read_only(conn, 5_000)
        rows = tuple(conn.execute(_SCHEMA_SQL).fetchall())
        conn.rollback()
    return rows


def _index_rows() -> list[tuple]:
    """Non mis en cache : un index validé et créé par un DBA doit apparaître tout de suite."""
    with pool_ro.connection() as conn:
        _read_only(conn, 5_000)
        rows = conn.execute(_INDEXES_SQL).fetchall()
        conn.rollback()
    return rows


def allowed_relations() -> frozenset[str]:
    return frozenset(r[0] for r in _schema_rows())


_LOT_COLUMN = re.compile(r"^lot([1-5])_(numero|surface_carrez)$")


def read_schema() -> str:
    """Description compacte (une ligne par colonne) pour limiter les tokens envoyés au modèle.
    Les colonnes lot1_… à lot5_… de DVF sont regroupées en une ligne."""
    lines: list[str] = []
    current = None
    lots_done: set[str] = set()
    for rel, kind, rel_comment, col, col_type, col_comment in _schema_rows():
        if rel != current:
            current = rel
            lines.append(f"\n## immo.{rel} ({kind})" + (f" : {rel_comment[:300]}" if rel_comment else ""))
        lot = _LOT_COLUMN.match(col)
        if lot:
            if lot.group(2) not in lots_done:
                lots_done.add(lot.group(2))
                lines.append(f"- lot1_{lot.group(2)} … lot5_{lot.group(2)} {col_type}")
            continue
        lines.append(f"- {col} {col_type}" + (f" : {col_comment[:120]}" if col_comment else ""))
    # Index existants : évite de recommander un index déjà présent
    lines.append("\n## Index existants (ne pas les recommander à nouveau)")
    lines += [f"- {table}.{name} : {definition}" for table, name, definition in _index_rows()]
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Communes
# ---------------------------------------------------------------------------
def _ncc(nom: str) -> str:
    """Forme du champ ncc de l'INSEE : majuscules sans accents, tirets et apostrophes en espaces."""
    decomposed = unicodedata.normalize("NFKD", nom)
    ascii_only = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"[\s\-'’]+", " ", ascii_only).strip().upper()


def find_commune(nom: str, limite: int = 10) -> list[dict[str, Any]]:
    nom = (nom or "").strip()
    if len(nom) < 2:
        raise ToolError("Nom de commune trop court.")
    with pool_ro.connection() as conn:
        _read_only(conn, 5_000)
        # Correspondance exacte d'abord, puis par inclusion ; les plus peuplées en premier
        rows = conn.execute(
            "SELECT code_insee, typecom, libelle, dep, pmun FROM immo.insee_communes "
            "WHERE ncc ILIKE %(motif)s OR libelle ILIKE %(motif_libelle)s "
            "ORDER BY (ncc = %(exact)s) DESC, pmun DESC NULLS LAST LIMIT %(limite)s",
            {"motif": f"%{_ncc(nom)}%", "motif_libelle": f"%{nom}%", "exact": _ncc(nom),
             "limite": max(1, min(limite, 20))},
        ).fetchall()
        conn.rollback()
    return [{"code_insee": r[0], "type": r[1], "libelle": r[2], "departement": r[3], "population": r[4]}
            for r in rows]


# ---------------------------------------------------------------------------
# pg_stat_statements
# ---------------------------------------------------------------------------
def costly_queries(limite: int = 10, tri: str = "total") -> list[dict[str, Any]]:
    order = "mean_exec_time" if tri == "moyenne" else "total_exec_time"
    with pool_ro.connection() as conn:
        _read_only(conn, 5_000)
        rows = conn.execute(
            pgsql.SQL(
                "SELECT left(regexp_replace(query, '\\s+', ' ', 'g'), 400), calls, "
                "round(total_exec_time::numeric, 1), round(mean_exec_time::numeric, 1), rows "
                "FROM public.pg_stat_statements "
                "WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database()) "
                # Les requêtes de l'application (comptes, sessions, historique) ne sont jamais
                # montrées au modèle : analyst_ro ne doit rien révéler du schéma app (fiche, Q5 et Q15)
                "  AND userid <> 'app_agent'::regrole AND query !~* '\\mapp\\.' "
                "  AND query NOT ILIKE '%%pg_stat_statements%%' AND query !~* '^\\s*(SET|SHOW|BEGIN|COMMIT|ROLLBACK)' "
                "ORDER BY {} DESC LIMIT %s"
            ).format(pgsql.Identifier(order)),
            (max(1, min(limite, 20)),),
        ).fetchall()
        conn.rollback()
    return [{"requete": r[0], "appels": r[1], "temps_total_ms": float(r[2]), "temps_moyen_ms": float(r[3]),
             "lignes": r[4]} for r in rows]


# ---------------------------------------------------------------------------
# EXPLAIN et exécution d'un SELECT vérifié
# ---------------------------------------------------------------------------
def check(sql: str) -> CheckedSql:
    return check_select(sql, allowed_relations())


_PARAMETER = re.compile(r"\$\d+")


def explain_select(sql: str, analyze: bool = False, timeout_ms: int | None = None) -> str:
    """Plan d'exécution. analyze=False : estimation seule, la requête n'est PAS exécutée.
    analyze=True (EXPLAIN ANALYZE) exécute la requête : réservé à une demande de l'utilisateur.
    Une requête paramétrée ($1, $2… comme dans pg_stat_statements) reçoit un plan générique."""
    checked = check(sql)
    has_parameters = bool(_PARAMETER.search(checked.sql))
    if has_parameters and analyze:
        raise ToolError("Requête paramétrée ($1…) : seul le plan estimé est possible, pas EXPLAIN ANALYZE.")
    if analyze:
        options = "ANALYZE, BUFFERS, FORMAT TEXT"
    else:
        options = "GENERIC_PLAN, FORMAT TEXT" if has_parameters else "FORMAT TEXT"
    try:
        with pool_ro.connection() as conn:
            _read_only(conn, timeout_ms)
            rows = conn.execute(f"EXPLAIN ({options}) {checked.sql}").fetchall()
            conn.rollback()
    except psycopg.Error as e:
        raise _db_error(e) from None
    return "\n".join(r[0] for r in rows)


# Seuils mesurés sur la base (19/11/2026) : vue matérialisée ≈ 8, index sur code_commune ≈ 1 700,
# lecture complète de dvf_mutations ≈ 115 000 (0,5 à 1 s), vue v_prix_m2_commune ≈ 420 000 (5 à 55 s).
SLOW_COST = 100_000
_TOP_COST = re.compile(r"cost=[\d.]+\.\.([\d.]+)")


def performance_diagnosis(sql: str, plan: str) -> str | None:
    """Diagnostic de lenteur tiré du plan estimé (fiche, 5.1 : « si la requête est lente,
    l'agent ajoute un diagnostic »). Déterministe : il ne dépend pas du modèle."""
    match = _TOP_COST.search(plan)
    cost = float(match.group(1)) if match else 0.0
    reasons = []
    if re.search(r"\bv_prix_m2_commune\b", sql, re.IGNORECASE):
        reasons.append("la vue v_prix_m2_commune recalcule son agrégat sur les 3,8 millions de lignes DVF "
                       "à chaque appel (5 à 55 s) ; v_prix_m2_commune_mat donne le même résultat en moins de 2 ms")
    if "Seq Scan on dvf_mutations" in plan and cost >= SLOW_COST:  # avec LIMIT, un Seq Scan peut être instantané
        reasons.append("la requête lit toute la table dvf_mutations (3,8 millions de lignes) faute d'index "
                       "utilisable pour ce filtre")
    if cost < SLOW_COST and not reasons:
        return None
    head = f"Requête potentiellement lente (coût estimé {cost:,.0f})".replace(",", " ")
    return head + (" : " + " ; ".join(reasons) + "." if reasons else ".")


def execute_select(sql: str, max_rows: int = 200, timeout_ms: int | None = None) -> dict[str, Any]:
    checked = check(sql)
    start = time.perf_counter()
    try:
        with pool_ro.connection() as conn:
            _read_only(conn, timeout_ms)
            with conn.cursor() as cur:
                cur.execute(checked.sql)
                columns = [d.name for d in cur.description] if cur.description else []
                rows = cur.fetchmany(max_rows + 1)
            conn.rollback()
    except psycopg.Error as e:
        raise _db_error(e) from None
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    return {
        "colonnes": columns,
        "lignes": [list(r) for r in rows[:max_rows]],
        "nb_lignes": min(len(rows), max_rows),
        "tronque": len(rows) > max_rows,
        "duree_ms": duration_ms,
    }
