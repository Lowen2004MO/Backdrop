# TF-IDF implementation and evidence plan

Prepared: 9 October 2026. Status: proposed implementation; no model has been trained or evaluated as part of this review.

This document turns [the existing training plan](training-plan.md) into application-specific work packages. It focuses on delivering TF-IDF first. The frozen sentence-embedding comparison remains a subsequent experiment in the wider research plan; completing TF-IDF alone would not answer that plan's full three-way research question.

## 1. Recommended first outcome

Implement **TF-IDF plus one-vs-rest logistic regression to assign zero, one or several of the seven existing themes to each complete written answer**. Use these predictions for the imported-survey text analysis and employee response pages, with model version, answer context and a separate human review record.

TF-IDF turns text into weighted word/phrase features. It does not itself classify themes or establish sentiment. The classifier learns the association between those features and independently labelled examples. For example, “The team is great but the software keeps failing” can receive both Team connection and Tools and access.

The initial deliverable answers “which existing themes occur?” Sentiment, new-topic discovery and extracting factual entities require their own methods and evaluation. Keep the current sentiment and suggested-topic rules explicitly identified as separate heuristic outputs if retained. A high Tools and access score says nothing about whether the tools are liked.

## 2. What the code review found

| Current location | Behaviour observed | Consequence for implementation |
| --- | --- | --- |
| `services/text_analysis.py` | Seven catalogue themes; sentence keyword matches and cosine similarity of normalised word counts with manual synonyms | Freeze this as the comparator. Despite the version name `local-hybrid-embedding-v1`, it is not a trained semantic encoder or TF-IDF classifier. |
| `services/text_analysis.py::analyse_survey` | Processes nonempty answers where `question.response_type == 'written'`; retains the strongest sentence match per answer/theme | Predict once per whole answer for TF-IDF; aggregate rule detections to the same answer-level target for evaluation. Explicitly exclude whitespace-only text too. |
| `services/csv_import.py::persist_csv_import` | Infers response types and automatically calls `analyse_survey` inside the import transaction | Check that short free-text columns are correctly identified as written. Upload should run inference against an existing artifact, without fitting a model. Measure transaction duration before considering background execution. |
| `services/text_analysis.py::analyse_survey` | Deletes existing answer annotations before saving replacements | Preserve human labels in separate records. Preserve experiment outputs outside the refresh lifecycle; introduce analysis-run records if retaining prediction history in the database. |
| `apps/pulse/models.py::TextAnnotation` | Stores answer/theme, integer confidence, evidence and model version; no assignment-review state | Add a floating-point model score and a separate human annotation/review model. Retain existing confidence only for compatibility with heuristic outputs. |
| `apps/pulse/views.py::review_text_theme` | Approves/rejects survey-specific theme categories and reruns analysis on approval | This is not independent labelling of individual answers. Add a seven-label answer review form, including explicit reviewed-with-no-themes. |
| `services/text_analysis.py::survey_text_summary` | Counts distinct response IDs for prevalence and divides by `survey.response_count`; reads reviewed categories without filtering by model version | Preserve this calculation deliberately for application comparisons. If prediction history is retained, filter every reader to an active analysis run. Category status does not establish assignment correctness. |
| `services/imported_analytics.py` | Employee details use answer annotations and compare detected theme names with the previous period | Update these readers too; model changes can otherwise appear to be employee/theme changes. |
| `templates/surveys/text_analysis.html` | Displays “% confidence” beside selected excerpts | Display “model score” and complete answer context for TF-IDF. Do not present a score as validated certainty or an unevaluated sentence as the explanation. Audit employee templates as well. |
| `services/queries.py` and `services/synthetic_repository.py` | General dashboard/theme pages use demonstration data | Changing imported-text analysis will not make the general demo dashboards reflect learned predictions. Treat connecting those pages to imported data as a separate application task. |
| `tests/test_app.py` | Includes import, local theme analysis, approval and reimport workflow tests | Extend these for the ML backend. Existing workflow assertions do not measure accuracy on unseen text. |
| `pyproject.toml` | No scikit-learn dependency or ML extra | Add an `ml` extra containing tested scikit-learn and persistence dependencies, and save exact resolved training/inference versions. |

Two data details need explicit decisions:

