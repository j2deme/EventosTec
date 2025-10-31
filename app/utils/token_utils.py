"""
Legacy token utilities (deprecated)

This module previously provided helpers to generate and verify stateless
tokens used in public flows (self-register and chief links). The project
policy changed: public flows must use slugs/IDs and tokens are deprecated.

To make accidental usage fail fast and make the deprecation explicit,
these helpers now raise a RuntimeError. If you are updating code that used
to rely on token generation/verification, switch to slug/id resolution.
"""


def _deprecated(*args, **kwargs):
    raise RuntimeError(
        "Token utilities deprecated: public tokens are removed. Remove any calls to token_utils."
    )


def generate_activity_token(*a, **k):
    return _deprecated()


def verify_activity_token(*a, **k):
    return _deprecated()


def generate_public_token(*a, **k):
    return _deprecated()


def verify_public_token(*a, **k):
    return _deprecated()


def generate_public_event_token(*a, **k):
    return _deprecated()


def verify_public_event_token(*a, **k):
    return _deprecated()
