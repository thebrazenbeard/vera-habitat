import pytest
from vera_habitat.model import Entity, Position3

@pytest.mark.parametrize("bad",[None, 12, True])
def test_entity_identity_must_be_string(bad):
    with pytest.raises(ValueError, match="entity_id"):
        Entity(bad, "avatar", "zone-a", Position3(0.0,0.0,0.0))