- `ImportedResponse.respondent_key` is an HMAC of email/name when available; anonymous keys are local to the survey period. Names can collide and identity fields can change. Validate the available linkage and document when cross-period person grouping cannot be guaranteed. Keep the pseudonymous key out of model features.
- Reimport deletes and recreates questions/responses/answers, so UUIDs are not durable research identifiers across reimports. A review model with cascading answer foreign keys would also be deleted. Freeze an independently versioned, de-identified research export before experiments; define a snapshot/preservation policy for reviews before permitting reimport of labelled data.

## 3. Target architecture and files

Keep dataset preparation and training outside HTTP requests. Keep Django responsible for extracting/reviewing data and saving inference results.

```text
Imported written answers -> de-identified snapshot -> independent human labels
                                                 -> frozen group split manifest
Training partition -> TF-IDF + classifiers -> validation selection -> model artifact
Frozen test partition -------------------------------> final evaluation report

Upload / refresh / analysis command -> configured artifact -> answer predictions
                                      -> active annotations -> existing summaries
Human review -------------------------> separate reference labels / corrections
```

Proposed locations below do not exist yet unless already present:

| File or area | Responsibility |
| --- | --- |
| `services/ml/dataset.py` | Validate the dataset schema, theme order and labels; create leakage groups and split manifests. No Django dependency needed. |
| `services/ml/baseline.py` | Evaluate frozen catalogue rules as a pure answer-to-label function, preserving sentence/token/match logic and the 0.20 similarity cutoff. Verify parity with current stored catalogue assignments. |
| `services/ml/train.py` | Fit candidates on training data, score validation data, choose the configuration and save the selected artifact. |
| `services/ml/evaluate.py` | Shared rule/TF-IDF metrics, prediction exports, prevalence calculations and grouped uncertainty estimates. |
| `services/ml/inference.py` | Load and validate an artifact; batch-transform texts; return scores and zero-or-more labels in fixed theme order. |
| `apps/pulse/management/commands/export_text_dataset.py` | Export an immutable research snapshot with explicit de-identification/review handling. Excluding name columns alone does not anonymise free text. |
| `apps/pulse/management/commands/train_text_model.py` | Explicit offline training entry point. Accept dataset, split manifest, config and output directory. |
| `apps/pulse/management/commands/evaluate_text_model.py` | Explicit evaluation entry point with validation/test mode and immutable result directory. |
| `apps/pulse/models.py` and migrations | Human annotation records, score storage and analysis-run identity if retaining predictions. |
| `services/text_analysis.py` | Select rules/TF-IDF backend and persist results using the existing application boundary. |
| `tests/test_ml_dataset.py`, `tests/test_ml_inference.py`, `tests/test_app.py` | Dataset contract, artifact/inference behaviour and application regression checks. |
| `ML/configs/`, `ML/evidence/` | Versioned experiment definitions, sanitised report templates and evidence register. |

Use settings such as `PEOPLE_PULSE_TEXT_BACKEND` and `PEOPLE_PULSE_TEXT_MODEL_PATH` for explicit selection. Start with rules as the default until evaluation supports adoption. Pin and deploy the same dependency environment used to produce the artifact; do not install a latest version implicitly at inference time.

