# ML training and evaluation plan

## Purpose

Evaluate whether trained text classifiers improve the detection of themes in employee survey responses compared with the application's existing rules. The main output is one or more theme labels per written answer, supporting the existing theme summaries, response review and survey comparisons.

Proposed research question:

> How do TF-IDF and pretrained sentence-embedding classifiers compare with a rule-based baseline for multi-label theme classification in employee survey responses?

This is a proposed plan, not a record of completed training or measured results. Dataset availability will determine the final experiment size.

For repository-specific implementation steps, integration risks and the evidence to retain at each stage, see [TF-IDF implementation and evidence plan](tfidf-implementation-and-evidence-plan.md).

For the full delivery stages, detailed implementation contracts for both trained approaches, prioritised technical reading and additional data-inference experiments, see [ML implementation roadmap and future inference opportunities](ml-implementation-roadmap-and-extensions.md).

## 1. Current application baseline

The current implementation is in `services/text_analysis.py`. It:

- Matches sentences to seven theme categories using keywords and manually defined synonyms.
- Uses cosine similarity between normalised word-count vectors; these are not learned semantic embeddings.
- Assigns sentiment using positive and negative word lists.
- Suggests topics from frequently occurring unmatched words.
- Stores theme assignments, supporting text, a model version and a heuristic confidence score.

The existing categories are workload and capacity, manager support, career development, communication, tools and access, team connection, and organisational change.

The baseline has no model-training stage. Its confidence percentages are calculated scores, not validated probabilities. Sentiment rules do not adequately handle negation: for example, “my manager is not helpful” contains a positive keyword. Existing application tests establish that selected workflows operate correctly; they do not measure generalisation to unseen responses.

Preserve a version of this baseline before experimentation so every model can be compared against the same implementation.

## 2. Define the prediction task

Use **multi-label classification**: an answer may belong to several themes, or none of the seven themes.

Example:

> My colleagues are supportive, but there are too many deadlines.

Expected labels: **Team connection** and **Workload and capacity**.

Use one complete written answer as the initial training and evaluation unit. For the current baseline, combine its sentence-level detections into answer-level labels. This gives all approaches the same prediction target.

Initially, use only the answer text as model input. Keep respondent identifiers, names, quantitative survey scores and cohort information out of the features. Retain identifiers separately for splitting and evaluation. Short answers that depend on the question wording should be flagged during error analysis; adding question text can be a later, separately evaluated experiment.

Keep sentiment classification and discovery of entirely new themes outside the primary experiment. They require separate labels and evaluation criteria.

## 3. Prepare a labelled dataset

### Data source

A fully synthetic 80-answer annotation pilot is available in [the review guide](synthetic-pilot/review-guide.md), with a [readable data preview](synthetic-pilot/data-preview.md) and [editable review CSV](synthetic-pilot/review.csv). Its labels are AI-authored drafts awaiting human review; it is development material, not real-data evidence or an untouched final test set.

Prefer survey responses that can appropriately be used for this project. Remove identifying details from the text before creating the research dataset.

Begin with a pilot of a few hundred answers if available. This is a planning target, not evidence that the sample is sufficient. Count positive and negative examples for every theme and expand the dataset where coverage is weak.

If only synthetic data is available, document how it was created and limit conclusions to that setting. Synthetic performance does not establish performance on real employee feedback. Keep examples created from the same template or paraphrase family in the same split.

### Annotation fields

| Field | Purpose |
| --- | --- |
| Answer ID | Stable reference to the example |
| De-identified answer text | Classifier input |
| Respondent group ID | Keep answers from the same person together during splitting |
| Survey period and source | Support time-based evaluation and traceability |
| Seven theme labels | Independent yes/no judgement for each theme |
| Review status | Distinguish completed labels from unlabelled examples |
| Annotation notes | Record ambiguity or disagreement |

“None of these themes” means all seven labels are negative after review. It must not mean that an answer has not yet been labelled. Blank answers should be excluded from theme classification and counted separately.

### Annotation process

1. Write a short guide defining each theme, with examples, exclusions and overlap rules.
2. Label a small pilot batch and revise unclear definitions.
3. Have a second annotator independently label a subset, without seeing model predictions.
4. Record per-theme agreement and discuss disagreements. If reporting Cohen's kappa, also report label frequencies because rare themes affect its interpretation.
5. Resolve disagreements to create the reference labels, then freeze the guide for the main dataset.

