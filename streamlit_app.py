"""Backward-compatible Streamlit launcher.

Prefer running ``streamlit run frontend/audit_workbench.py``. This wrapper keeps
older commands working.
"""

from frontend import audit_workbench  # noqa: F401
