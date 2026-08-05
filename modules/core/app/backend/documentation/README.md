# In-app workflow documentation

These markdown pages are the **user-facing reference for every UI workflow tab**. They are indexed in
[`index.md`](index.md), surfaced in the app's *Documentation Search* tab, and pulled into the AI
Assistant's prompt context. When you add a feature, you add a page here in the **same PR** as the code
(one of the three documentation hard rules — see the
[Development skill](../../../../../claude_skills/SKILL_GENESIS_WORKBENCH_DEVELOPMENT.md)).

## Canonical template

Name the file `<module>_<feature>.md` in snake_case (e.g. `protein_structure_prediction.md`,
`cell_type_annotation.md`) and include these sections:

```markdown
# <Feature Name>

## What it does
One paragraph: the input, the output, and the problem it solves for the scientist.

## How to use
UI walkthrough — which tab, the form fields, the expected wait time, and where results appear.

## Inputs
Schema: accepted file formats, column names, parameter ranges and defaults.

## Outputs
What the run produces: MLflow run name + artifacts + tags, any Delta tables, and what the
result dialog shows.

## Underlying models / endpoints
Which serving endpoints, Unity Catalog models, and Vector Search indexes this feature depends on.
Link to the submodule that registers them.

## Limitations and known issues
Honest caveats. Especially: where a predicted score is relative/anchored rather than absolute, and
anything the scientist must verify against the data.
```

## After adding a page

1. Add a bullet linking it under the matching module section in [`index.md`](index.md).
2. Add a bullet under the matching module in the root [`README.md`](../../../../../README.md).
3. Add a dated decision entry in the root [`CHANGELOG.md`](../../../../../CHANGELOG.md).

Write the page **before** declaring the feature shipped: if you can't describe the inputs, outputs, and
errors without hand-waving, the feature isn't done yet.
