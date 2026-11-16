# Accuracy evaluation

Measures how well the damage detector does on photos that people have already labelled.
The code is in `backend/evals/`; this folder holds the data and results (photos and raw
results are gitignored).

Results from a 50-photo CarDD run on three models are in the
[main README](../README.md#results-on-cardd). A run needs an Anthropic API key and a
dataset. The harness itself is also tested with a fake detector.

Per damage type, F1 on those 50 photos:

| Damage type | Photos with it | Haiku 5.5 | Sonnet 5.5 | Opus 5.5 |
|---|---|---|---|---|
| dent | 19 | 90.5% | 84.4% | 80.9% |
| scratch | 26 | 80.0% | 89.7% | 86.2% |
| crack | 11 | 72.0% | 71.4% | 72.0% |
| glass shatter | 9 | 94.7% | 94.7% | 94.7% |
| lamp broken | 6 | 72.7% | 76.9% | 83.3% |
| tire flat | 3 | 100.0% | 100.0% | 100.0% |

The rarer types rest on very few photos, so read those rows loosely. Cracks are the
hardest type for every model.

## Get a dataset

[CarDD](https://cardd-ustc.github.io/) has 4,000 photos with 9,000 labelled damages in the
same six categories this project uses (dent, scratch, crack, glass shatter, lamp broken,
tire flat). It is free for research use, but you have to request it through the form on
that page. It comes in COCO format, which is what the loader reads.

Any COCO-format set works if its category names match those six. To score panels as well,
add a `"panel"` to each annotation with one of the names in `backend/app/schemas.py`
(for example `"left_front_door"`).

For CarDD's test split, [cardd_panel_labels.json](cardd_panel_labels.json) has panels for
75 damages on the 50 photos used in the published run (annotation id to panel). Merge them
into a copy of the annotations, from `backend/`:

```bash
python -m evals.add_panels --annotations path/to/instances_test2017.json --panels ../eval/cardd_panel_labels.json --out ../eval/annotations-panels.json
```

Then pass `../eval/annotations-panels.json` to `evals.report` to get the panel accuracy column.

Put the files here:

```
eval/images/                 the photos
eval/annotations.json        the COCO annotations (e.g. CarDD's instances_test2017.json)
```

## Run it

From `backend/`, with `CRASHTIMATE_DETECTOR=claude` and `ANTHROPIC_API_KEY` set in `.env`:

```bash
python -m evals.run --annotations ../eval/annotations.json --images ../eval/images --out ../eval/results/opus-5-5-medium.jsonl --limit 200
```

- `--limit 200` scores a random 200 photos. The same `--seed` picks the same photos, so
  different models are compared on identical inputs.
- Each photo is one paid request. Results are saved as they arrive, and a second run skips
  photos that already succeeded, so an interrupted run can be resumed.

To compare models, change `CRASHTIMATE_CLAUDE_MODEL` or `CRASHTIMATE_CLAUDE_EFFORT` and run
again with a different `--out` file.

## Score it

```bash
python -m evals.report ../eval/results/*.jsonl --annotations ../eval/annotations.json
```

Add `--input-price` and `--output-price` (US dollars per million tokens, from the model's
pricing page) to get a cost per photo. This prints a Markdown comparison table, one row per
results file, plus a per-damage-type table for each.

## What is measured

| Measure | Question it answers |
|---|---|
| Precision, recall, F1 | Per photo and damage type: did the detector report the kinds of damage the photo is labelled with? |
| Exact match | On how many photos is the reported set of damage types exactly right? |
| Labels located | How many labelled damages have a predicted box of the same type on them (IoU of 0.3 or more)? |
| Boxes on a label | How many predicted boxes sit on a real labelled damage? |
| Panel accuracy | When labels name a panel, did the detector name the same one? |
| Time and cost | Median seconds and tokens per photo. |

Two limits to keep in mind when reading the numbers:

- The detector draws one box per panel per damage type, while CarDD labels every mark
  separately. That is why the overlap threshold is a loose 0.3 and one predicted box can
  count for several labels.
- CarDD has no severity or panel labels, so severity is not scored at all, and panel
  accuracy needs hand-labelled panels.
