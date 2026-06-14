from app.bootstrap import BACKEND_ROOT


def test_backend_is_project_level_package():
    assert not (BACKEND_ROOT / "week 02").exists()
    assert not (BACKEND_ROOT / "week3").exists()
    assert (BACKEND_ROOT / "app" / "rag").is_dir()
    assert (BACKEND_ROOT / "app" / "providers").is_dir()
    assert (BACKEND_ROOT / "app" / "parsers").is_dir()
    assert (BACKEND_ROOT / "app" / "rag" / "grounding.py").exists()
    assert (BACKEND_ROOT / "app" / "providers" / "model_provider.py").exists()
