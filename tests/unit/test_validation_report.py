"""
Validação estruturada do modelo e das extensões (etapas 4, 6, 7 e 8 do pipeline da proposta
de dissertação, §5.6; decisão D15). As extensões são analisadas por AST, nunca executadas.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from faaster.validation import validate

REPO = Path(__file__).resolve().parents[2]
DYNAMIC = {"type": "faaster:dynamic", "kind": "ValueQualifier",
           "valueType": "xs:boolean", "value": "true"}


def env(submodel_elements, sm_id_short="Energy"):
    return {
        "assetAdministrationShells": [{
            "modelType": "AssetAdministrationShell", "id": "urn:aas:1", "idShort": "Meter",
            "assetInformation": {"assetKind": "Instance", "globalAssetId": "urn:asset:1"},
            "submodels": [{"type": "ModelReference",
                           "keys": [{"type": "Submodel", "value": "urn:sm:1"}]}],
        }],
        "submodels": [{"modelType": "Submodel", "id": "urn:sm:1", "idShort": sm_id_short,
                       "submodelElements": submodel_elements}],
        "conceptDescriptions": [],
    }


def prop(id_short, dynamic=True, **extra):
    data = {"modelType": "Property", "idShort": id_short, "valueType": "xs:double", **extra}
    if dynamic:
        data.setdefault("qualifiers", [DYNAMIC])
    return data


def operation(id_short):
    return {"modelType": "Operation", "idShort": id_short}


EXTENSION = '''
class Energy:
    def __init__(self, context):
        self.voltage = context.get_node("Electrical/Voltage/Value")
    async def init(self): ...
    async def stop(self): ...
    async def reset_counter(self, parent): ...
'''


def model(tmp_path, elements, extension=EXTENSION, sm="Energy"):
    path = tmp_path / "model.json"
    path.write_text(json.dumps(env(elements, sm)))
    sources = tmp_path / "sources"
    sources.mkdir()
    if extension is not None:
        (sources / "energy.py").write_text(extension)
    return path, sources


GOOD = [
    {"modelType": "SubmodelElementCollection", "idShort": "Electrical",
     "value": [prop("Voltage")]},
    operation("ResetCounter"),
]


def stage(report, number):
    return next(s for s in report.stages if s.number == number)


async def test_valid_model_passes_every_stage(tmp_path):
    report = await validate(*model(tmp_path, GOOD))

    assert report.ok
    assert [(s.number, s.status) for s in report.stages] == [
        (4, "passed"), (6, "passed"), (7, "passed"), (8, "passed")]


@pytest.mark.parametrize("content", ["{not json", json.dumps(env([prop("1bad")]))])
async def test_unloadable_or_invalid_model_fails_stage_4_and_skips_the_rest(tmp_path, content):
    path = tmp_path / "model.json"
    path.write_text(content)

    report = await validate(path, tmp_path / "sources")

    assert not report.ok
    assert stage(report, 4).status == "failed"
    assert {s.status for s in report.stages if s.number != 4} == {"skipped"}


async def test_nested_element_violating_the_metamodel_fails_stage_4(tmp_path):
    """Regression: collection children are validated at load (AASd-020 here)."""
    bad = prop("Voltage", qualifiers=[{**DYNAMIC, "value": "yes"}])  # AASd-020
    elements = [{"modelType": "SubmodelElementCollection", "idShort": "Electrical",
                 "value": [bad]}]

    report = await validate(*model(tmp_path, elements))

    assert not report.ok
    assert stage(report, 4).status == "failed"
    assert "AASd-020" in stage(report, 4).issues[0].message


async def test_missing_file_fails(tmp_path):
    report = await validate(tmp_path / "nope.json", tmp_path)

    assert not report.ok and stage(report, 4).status == "failed"


async def test_operation_without_method_is_a_warning(tmp_path):
    report = await validate(*model(tmp_path, [*GOOD, operation("Calibrate")]))

    assert report.ok
    assert stage(report, 6).status == "warning"
    assert "Calibrate" in stage(report, 6).issues[0].message
    assert "calibrate" in stage(report, 6).issues[0].message


async def test_dynamic_submodel_without_extension_is_a_warning(tmp_path):
    """Without an extension the runtime still starts: dynamic values stay static and the
    Operations return []. A model not yet integrated is not a wrong model (FTM E3: the 42
    official IDTA templates refused by this rule all start)."""
    report = await validate(*model(tmp_path, GOOD, extension=None))

    assert report.ok
    assert stage(report, 7).status == "warning"
    assert "energy.py" in stage(report, 7).issues[0].message
    assert "static" in stage(report, 7).issues[0].message


async def test_get_node_to_unknown_or_static_path_fails(tmp_path):
    extension = EXTENSION.replace("Electrical/Voltage/Value", "Electrical/Current/Value")
    elements = [{"modelType": "SubmodelElementCollection", "idShort": "Electrical",
                 "value": [prop("Voltage"), prop("Current", dynamic=False)]}]

    report = await validate(*model(tmp_path, elements, extension))

    issue = stage(report, 7).issues[0]
    assert stage(report, 7).status == "failed"
    assert "Electrical/Current/Value" in issue.message and "line 4" in issue.message


async def test_virtual_hda_node_path_is_accepted(tmp_path):
    extension = EXTENSION.replace("Electrical/Voltage/Value", "Electrical/Voltage/Value@1hour")
    policy = [{"name": "faaster:hda:levels", "value": "1min,1hour"}]
    elements = [{"modelType": "SubmodelElementCollection", "idShort": "Electrical",
                 "value": [prop("Voltage", extensions=policy)]}]

    assert (await validate(*model(tmp_path, elements, extension))).ok


async def test_extension_is_never_executed(tmp_path):
    marker = tmp_path / "executed"
    extension = EXTENSION + f"\nopen({str(marker)!r}, 'w').write('x')\n"

    await validate(*model(tmp_path, GOOD, extension))

    assert not marker.exists()


async def test_extension_with_syntax_error_fails(tmp_path):
    report = await validate(*model(tmp_path, GOOD, "class Energy(:\n"))

    assert stage(report, 7).status == "failed"
    assert "syntax" in stage(report, 7).issues[0].message.lower()


@pytest.mark.parametrize(
    ("element", "fragment"),
    [
        (prop("Voltage", extensions=[{"name": "faaster:hda:levels", "value": "3min"}]), "3min"),
        (prop("Voltage", dynamic=False,
              extensions=[{"name": "faaster:hda:mode", "value": "sample"}]), "not dynamic"),
        (prop("Voltage", qualifiers=[{**DYNAMIC, "valueType": "xs:string", "value": "yes"}]),
         "boolean"),
        (prop("Voltage", extensions=[{"name": "x", "value": "1"}, {"name": "x", "value": "2"}]),
         "AASd-077"),
    ],
)
async def test_dynamic_and_hda_rules(tmp_path, element, fragment):
    elements = [{"modelType": "SubmodelElementCollection", "idShort": "Electrical",
                 "value": [element]}]

    report = await validate(*model(tmp_path, elements))

    assert not report.ok
    assert stage(report, 8).status == "failed"
    assert any(fragment in i.message for i in stage(report, 8).issues)


async def test_deprecated_category_is_a_warning(tmp_path):
    elements = [{"modelType": "SubmodelElementCollection", "idShort": "Electrical",
                 "value": [prop("Voltage", dynamic=False, category="VARIABLE")]}]

    report = await validate(*model(tmp_path, elements))

    assert report.ok
    assert stage(report, 8).status == "warning"
    assert "faaster:dynamic" in stage(report, 8).issues[0].message


async def test_report_serializes_to_json(tmp_path):
    report = await validate(*model(tmp_path, GOOD))

    data = json.loads(report.to_json())

    assert data["ok"] is True
    assert data["faaster_version"] not in ("", "unknown")
    assert data["stages"][0] == {"number": 4, "name": "metamodel", "blocking": True,
                                 "status": "passed", "issues": []}


def run_cli(*args):
    return subprocess.run([sys.executable, "server.py", *args], cwd=REPO,
                          capture_output=True, text=True, timeout=120)


def test_cli_validate_only_json_exit_codes(tmp_path):
    path, sources = model(tmp_path, GOOD)
    ok = run_cli("-m", str(path), "--validate-only", "--report-format", "json",
                 "--sources", str(sources))
    missing = run_cli("-m", str(tmp_path / "nope.json"), "--validate-only",
                      "--report-format", "json")

    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["ok"] is True
    assert missing.returncode == 1
    assert json.loads(missing.stdout)["ok"] is False


def test_cli_validate_only_text_fails_on_broken_model(tmp_path):
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")

    result = run_cli("-m", str(broken), "--validate-only")

    assert result.returncode == 1
