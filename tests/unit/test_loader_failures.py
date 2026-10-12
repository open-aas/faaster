"""ExtensionLoader registra as falhas de cada extensão (antes só iam para o log) — D16."""
from unittest.mock import MagicMock

from faaster.extensions.loader import ExtensionLoader


def _loader(tmp_path, monkeypatch, files: dict):
    sources = tmp_path / "sources"
    sources.mkdir()
    for name, content in files.items():
        (sources / name).write_text(content)
    monkeypatch.chdir(tmp_path)
    registry = MagicMock()
    registry.node_submodels = {name.removesuffix(".py").title(): None for name in files}
    registry.get_operations.return_value = []
    return ExtensionLoader(MagicMock(), registry)


GOOD = '''
from faaster.extensions.interfaces import ISubmodelExtension
class Energy(ISubmodelExtension):
    def __init__(self, context): self.context = context
    async def init(self): ...
    async def stop(self): ...
'''


async def test_failures_are_recorded_per_submodel(tmp_path, monkeypatch):
    loader = _loader(tmp_path, monkeypatch, {
        "energy.py": GOOD,
        "broken.py": "import does_not_exist\n",
        "missing.py": "class Other: ...\n",
        "crashes.py": GOOD.replace("Energy", "Crashes").replace(
            "self.context = context", "raise RuntimeError('mqtt://user:s3cret@10.0.0.5')"),
    })

    loaded = await loader.load(MagicMock())

    assert set(loaded) == {"Energy"}
    assert set(loader.failures) == {"Broken", "Missing", "Crashes"}
    assert loader.failures == {
        "Broken": "import_error: ModuleNotFoundError",
        "Missing": "class_not_found",
        "Crashes": "init_error: RuntimeError",
    }


async def test_failure_messages_never_leave_the_logs(tmp_path, monkeypatch):
    """Security: exception messages may hold credentials; only categories are published."""
    loader = _loader(tmp_path, monkeypatch, {"crashes.py": GOOD.replace("Energy", "Crashes")
        .replace("self.context = context", "raise RuntimeError('mqtt://user:s3cret@10.0.0.5')")})

    await loader.load(MagicMock())

    assert "s3cret" not in str(loader.failures) and "10.0.0.5" not in str(loader.failures)
