"""Results directory layout, shared by every stage so the layout only needs
to change in one place:

  results/raw/<session>/<deployment>/<condition>/<run_id>/   CSV + metadata + manifest
  results/derived/<stage>/...                                JSON/CSV summaries
  results/figures/
  results/tables/
"""
from __future__ import annotations

from pathlib import Path


def find_rq2_root(start: Path | None = None) -> Path:
    """Walk up from `start` (default: this file) to the directory containing
    the `rq2` package and `results/`, i.e. the RQ2 project root."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here] + list(here.parents):
        if (candidate / "rq2").is_dir() and (candidate / "configs").is_dir():
            return candidate
    raise RuntimeError(f"could not locate RQ2 project root above {here}")


def results_root(rq2_root: Path | None = None) -> Path:
    return (rq2_root or find_rq2_root()) / "results"


def session_raw_dir(session: str, rq2_root: Path | None = None) -> Path:
    return results_root(rq2_root) / "raw" / session


def raw_run_dir(session: str, deployment: str, condition: str, run_id: str,
                 rq2_root: Path | None = None) -> Path:
    return session_raw_dir(session, rq2_root) / deployment / condition / run_id


def derived_dir(stage: str, rq2_root: Path | None = None) -> Path:
    return results_root(rq2_root) / "derived" / stage


def figures_dir(rq2_root: Path | None = None) -> Path:
    return results_root(rq2_root) / "figures"


def tables_dir(rq2_root: Path | None = None) -> Path:
    return results_root(rq2_root) / "tables"


def campaign_log_path(session: str, rq2_root: Path | None = None) -> Path:
    return session_raw_dir(session, rq2_root) / "campaign.log"


def session_log_path(session: str, rq2_root: Path | None = None) -> Path:
    return session_raw_dir(session, rq2_root) / "session.log"
