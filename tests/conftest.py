"""conftest.py — project-wide pytest fixtures."""
import sys
from unittest.mock import MagicMock, patch

# Patch spacy.load at collection time so pii_detection.py can be imported
# without downloading or loading the model.
_spacy_mock = MagicMock()
sys.modules.setdefault("spacy", MagicMock(load=MagicMock(return_value=_spacy_mock)))
