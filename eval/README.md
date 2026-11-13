# Accuracy evaluation

Measures how well the damage detector does on photos that people have already labelled.
The code is in `backend/evals/`; this folder holds the data and results (photos and raw
results are gitignored).

**No results are published yet.** A run needs an Anthropic API key and a dataset, and
neither has been set up. The harness itself is tested with a fake detector.

## Get a dataset

[CarDD](https://cardd-ustc.github.io/) has 4,000 photos with 9,000 labelled damages in the
same six categories this project uses (dent, scratch, crack, glass shatter, lamp broken,
tire flat). It is free for research use, but you have to request it through the form on
that page. It comes in COCO format, which is what the loader reads.

Any COCO-format set works if its category names match those six. To score panels as well,
add a `"panel"` to each annotation with one of the names in `backend/app/schemas.py`
(for example `"left_front_door"`).

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
