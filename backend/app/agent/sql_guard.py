"""
Vérification du SQL généré par le modèle, AVANT toute exécution (fiche, Q10 et Q15).

Règle : une seule instruction, de type SELECT (CTE et UNION compris), qui ne lit que les
relations autorisées du schéma immo et n'appelle aucune fonction système dangereuse.
L'analyse se fait avec un vrai parseur SQL (sqlglot, dialecte PostgreSQL), pas avec des
expressions régulières : un « ; DROP » caché dans une chaîne ou un commentaire est bien compris.

C'est une défense en profondeur : même si une requête passait, elle s'exécuterait avec
analyst_ro (lecture seule, aucun accès au schéma app, 30 s maximum).
"""
from dataclasses import dataclass

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError

MAX_SQL_LENGTH = 10_000

# Nœuds interdits n'importe où dans l'arbre (y compris dans une CTE : WITH x AS (DELETE …))
_FORBIDDEN_NODES = tuple(
    t for t in (
        getattr(exp, name, None)
        for name in ("Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "AlterTable",
                     "TruncateTable", "Command", "Copy", "Into", "Lock", "Set", "Use", "Grant",
                     "Transaction", "Commit", "Rollback", "Analyze", "Pragma")
    ) if t is not None
)

# Fonctions refusées : lecture de fichiers, attente, exécution de SQL dynamique, réglages…
_FORBIDDEN_FUNCTIONS = {
    "set_config", "current_setting", "query_to_xml", "query_to_xml_and_xmlschema",
    "query_to_xmlschema", "cursor_to_xml", "table_to_xml", "schema_to_xml", "database_to_xml",
    "nextval", "setval", "txid_current", "json_populate_record",
}
_FORBIDDEN_PREFIXES = ("pg_", "lo_", "dblink")

_SET_OPERATIONS = tuple(
    t for t in (getattr(exp, n, None) for n in ("SetOperation", "Union", "Intersect", "Except")) if t
)


class SqlRejected(ValueError):
    """Requête refusée ; le message est destiné au modèle et à l'utilisateur."""


@dataclass(frozen=True)
class CheckedSql:
    sql: str  # texte d'origine, sans point-virgule final


def _function_name(node: exp.Expression) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.name).lower()
    try:
        return node.sql_name().lower()
    except Exception:
        return node.key.lower()


def check_select(sql: str, allowed_relations: frozenset[str] | set[str]) -> CheckedSql:
    """Lève SqlRejected si la requête n'est pas une seule instruction SELECT autorisée."""
    if sql is None or not sql.strip():
        raise SqlRejected("Requête vide.")
    if len(sql) > MAX_SQL_LENGTH:
        raise SqlRejected(f"Requête trop longue (plus de {MAX_SQL_LENGTH} caractères).")

    try:
        statements = [s for s in sqlglot.parse(sql, read="postgres") if s is not None]
    except ParseError as e:
        raise SqlRejected(f"SQL illisible : {str(e).splitlines()[0][:200]}") from None

    if len(statements) != 1:
        raise SqlRejected(f"Une seule instruction est autorisée ({len(statements)} trouvées).")
    stmt = statements[0]

    if not isinstance(stmt, (exp.Select, *_SET_OPERATIONS)):
        raise SqlRejected(f"Seule une instruction SELECT est autorisée (reçu : {stmt.key.upper()}).")

    for node in stmt.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise SqlRejected(f"Opération interdite dans la requête : {node.key.upper()}.")
        if isinstance(node, exp.Func):
            name = _function_name(node)
            if name in _FORBIDDEN_FUNCTIONS or name.startswith(_FORBIDDEN_PREFIXES):
                raise SqlRejected(f"Fonction interdite : {name}().")

    cte_names = {str(cte.alias).lower() for cte in stmt.find_all(exp.CTE)}
    allowed = {r.lower() for r in allowed_relations}
    for table in stmt.find_all(exp.Table):
        name = str(table.name).lower()
        schema = str(table.db).lower() if table.db else ""
        if not name:
            continue
        if table.catalog:
            raise SqlRejected("Les références à une autre base sont interdites.")
        if schema and schema != "immo":
            raise SqlRejected(f"Seul le schéma immo est accessible (reçu : {schema}.{name}).")
        if not schema and name in cte_names:
            continue
        if name not in allowed:
            raise SqlRejected(
                f"Relation inconnue ou non autorisée : {name}. Relations disponibles : "
                + ", ".join(sorted(allowed)) + "."
            )

    return CheckedSql(sql=sql.strip().rstrip(";").strip())
