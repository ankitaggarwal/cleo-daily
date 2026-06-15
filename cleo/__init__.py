"""Cleo Daily — an open-source engine for LLM-authored print magazines.

Boring, reliable work is code (this package). Work that needs taste is the
model (the Editor, run as a scheduled Claude routine over MCP).

The split is the whole design:

    cleo ingest   → pull sources over MCP, normalize to the Item schema   (code)
    [the routine] → read, cut 9-in-10, cluster, rank, write the Issue      (model)
    cleo render   → Issue + theme → HTML → headless Chrome → print PDF      (code)
    cleo publish  → ship the artifact (file / git / email / web)           (code)
"""

__version__ = "0.2.0"
