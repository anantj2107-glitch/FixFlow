# ML roadmap

The core product is useful before ML is introduced. Add ML only after reviewed examples exist.

## Stage 1: rules (current V1)

- Urgent safety terms raise priority.
- Same category and hostel block creates a duplicate-review signal.
- Staff remain responsible for the final decision.

## Stage 2: duplicate similarity

Use a local multilingual sentence-embedding model. Store the embedding of each active report and return the closest candidates with a similarity score. Do not auto-merge reports.

Evaluate with labelled pairs:

- Precision at top 1 duplicate candidate.
- Recall for known duplicate pairs.
- False duplicate rate, especially across different rooms.

## Stage 3: category model

Collect 300–600 staff-reviewed reports across the supported categories. Use an 80/20 train-test split and report macro-F1, confusion matrix, and per-category recall. Show the predicted category as a suggestion when confidence is low.

## Data protection

Remove phone numbers, names, and room numbers before training whenever they are not necessary for the language model.
