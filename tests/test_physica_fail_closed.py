"""Provider failure handling in the default, dependency-free test matrix."""
import pytest

from vera_habitat.training_ground import NeutralTrainingGround


def test_default_never_imports_physica_and_explicit_optin_fails_closed(monkeypatch):
    from vera_habitat import physica_adapter

    def unavailable(_name):
        raise ModuleNotFoundError("deliberate test: Physica unavailable")

    monkeypatch.setattr(physica_adapter, "import_module", unavailable)
    default = NeutralTrainingGround()
    assert default.collision_backend == "habitat"
    assert default.observe().scene.revision > 0

    with pytest.raises(ImportError, match="separately installed"):
        NeutralTrainingGround(collision_backend="physica")


@pytest.mark.parametrize("backend", ["", "PHYSICA", "other", 0, None, True])
def test_invalid_backend_names_do_not_activate_plugins(backend):
    with pytest.raises(ValueError, match="collision_backend"):
        NeutralTrainingGround(collision_backend=backend)
