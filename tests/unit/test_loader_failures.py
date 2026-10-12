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
            "self.context = context", "raise RuntimeError('boom')"),
    })

    loaded = await loader.load(MagicMock())

    assert set(loaded) == {"Energy"}
    assert set(loader.failures) == {"Broken", "Missing", "Crashes"}
    assert "does_not_exist" in loader.failures["Broken"]
    assert "Missing" in loader.failures["Missing"]
    assert "boom" in loader.failures["Crashes"]
