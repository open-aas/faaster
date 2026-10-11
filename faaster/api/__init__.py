"""Interface HTTP/REST do AAS (IDTA-01002-3-2 — Part 2 API)."""
from .server import HttpApiServer
from .app import create_app
from .repository import AASRepository