The artifact bundle should contain the fitted pipeline, ordered theme identifiers, selected thresholds, input/label schema versions, model ID, dataset/split/config hashes, code revision (or source snapshot hash), exact dependency versions and creation time. Validate these before writing any predictions. Load only artifacts produced by the trusted training process: pickle/joblib loading can execute code. [scikit-learn persistence guidance](https://scikit-learn.org/stable/model_persistence.html).

## 4. Dataset and annotation work package

1. Inventory eligible written answers by survey, question and period. Report missing/whitespace answers, response-type mistakes, language, answer lengths, duplicate text and identity-linkage limitations. The small sample CSVs and repeated response bank are suitable for workflow examples, not representative accuracy evidence.
2. Define the seven themes with inclusion/exclusion examples. Label theme presence independently of positive/negative sentiment. Include short answers, overlap and reviewed answers with no applicable theme.
3. Export de-identified text with stable snapshot example IDs. Retain a restricted mapping to live answer IDs only where needed for review lineage. Record data-use basis, extraction query, transformations and snapshot hash.
4. Have a second person independently label a subset without seeing rule/model predictions. Retain original judgements, per-theme agreement, disagreement notes and adjudicated labels.
5. Freeze completed reference labels before splitting. Unreviewed answers are not all-negative examples. Store both binary values per theme and a review-complete flag.

Suggested research row schema:

| Field | Use |
| --- | --- |
| `example_id`, `snapshot_version`, `source_answer_id` | Traceability within the frozen snapshot; keep the live source mapping restricted. |
| `text` | De-identified classifier input. |
| `respondent_group_id`, `survey_id`, `period`, `question_id` | Splitting, source analysis and prevalence; excluded from text features. |
| `duplicate_family_id`, `template_family_id`, `leakage_group_id` | Keep related examples together. |
| Seven fixed binary label columns | Human reference targets in the persisted catalogue order. |
| `review_complete`, annotation revision/notes | Distinguish complete negatives from missing labels. |

Combine respondent and duplicate/template links into connected groups before assigning splits: grouping on respondent alone does not prevent duplicate text crossing partitions. Aim for 70/15/15 train/validation/test, then inspect per-theme positives and negatives and group sizes. A giant connected group or missing theme coverage is a dataset problem to document, not a reason to silently leak examples. Grouped splitting does not guarantee balanced multi-label coverage.

For a small dataset, use a reserved final test partition and grouped cross-validation in development data. Keep an untouched challenge set for diagnostic cases, reporting it separately from representative test performance. Include negation, paraphrases, multiple themes, misspellings, question-dependent replies, and unknown words.

**Evidence:** source/data dictionary, annotation guide, pilot changes, agreement/adjudication report, de-identification log, dataset hash, source counts, split IDs/seed, leakage-check output, label counts by partition and documented exclusions. Keep answer-level data and vocabulary-bearing artifacts in restricted storage outside ordinary Git; add ignore rules before generating local datasets/runs.

## 5. Training and validation work package

Use a scikit-learn `Pipeline` containing `TfidfVectorizer` and `OneVsRestClassifier(LogisticRegression(...))`, with an `n_answers x 7` binary target matrix. One-vs-rest supports independent multi-label decisions. [TF-IDF documentation](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html), [one-vs-rest documentation](https://scikit-learn.org/stable/modules/generated/sklearn.multiclass.OneVsRestClassifier.html).

Start with a deliberately small search:

| Setting | Initial candidates / fixed choice |
| --- | --- |
| Word n-grams | `(1, 1)` versus `(1, 2)` |
| Stop words | `None`; retain `no` and `not`. Do not reuse the baseline's stop-word set, which removes `not`. |
| Minimum document frequency | Start with `1`; record vocabulary size. Evaluate a higher value later only as a recorded development experiment. |
| Regularisation `C` | `0.1`, `1`, `10` |
| Class weighting | `None` versus `balanced` |
| Iteration limit | Set an explicit limit, inspect convergence warnings and resolve/document nonconvergence. |
| Decision thresholds | Initially `0.5` for each theme; optional validation-only tuning afterwards. |

This gives 12 initial configurations. Save every run, including failures, with training time and validation metrics. Choose by validation macro-F1, inspect per-theme precision/recall and use a documented tie-break favouring simpler features. Record training metrics to diagnose overfitting, without using them as evidence of generalisation.

Fit vocabulary, IDF and classifiers only on the training partition, or inside each training fold during cross-validation. Transform validation/test with the fitted pipeline. This prevents preprocessing leakage. [scikit-learn common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html).

Before fitting, fail clearly if a theme lacks positive or negative training examples. Before reporting, flag insufficient validation/test support rather than treating undefined metrics as proof of good performance. Persist the full seven-theme order even when a label is rare.

If tuning thresholds, record the search range, objective and number of trials. Prefer shared thresholds when per-theme validation support is weak. Scores across themes need not sum to one. Treat them as uncalibrated model scores, particularly with balanced class weighting.

For the first experiment, retain the winning pipeline fitted on the original training partition and its validation-selected thresholds for final testing. Do not silently refit on training plus validation while retaining thresholds chosen for the previous fit. A later combined-data release model requires its own documented fitting/threshold protocol and separate artifact identity.

**Evidence:** exact environment export, source revision/hash, run commands, immutable configs, training logs/warnings, configuration comparison CSV, selection rationale, fitted artifact checksum, vocabulary size, thresholds and training/validation support. Show a reproducibility rerun within stated numerical tolerances. Epoch/loss plots are not required for this classical pipeline; validation comparisons and learning curves, if justified by data volume, are more informative.

## 6. Final ML testing work package

Freeze the selected configuration and adoption criteria before inspecting final test results. Run the unchanged catalogue rule comparator and selected TF-IDF artifact on exactly the same held-out examples. The catalogue comparator excludes approved survey-local topics because they are outside the seven-label target; report those separately if needed.

| Result | Evidence to retain |
| --- | --- |
| Per-theme precision, recall, F1, positive support and TP/FP/FN/TN | Seven-theme table; explain undefined values and rare labels. |
| Macro-F1 and micro-F1 | Side-by-side rule and TF-IDF results with configuration/run IDs. |
| No-theme and multi-theme answers | False theme assignment rate for no-theme answers; quality of multi-theme predictions and sample counts. |
| Uncertainty | Bootstrap leakage groups for score differences where feasible; record seed/method and limitations of small samples. |
| Prevalence error | Per-survey/theme predicted minus human prevalence and absolute error in percentage points, using identical eligible response sets. |
| Operational cost | Artifact size, load time, batch throughput and end-to-end upload/refresh timing on named hardware and dataset size. |
| Errors | De-identified examples of false positives/negatives, grouped by failure pattern; include good and poor cases. |
| Challenge cases | Separate diagnostic table, without merging its curated results into the representative score. |

For prevalence, first combine all labelled answers belonging to a response row. Human absence can only be asserted if all relevant written answers for that row were reviewed. If only some answers are labelled, do not treat missing labels as negative or claim full-survey prevalence. Compare within fully covered response rows, with an explicit denominator, or label the calculation as prevalence of the evaluated answers only.

The current UI uses distinct **response rows**, not deduplicated respondent keys. Repeated submissions can therefore count twice. Keep the existing response-row definition for initial parity and document it; evaluate deduplicated-person prevalence separately if the product definition changes. Survey-level aggregate estimates also need enough independently represented groups to be meaningful.

Adoption criteria should specify a useful macro-F1 improvement, tolerable per-theme precision/recall changes, prevalence error and inference/review burden. Agree concrete values from the pilot and user needs before final testing; do not invent a pass threshold after seeing test scores. Report an inconclusive or worse result candidly.

After test inspection, any model revision prompted by those errors needs a fresh untouched evaluation set for an unbiased new result. Do not relabel model disagreements just to improve the metric; record legitimate reference-label corrections transparently.

**Evidence:** test dataset/split hashes, model/baseline versions, evaluation command/log, scores for every example in restricted storage, aggregate tables, confusion charts, bootstrap method/output, prevalence table, timed execution and a signed/dated model-selection decision. A screenshot of training completing cannot substitute for these results.

## 7. Application integration and software testing

Implement integration after the offline evaluation pipeline works; enable TF-IDF for users only if evidence supports it.

1. Add independent answer-label records with reviewer, timestamp, label set and review status. A reviewer can mark an answer reviewed with zero labels. Store original references/corrections independently of refresh-generated annotations, with a reimport preservation policy.
2. Add score and analysis-run identity. Prefer a run record containing backend/model/threshold versions, status, counts and timing; a completed run can be selected as active for the survey. The existing 40-character model-version field can hold a short ID; put full hashes in the manifest/run record.
3. Make all summary, employee and trend queries select the active run, preventing old/new outputs from mixing. Compare periods under the same model where possible, or explicitly flag the model change.
4. Load one trusted validated pipeline per process/artifact revision, infer in batches and save full-answer context. Ignore blank input; flag all-out-of-vocabulary input for review instead of silently relying on classifier intercepts. Preserve zero-theme outcomes without inventing a theme.
5. Keep catalogue classification distinct from optional rules for survey-local topics and sentiment. Record the relevant source versions separately. If retaining sentiment, evaluate its sentence/answer scope; do not imply TF-IDF trained it.
6. Validate/load/predict before replacing the active output. A missing, incompatible or corrupt artifact must leave the last successful analysis intact and produce a clear failure state. Any configured fallback to rules must be visible and carry its own backend/version.
7. Update text and employee UI wording, add assignment review, and measure upload timing. Introduce background execution only if measured transaction/latency limits warrant it, with explicit pending/completed states.

| Software check | What it establishes |
| --- | --- |
| Dataset validation and split tests | Incomplete labels excluded; theme order fixed; linked respondent/duplicate families cannot cross splits. |
| Frozen baseline parity | Extracted evaluation logic reproduces existing catalogue assignments on controlled multi-sentence examples. |
| Artifact round trip | Save/load retains scores and labels within numerical tolerance; manifest mismatch fails before saving annotations. |
| Inference contract | Batch and single-answer output agree; blank, unseen-vocabulary and multi-label cases follow the documented behaviour. |
| Failure/rollback | Bad artifact or inference failure preserves active results and reports the failure; explicit fallback shows its real version. |
| Refresh and version changes | Reruns are idempotent for the active run; human labels survive; historical predictions cannot contaminate summaries. |
| Import/reimport | Uploaded written answers reach inference; numeric/dimension answers do not; labelled snapshots remain traceable across reimport. |
| Prevalence calculation | Multiple answers for a response count once; repeated-response denominator and missing-label policy match the documented definition. |
| Review permissions and UI | Existing role controls protect corrections; zero-label review is possible; scores/category approval are accurately described. |
| User task evaluation | Reviewers can locate relevant answers, correct wrong assignments and understand the outputs; compare task time/errors with the existing workflow. |

Use small controlled fixtures for software behaviour, not as ML accuracy evidence. Run the existing non-UI pytest suite plus the new tests; run relevant browser journeys when the interface changes. Record actual commands, environment, date, pass/fail output, defects and retests. This documentation review did not execute the application tests.

## 8. Evidence pack and delivery order

Use the existing evidence IDs in [the project KSB plan](../docs/project-ksb-evidence-plan.md). Evidence should explain the engineering decision and outcome as well as showing an artifact.

| Order | Deliverable / gate | Main evidence packs |
| --- | --- | --- |
| 1 | Freeze rule baseline; confirm task, data route and draft adoption criteria | E03, E06, E08 |
| 2 | Annotation pilot, independent agreement and source profile | E07 |
| 3 | Freeze labelled snapshot/splits; pass leakage and coverage checks | E05, E07 |
| 4 | Build shared evaluation harness and record rule metrics | E04, E05, E08 |
| 5 | Run 12 TF-IDF configurations; select on validation; reproduce winning run | E04, E08 |
| 6 | Evaluate frozen models on final test data; record adoption decision | E08, E12 |
| 7 | Integrate versioned inference/review; pass regression and failure checks | E04, E05, E09 |
| 8 | Measure reviewer usefulness and document limitations | E10, E11, E12 |
| 9 | Optional frozen sentence-embedding experiment under the original research scope | E08, E12 |

For each run, retain a restricted evidence bundle such as:

```text
<restricted-storage>/text-ml/<run-id>/
  manifest.json                  # Dataset/split/code/config/model hashes and versions
  environment.txt                # Exact runtime and resolved dependencies
  config.json                    # Features, C, weighting, seed and threshold protocol
  train.log                      # Command, timing, warnings, failures
  validation-comparison.csv      # All candidates and selection evidence
  pipeline.joblib                # Trusted fitted artifact; may reveal vocabulary
  thresholds.json                # Fixed ordered themes and cutoffs
  evaluation.log                 # Evaluation command and partition
  predictions.csv                # Example IDs, reference labels, scores and decisions
  metrics.json                   # Aggregate and per-theme measures/support
  prevalence.csv                 # Cohort/period, denominator and prevalence errors
  error-analysis.csv             # Restricted examples and failure categories
  model-report.md                # Intended use, selection, results and limitations
```

Keep reusable code/configs and sanitised aggregate reports in the repository. Keep identifying text, row-level predictions, linkage files and fitted vocabulary artifacts in restricted storage. The evidence register can point to those artifacts using IDs/checksums without publishing their contents.

Minimum model report structure: problem and intended use; data provenance and annotation; split/leakage controls; frozen rule comparator; candidate search and validation choice; held-out results with support/uncertainty; application cost and user effects; error patterns; adoption/rollback decision; limitations and next experiment. Map data work to E07, experimental results to E08 and software checks to E05; none alone proves all three.

The immediate dependency is an independently labelled dataset. Begin with the annotation pilot and reproducible rule-evaluation harness; these establish whether there is enough coverage to train and assess TF-IDF credibly.
