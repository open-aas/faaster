# Validation

`--validate-only` checks a model and its extensions before deployment, without building the
address space or starting a server:

```bash
python server.py -m models/my_asset.json --validate-only [--report-format json] [--sources sources/]
```

`server.py` calls `validate_only(args)`, which runs `faaster.validation.validate(model, sources)`,
prints the report and exits with `0`, or `1` when a blocking stage fails. Extensions are read with
`ast` and **never imported**, so validating does not run user code.

## Stages

The numbers follow the deployment pipeline (stages 4, 6, 7 and 8 are the ones that can be checked
offline). Code: `faaster/validation/validator.py`.

| Stage | Checks | Blocking |
|---|---|---|
| 4 metamodel | the model loads (json/xml/aasx) and passes the AASd constraints | yes |
| 6 operations | every Operation has a snake_case method in its extension class | no (warning) |
| 7 extensions | the extension parses and defines the expected class; every literal `context.get_node("…")` points to a dynamic variable or one of its `Value@<level>` nodes. A submodel with dynamic variables or Operations but no extension is only a warning: values stay static and Operations return `[]` | yes |
| 8 dynamic | the `faaster:dynamic` Qualifier is a boolean; `faaster:hda:*` policies are valid and only on dynamic variables; Extension names are unique per element (AASd-077). `category: VARIABLE` gives a deprecation warning | yes |

If stage 4 fails, the other stages are reported as `skipped`.

## Report

`faaster/validation/report.py` — a `Report` holds one `Stage` per check; each stage has a status
(`passed`, `warning`, `failed`, `skipped`) and a list of issues (`error` or `warning`, message and
optional path). A non-blocking stage records its errors as warnings.

- `--report-format text` (default):

  ```
  [ passed] stage 4 metamodel
  [warning] stage 6 operations
            warning: …
  [ passed] stage 7 extensions
  [ passed] stage 8 dynamic
  OK
  ```

- `--report-format json`: `{"faaster_version", "ok", "stages": [{"number", "name", "blocking",
  "status", "issues"}]}` on stdout; logs go to stderr so the output can be piped.

The project agent `.claude/agents/aas-model-validator.md` covers model review for agents.