Do not use the current keyword rules as the ground-truth labels: this would mainly test whether the new models reproduce those rules.

## 4. Split the data before training

Aim for approximately **70% training, 15% validation and 15% test**, subject to dataset size and theme coverage.

- **Training:** fit vocabulary, word weights and classifier parameters.
- **Validation:** choose features, regularisation and decision thresholds.
- **Test:** measure the final selected configuration once development is complete.

Keep answers from the same respondent in one split. Also group duplicates and near-duplicate or synthetic template families to prevent leakage. Check theme counts after splitting; exact proportions matter less than a defensible split with enough examples to assess each theme.

For a small dataset, reserve a final test set and use grouped cross-validation within the remaining development data. Fit preprocessing separately within each training fold.

If enough survey periods exist, add a later-period evaluation to test performance on future surveys. Document whether respondents also appear in earlier periods: future-period generalisation and generalisation to entirely new respondents are different claims.

Save the split assignments and random seed. Use identical splits for all approaches.

## 5. Compare three approaches

| Approach | Representation | What is trained? | Purpose |
| --- | --- | --- | --- |
| A. Existing rules | Keywords, manual synonyms and word-count similarity | Nothing | Application baseline |
| B. TF-IDF + logistic regression | Weighted word and phrase features | TF-IDF vocabulary/weights and one binary classifier per theme | Main classical ML experiment |
| C. Sentence embeddings + logistic regression | Vectors from a pretrained sentence encoder | One binary classifier per theme; encoder stays fixed | Test whether semantic features improve results |

### A. Existing rule-based baseline

Run the current implementation on the held-out examples and collect answer-level theme predictions. Keep its rules fixed during the main comparison. If rules are revised using development data, report that as a separate baseline version.

### B. TF-IDF + logistic regression

**TF-IDF** represents an answer using words or phrases, giving weight to terms that help distinguish it from other answers. Logistic regression then learns a separate theme decision from those features.

Proposed implementation:

1. Build a scikit-learn pipeline containing `TfidfVectorizer` and `OneVsRestClassifier(LogisticRegression(...))`.
2. Fit it on the training answers and their seven binary labels.
3. Compare word unigrams with unigrams plus bigrams. Bigrams retain short phrases such as “not helpful”, although this does not guarantee correct negation handling.
4. Preserve negation words such as “not” and “no”; start without generic stop-word removal.
5. Compare a small regularisation grid, for example `C = 0.1, 1, 10`.
6. Compare default class weighting with balanced class weighting if themes are unevenly represented.
7. Select the configuration using validation macro-F1, alongside per-theme precision and recall.
8. Start with a 0.5 decision threshold. Only tune per-theme thresholds if validation data contains enough positive and negative examples; otherwise use a shared threshold.

Keep the search small and record each configuration. Fit the vectoriser only on training data, including when using cross-validation. A theme with no positive training examples cannot be learned meaningfully; collect more labels or explicitly report that limitation.

Save the fitted pipeline, theme order, thresholds, dependency versions and training metadata. The same pipeline must transform new answers during inference.

### C. Pretrained sentence embeddings + logistic regression

Use a compact pretrained sentence-transformer encoder to turn each answer into a vector, then train the same style of one-vs-rest logistic regression classifier.

Keep the encoder frozen initially. Training therefore updates the classifier, not the underlying language model. Compare regularisation and thresholds using the same development protocol as the TF-IDF model.

Record the encoder name and exact revision, input-length limit and any truncation policy. Examine long answers so important content is not silently dropped. Measure inference time and memory use as well as predictive performance.

Fine-tuning the encoder is an optional later experiment if the labelled dataset and initial results justify it; it is not necessary for the first comparison.

## 6. Evaluate the models

### Classification quality

| Measure | What it tells us |
| --- | --- |
| Per-theme precision | How often a predicted theme is correct |
| Per-theme recall | How many relevant answers the model finds |
| Per-theme F1 and support | Balance of precision/recall and the number of examples behind the result |
| Macro-F1 | Average performance with equal weight for each theme |
| Micro-F1 | Overall performance across all theme decisions |
| Per-theme confusion counts | False positives and false negatives for each theme |

