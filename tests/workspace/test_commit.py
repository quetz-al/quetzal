"""Unit tests for committing a workspace and detecting conflicts """
import pytest

from quetzal.app.api.data.tasks import merge
from quetzal.app.api.exceptions import Conflict


def test_commit_success():
    # Create a workspace
    # Add a file
    # Commit
    # File must exist on global bucket
    # File name must be its id
    # File url must be its new address
    raise NotImplementedError


def test_commit_ignores_temporaries():
    # Create a workspace
    # Add file temporary
    # Commit
    # File must have been excluded
    # No file with the corresponding id exists in the global bucket
    raise NotImplementedError


def test_commit_success_new_metadata():
    # Create a workspace with new family
    # Add metadata to new family
    # Commit
    # Global metadata family exists and with its correct value
    # Committed metadata has id on it with its correct value
    raise NotImplementedError


def test_commit_success_metadata_modification():
    # Create a workspace with new family
    # Add metadata to new family
    # Commit
    # Create new workspace with same family
    # Add metadata to same family
    # Commit
    # Global metadata family exists with its correct value
    # Previous metadata is still found on previous version
    raise NotImplementedError


@pytest.mark.parametrize('predecessor,theirs,mine,expected', [
    ({}, {}, {}, {}),                          # No change at all
    ({}, {}, {'x': 1}, {'x': 1}),              # Mine branch adds
    ({}, {'x': 1}, {}, {'x': 1}),              # Their branch adds
    ({}, {'x': 1}, {'x': 1}, {'x': 1}),        # Mine and their add, same content
    ({}, {'x': 1}, {'x': 2}, None),            # Mine and their add, different content
    ({'x': 1}, {'x': 1}, {'x': 1}, {'x': 1}),  # No change on existing
    ({'x': 1}, {'x': 1}, {'x': 2}, {'x': 2}),  # Mine branch modifies
    ({'x': 1}, {'x': 1}, {}, {}),              # Mine branch deletes
    ({'x': 1}, {'x': 2}, {'x': 1}, {'x': 2}),  # Their branch modifies
    ({'x': 1}, {'x': 2}, {'x': 2}, {'x': 2}),  # Mine branch and their branch modify, same content
    ({'x': 1}, {'x': 2}, {'x': 3}, None),      # Mine branch and their branch modify, different content
    ({'x': 1}, {'x': 2}, {}, None),            # Their branch modifies, mine branch deletes
    ({'x': 1}, {}, {'x': 1}, {}),              # Their branch deletes
    ({'x': 1}, {}, {'x': 2}, None),            # Their branch deletes, mine modifies
    ({'x': 1}, {}, {}, {}),                    # Mine branch and their branch delete
])
def test_3way_merge(predecessor, theirs, mine, expected):
    if expected is None:
        with pytest.raises(Conflict):
            merge(predecessor, theirs, mine)
    else:
        new = merge(predecessor, theirs, mine)
        assert new == expected
