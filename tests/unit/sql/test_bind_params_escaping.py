"""Regression tests: DB-derived pg_stats sample values used to fill query parameters
must be escaped as SQL literals, not interpolated raw (second-order SQL injection guard)."""

from unittest.mock import AsyncMock

import pytest

from postgres_mcp.sql.bind_params import SqlBindParams


@pytest.mark.parametrize(
    "evil",
    [
        "a'); DROP TABLE audit_log; --",
        "o'brien",
        "x' OR '1'='1",
    ],
)
def test_equality_replacement_escapes_pg_stats_sample(evil):
    """A most-common text value containing a single quote must become a properly-escaped
    SQL literal (quote doubled) so it cannot break out of the surrounding string."""
    bp = SqlBindParams(AsyncMock())
    out = bp._get_replacement_value(
        {"data_type": "text", "common_vals": [evil]},
        context="col = $1",
    )
    # Properly-escaped literal: wrapped in quotes with every inner quote doubled, so the
    # payload stays inert data inside the string and cannot terminate it.
    assert out.startswith("'") and out.endswith("'")
    assert out == "'" + evil.replace("'", "''") + "'"
    # Every single quote in the payload is doubled (no un-doubled quote can close the literal).
    assert out[1:-1].count("'") % 2 == 0


def test_between_bound_string_is_escaped():
    """String bounds returned for a BETWEEN range must round-trip through a SQL literal
    rather than being embedded raw."""
    from psycopg.sql import Literal

    evil = "a'); DELETE FROM t; --"
    bp = SqlBindParams(AsyncMock())
    bound = bp._get_bound_values(
        {"data_type": "text", "common_vals": [evil], "common_freqs": [1.0]},
        is_lower=True,
    )
    literal = Literal(bound).as_string()
    assert literal == "'" + evil.replace("'", "''") + "'"
    # Inner quotes are all doubled → the literal cannot be terminated early.
    assert literal[1:-1].count("'") % 2 == 0
