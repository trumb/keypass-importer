"""KeePass to CyberArk Privilege Cloud importer."""

import sys

__version__ = "0.1.0"

# Backward-compatible re-exports so that existing imports like
# ``from keypass_importer.models import KeePassEntry`` continue to work.
# We register the sub-package modules under their old top-level names
# in sys.modules so that ``import keypass_importer.models`` resolves.
from keypass_importer.core import models as models  # noqa: F401
from keypass_importer.core import config as config  # noqa: F401
from keypass_importer.keepass import reader as keepass_reader  # noqa: F401
from keypass_importer.cyberark import auth as cyberark_auth  # noqa: F401
from keypass_importer.cyberark import client as cyberark_client  # noqa: F401
from keypass_importer.io import mapper as mapper  # noqa: F401
from keypass_importer.io import csv_reader as csv_reader  # noqa: F401
from keypass_importer.io import exporter as exporter  # noqa: F401
from keypass_importer.io import reporter as reporter  # noqa: F401

# Register backward-compat module aliases in sys.modules
sys.modules["keypass_importer.models"] = models
sys.modules["keypass_importer.config"] = config
sys.modules["keypass_importer.keepass_reader"] = keepass_reader
sys.modules["keypass_importer.cyberark_auth"] = cyberark_auth
sys.modules["keypass_importer.cyberark_client"] = cyberark_client
sys.modules["keypass_importer.mapper"] = mapper
sys.modules["keypass_importer.csv_reader"] = csv_reader
sys.modules["keypass_importer.exporter"] = exporter
sys.modules["keypass_importer.reporter"] = reporter