Use macro-F1 as the primary model-selection measure, but do not select a model from a single aggregate score alone. Report results for answers with no applicable theme and for answers with multiple themes. Where feasible, estimate uncertainty by bootstrapping respondent groups rather than individual answers.

### Impact on the application

Measure **theme prevalence error**: the absolute difference, in percentage points, between model-derived and human-labelled prevalence.

Aggregate assignments to distinct respondents before calculating prevalence, matching the application. Use the same denominator for predictions and reference labels. If evaluation labels cover only a subset of respondents, report prevalence for that subset rather than presenting it as full-survey prevalence.

Also record inference time, model size, and the proportion of answers that would need human review. If testing an uncertainty-based review threshold, select it using validation data and report both error rates and review workload on the test set.

### Error analysis

Review examples involving:

- Negation: “My manager is not supportive.”
- Different wording: “I cannot keep up with everything assigned to me.”
- Multiple themes: “The team is great, but the software keeps failing.”
- Mixed opinions within one theme.
- Very short or question-dependent answers.
- Misspellings, unfamiliar terms and long answers.
- Topics outside the existing theme catalogue.

Keep a small challenge set for these cases, separate from the representative test set. Report its results separately. Do not repeatedly edit the model against the final test set; any changes prompted by final-test findings require a fresh evaluation for an unbiased result.

## 7. Integrate the selected model

The existing service boundary and stored annotations provide a starting point for integration. Preserve the outputs needed by the current UI: theme assignment, response reference, model version and evidence.

Recommended application changes:

1. Add a way for reviewers to correct **individual answer-to-theme assignments**, separately from approving a theme category.
2. Store human decisions separately from model predictions so rerunning analysis does not delete the reviewed labels.
3. Distinguish “theme category approved” from “this answer's assignment checked”.
4. Label uncalibrated values as model scores. Neither cosine similarity nor an unvalidated classifier probability should be presented as a proven percentage certainty.
5. For answer-level classifiers, show the answer as supporting context. Do not claim a specific sentence explains the decision unless sentence-level evidence selection has also been evaluated.
6. Record the model version used for each analysis. When comparing survey trends, use a consistent model version or clearly identify version changes.

Train models offline and load versioned artifacts for application inference. Survey uploads should not trigger model retraining. Reviewer corrections can feed a later, controlled training round while preserving the held-out evaluation data.

## 8. Delivery stages

| Stage | Deliverable | Completion condition |
| --- | --- | --- |
| 1. Task and labels | Theme annotation guide and pilot dataset | Ambiguous definitions reviewed |
| 2. Dataset | Labelled examples and saved split assignments | Leakage and theme coverage checked |
| 3. Baseline | Existing-rule predictions and metrics | Evaluation pipeline works |
| 4. TF-IDF | Fitted pipeline and validation comparison | Configuration selected without test data |
| 5. Embeddings | Frozen-encoder classifier and comparison | Same splits and metrics used |
| 6. Final evaluation | Test results, uncertainty and error analysis | Selected configurations evaluated and limitations recorded |
| 7. Application integration | Versioned inference and assignment-review workflow | Outputs and review records verified |

Prefer the simplest model that provides a useful, defensible improvement. If neither trained model improves sufficiently on the rules, report that finding rather than assuming complexity is a benefit.

## 9. Suggested experiment artifacts

- Annotation guide and dataset description.
- Dataset version, label counts and split manifest.
- Reproducible training and evaluation scripts.
- Saved model configuration, seed, thresholds and dependency versions.
- Results table comparing all three approaches.
- Per-theme error analysis and application prevalence comparison.
- Short model report describing intended use, limitations and data provenance.

Keep raw employee responses and trained artifacts containing sensitive vocabulary out of ordinary source control. This document is the plan; it does not introduce datasets or trained models into the repository.

## References

- [scikit-learn: TF-IDF vectoriser](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html)
- [scikit-learn: cross-validation and grouped splits](https://scikit-learn.org/stable/modules/cross_validation.html)
- [Sentence-BERT paper](https://aclanthology.org/D19-1410.pdf)
- [Sentence Transformers: training overview](https://www.sbert.net/docs/sentence_transformer/training_overview.html)
