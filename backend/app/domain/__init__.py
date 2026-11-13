"""Pure business logic: no I/O, no database, no network, no clock, no randomness.

Every module here has a `*_test.py` next to it. Adapters (readers, API, worker)
call into this package; this package never calls out.
"""
