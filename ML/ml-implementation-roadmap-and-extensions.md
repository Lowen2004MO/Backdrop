# ML implementation roadmap and future inference opportunities

Prepared: 16 October 2026. Status: proposed; no new model training or production deployment is claimed by this document.

This document expands the [ML training plan](training-plan.md) into an end-to-end delivery sequence. It is intended to be used alongside the more repository-specific [TF-IDF implementation and evidence plan](tfidf-implementation-and-evidence-plan.md). The immediate objective is a defensible multi-label classifier for the seven existing employee-feedback themes. The later sections describe additional analyses that could be built once the data, privacy controls and evaluation practice are mature enough.

Expanded after reviewing both plans and the current application on 16 October 2026. Sections 8–10 supply the detailed implementation contracts, experiment protocols and further data-analysis work packages. Section 11 gives a prioritised reading route. All new modules, commands, database records and configurations below are proposals unless explicitly described as current code.

## 1. Scope and non-goals

The first system should answer one bounded question:

> Which of the seven existing themes are expressed in this complete written answer?

The target is multi-label: one answer may have several themes or none. The initial features should be the de-identified answer text only. Respondent identifiers, names, demographic attributes, survey scores and cohort fields must remain outside the model features.

The first release should not claim to infer an employee's performance, personality, protected characteristics, mental-health status or likelihood of leaving. It should not turn a model score into a validated probability, and it should not make causal claims about why a survey result occurred. Sentiment, new-topic discovery and recommendations are separate products with separate labels, risks and evaluation criteria.

## 2. Target technical architecture

```text
Survey import
    -> written-answer extraction
    -> restricted de-identification and research snapshot
    -> human annotation / adjudication
    -> grouped split manifest
         |-> rules baseline
         |-> TF-IDF + one-vs-rest classifier
         |-> frozen sentence-embedding classifier (later)
    -> validation selection
    -> frozen test evaluation
    -> versioned model artifact

Application inference
    -> validate artifact and input schema
    -> batch prediction
    -> analysis run + answer-level predictions
    -> existing summaries and employee views
    -> separate human review/correction records
```

Training must happen offline, from an explicit command or reproducible job. Uploading a survey should load a trusted, versioned artifact; it must never silently retrain the model. Django/application code should own extraction, persistence, permissions and display. Pure dataset, training, evaluation and inference modules should be usable without HTTP requests.

Suggested boundaries:

| Component | Responsibility |
| --- | --- |
| `services/ml/dataset.py` | Dataset schema, label validation, de-identification checks, leakage groups and split manifests. |
| `services/ml/baseline.py` | Frozen rule-based answer-to-label comparator. |
| `services/ml/train.py` | Candidate pipelines, validation search, artifact creation and manifest generation. |
| `services/ml/evaluate.py` | Shared metrics, prevalence comparisons, uncertainty and error exports. |
| `services/ml/inference.py` | Trusted artifact loading, schema checks, batch prediction and threshold application. |
| `apps/pulse/management/commands/export_text_dataset.py` | Restricted, immutable research snapshot export. |
| `apps/pulse/management/commands/train_text_model.py` | Explicit offline training entry point. |
| `apps/pulse/management/commands/evaluate_text_model.py` | Reproducible validation/test evaluation entry point. |
| `ML/configs/` | Versioned experiment configurations, without raw responses. |
| `ML/evidence/` | Sanitised aggregate reports and evidence indexes. |

## 3. Delivery stages

### Stage 0 — Freeze the product question and the current baseline

Before changing code, define:

1. The seven theme IDs and their permanent ordering.
2. Whether a label means that the theme is mentioned, is a problem, or is a positive/negative experience. Do not mix these meanings.
3. The unit of prediction: initially one complete written answer.
4. The aggregation unit for reporting: currently distinct response rows, unless the product definition is deliberately changed.
5. What happens to blank answers, non-written answers, unknown language and answers with no applicable theme.
6. Adoption criteria agreed before final test results are inspected.

Run the existing rules against a controlled fixture and save its outputs as the comparator. Freeze the implementation/version used for the comparison. The current heuristic confidence and cosine similarity values are not calibrated probabilities.

**Exit evidence:** task specification, theme catalogue, baseline output fixture, baseline version, aggregation definition and draft adoption criteria.

### Stage 1 — Audit data and establish governance

Inventory eligible answers by survey, question, period and response type. Report:

- missing and whitespace-only answers;
- answer length distribution and language assumptions;
- duplicate and near-duplicate text;
- repeated submissions and respondent linkage quality;
- possible names, emails, employee numbers and other identifiers in free text;
- label availability by theme and by source period;
- retention, access and deletion requirements.

Create a data dictionary and an explicit data-flow record. A pseudonymous respondent key is useful for grouped splitting, but it is not automatically anonymous: free text can identify people, and an HMAC key can still be linkable inside the application. Keep the live-ID mapping restricted. Do not put raw responses, fitted vocabularies or row-level predictions in ordinary Git.

**Exit evidence:** source inventory, risk assessment, data dictionary, access decision, de-identification procedure and snapshot storage location.

### Stage 2 — Create a labelled research snapshot

Export an immutable snapshot with stable research IDs. A recommended row contains:

```text
example_id, snapshot_version, text,
respondent_group_id, survey_id, period, question_id,
duplicate_family_id, template_family_id, leakage_group_id,
theme_workload, theme_manager, theme_career, theme_communication,
theme_tools, theme_team, theme_change,
review_complete, annotation_revision, annotation_notes
```

Keep `source_answer_id` in a restricted lineage table, not in the model feature matrix. De-identification must include text review or automated detection followed by review; dropping a name column is not sufficient.

Do not represent “not labelled” as seven negative labels. A complete negative example means an annotator explicitly reviewed the answer and found none of the seven themes. Exclude incomplete rows from training and evaluation.

**Exit evidence:** snapshot hash, row counts, exclusion log, de-identification log, schema validation output and label coverage table.

### Stage 3 — Write and test the annotation guide

For each theme define inclusion rules, exclusions, borderline cases, overlap rules and at least several positive and negative examples. Clarify whether a statement such as “the software is fine but deadlines are impossible” receives one or two labels.

Run a pilot with two independent annotators. Keep the original judgements, not just the final adjudicated value. Report per-theme agreement, support counts and disagreement examples; do not rely on one aggregate agreement score for rare labels. Adjudicate the pilot, revise the guide, then freeze the version used for the main dataset.

The current keyword rules must not be used as ground truth. Otherwise the experiment mainly measures how well a new model reproduces the old rules.

**Exit evidence:** annotation guide revision, independent labels, per-theme agreement, adjudication decisions and completed-label definition.

### Stage 4 — Build leakage-safe splits

Create connected leakage groups from respondent identity, duplicate text, near-duplicates and synthetic template/paraphrase families. Every member of a group must remain in one partition. Use approximately 70/15/15 train/validation/test where the data allows it, but prioritise defensible group separation and adequate theme support over exact percentages.

For a small dataset, reserve a final test set and use grouped cross-validation within the development data. Fit the vectoriser and every preprocessing step inside each training fold. Save split assignments, grouping rules and random seeds. Check label counts after splitting; if a rare theme has no positive examples in a partition, report the limitation rather than fabricating balance.

If enough periods exist, add a later-period evaluation. This tests temporal generalisation and is different from testing on entirely new respondents.

**Exit evidence:** split manifest, leakage-group report, label counts per partition, duplicate checks, seed and cross-validation configuration.

### Stage 5 — Implement the reproducible baseline and candidates

The first candidate should be:

```python
Pipeline([
    ("tfidf", TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words=None,
        min_df=1,
    )),
    ("classifier", OneVsRestClassifier(
        LogisticRegression(max_iter=2000, C=1.0)
    )),
])
```

Treat this as an illustrative starting configuration, not a final setting. Search a small, recorded grid over word unigrams versus unigrams+bigrams, `C` values such as 0.1/1/10, and `class_weight=None` versus `balanced`. Retain `not` and `no`; generic stop-word removal can destroy useful negation cues. Check convergence warnings and vocabulary size.

Fit the pipeline only on training data. Produce one score and one binary decision per theme. Scores across themes do not sum to one. Initially use 0.5 thresholds; tune per-theme thresholds only on validation data and only where support is sufficient. Persist the fixed theme order and thresholds.

The later embedding candidate should use an exact sentence-transformer model revision, a documented truncation policy and the same one-vs-rest evaluation design. Keep the encoder frozen initially. Fine-tuning is a separate, higher-risk experiment requiring more labelled data and stronger compute/reproducibility controls.

**Exit evidence:** source revision, environment lock/export, configuration files, run logs, all candidate results, convergence status, selected validation configuration and artifact checksum.

### Stage 6 — Evaluate quality and practical impact

Evaluate rules and trained candidates on identical held-out examples. Report per theme:

- precision, recall, F1 and positive support;
- true/false positives and negatives;
- macro-F1 and micro-F1;
- no-theme and multi-theme performance;
- confidence intervals or grouped bootstrap uncertainty where feasible.

Also measure application impact: theme prevalence error in percentage points, review workload, abstention/uncertainty rate, model load time, batch throughput, memory and upload/refresh duration. Bootstrap respondent or leakage groups rather than pretending individual answers are independent when they are not.

Maintain a separate challenge set containing negation, mixed themes, short answers, misspellings, question-dependent replies, paraphrases, unknown words and out-of-catalogue topics. Challenge-set performance is diagnostic and must not replace representative test performance.

Inspect false positives and false negatives by failure mode. Do not repeatedly tune on the final test set. Any change prompted by test findings requires a fresh untouched evaluation set.

**Exit evidence:** aggregate metrics, per-example predictions in restricted storage, prevalence table, uncertainty method, operational timings, challenge-set results and de-identified error analysis.

### Stage 7 — Package and validate the model artifact

An artifact bundle should include:

```text
pipeline.joblib                 # trusted fitted pipeline
manifest.json                   # model, schema, code, dataset and config hashes
thresholds.json                 # ordered theme IDs and cut-offs
environment.txt                 # exact runtime/dependency versions
model-report.md                 # intended use, results and limitations
```

Validate before inference: artifact format, theme order, schema version, expected feature contract, dependency compatibility and checksum. Loading pickle/joblib files is code execution; load only artifacts from a trusted training process. Keep an active model ID and a rollback target.

Do not silently refit on training plus validation after choosing thresholds on the old fit. A release trained with a different protocol needs a new artifact identity and evaluation record.

### Stage 8 — Integrate application inference and review

Add an analysis-run identity containing backend, model ID, thresholds, start/end time, status, counts and failure details. Save predictions against the active run. Ensure summaries, employee views and trend comparisons filter consistently by that run and do not mix model versions.

Keep model predictions separate from human corrections. A reviewer must be able to mark an answer as reviewed with zero themes, correct one assignment without approving an entire category, and see the complete answer context. Rerunning analysis must not erase human reference labels.

Inference should be batch-oriented and idempotent. Blank answers should be skipped explicitly. All-out-of-vocabulary answers should be flagged for review rather than treated as reliable intercept-only predictions. If loading or prediction fails, preserve the last successful active run. If a rules fallback exists, show that it was used and record its own version.

Update UI wording from “confidence percentage” to “model score” unless calibration has been demonstrated. Do not identify a particular sentence as an explanation unless sentence-level evidence selection has itself been evaluated.

### Stage 9 — Test, deploy and monitor

Add tests for:

1. dataset schema, complete negatives and fixed theme order;
2. respondent/duplicate/template leakage prevention;
3. baseline parity on controlled examples;
4. artifact save/load score equivalence;
5. single-answer and batch inference equivalence;
6. blank, unseen-vocabulary and multi-label behaviour;
7. corrupt-artifact failure and rollback;
8. reimport/reanalysis preservation of human labels;
9. active-run filtering in summaries and employee views;
10. permissions and review workflow;
11. timing and memory on a named representative fixture.

After deployment, monitor input volume, answer length/language drift, out-of-vocabulary rate, label prevalence, score distributions, review corrections, abstentions, latency and failures. Do not treat drift as proof of model degradation without new reference labels. Periodically sample answers for fresh annotation and compare against the frozen baseline and previous model version.

**Exit evidence:** test commands and results, release checklist, rollback test, monitoring definition, incident procedure and model card/report.

## 4. Additional ML opportunities

These are candidate workstreams, not assumptions that the first theme classifier can perform them automatically.

| Opportunity | Useful output | Data/technical requirement | Main caution |
| --- | --- | --- | --- |
| Aspect-based sentiment | Sentiment attached to a theme/aspect, e.g. tools negative but team positive | Sentence/aspect sentiment labels; negation and mixed-sentiment evaluation | Do not reuse theme labels as sentiment labels. |
| New-theme discovery | Clusters or candidate topics outside the seven-theme catalogue | Embeddings, clustering/topic model, human naming and stability checks | A cluster is not automatically a real organisational theme. |
| Theme hierarchy | Broad theme plus subtheme such as workload → deadlines/capacity | Hierarchical annotation and enough examples per child label | Child labels can be sparse and inconsistent. |
| Urgency/actionability | Flag answers needing prompt review and identify requested action | Explicit urgency/actionability labels and reviewer agreement | Do not infer risk to an individual or promise that action will occur. |
| Semantic search | Find similar historical answers and supporting examples | Embedding index, access controls, retention and deduplication | Search can expose sensitive text across groups. |
| Duplicate/template detection | Identify repeated or copied responses before evaluation | Character/semantic similarity and leakage-group construction | Similarity must not be used to dismiss genuine repeated concerns. |
| Summarisation | Period/theme summaries with linked supporting evidence | Retrieval plus constrained summarisation and human verification | Generated summaries can omit minority views or invent claims. |
| Trend/change detection | Detect changes in theme prevalence or wording over periods | Stable model version, denominators, time-aware uncertainty | Changes may reflect survey composition or wording, not real causes. |
| Question-aware classification | Use survey question plus answer for context-dependent replies | Separate experiment with question leakage checks | Question text can make results incomparable across surveys. |
| Multilingual support | Classify non-English answers consistently | Language inventory, multilingual model and per-language labels | Translation can alter meaning; report per-language performance. |
| Weak supervision | Scale labelling using rules/labeling functions | Multiple noisy sources and a held-out human-labelled set | Weak labels cannot substitute for an independent reference set. |
| Active learning | Select uncertain/diverse answers for annotation | Uncertainty/diversity sampling and reviewer workflow | Sampling can distort prevalence estimates if not corrected. |
| Calibrated review queue | Route likely errors to humans using calibrated risk | Calibration set, calibration method and threshold policy | Calibration must be measured per theme and population. |
| Causal or predictive workforce analysis | Study whether themes relate to later aggregate outcomes | Pre-registered design, confounding controls and governance review | Association is not causation; avoid individual-level employment decisions. |

### Recommended order after the first classifier

1. Improve annotation and review capture; this gives every later model better supervision.
2. Add aspect-based sentiment as a separate labelled task if users genuinely need polarity.
3. Add duplicate detection and semantic search as operational aids, with access controls.
4. Explore new-theme clustering using embeddings, but require human naming and stability review.
5. Add time-aware trend and drift reporting using a fixed model version.
6. Consider summarisation only after retrieval, citation links and human verification are available.

## 5. Inferences that should not be made from this data

The system should not infer protected attributes from writing, diagnose health conditions, identify “difficult” employees, rank individuals, predict disciplinary or retention outcomes for individual decisions, or treat silence as agreement. It should not report a theme as prevalent when the denominator contains unlabelled answers. It should not use a model-generated summary as the sole evidence for an organisational decision.

For aggregate analysis, retain subgroup minimum-count rules, suppress small cells, preserve minority and negative cases, and document who can access raw text. Every derived metric should state its population, denominator, model version, uncertainty and missing-label policy.

## 6. Useful reading

### Core implementation

- [scikit-learn: `TfidfVectorizer`](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html)
- [scikit-learn: `OneVsRestClassifier`](https://scikit-learn.org/stable/modules/generated/sklearn.multiclass.OneVsRestClassifier.html)
- [scikit-learn: model evaluation](https://scikit-learn.org/stable/modules/model_evaluation.html)
- [scikit-learn: cross-validation and grouped splits](https://scikit-learn.org/stable/modules/cross_validation.html)
- [scikit-learn: common pitfalls and leakage](https://scikit-learn.org/stable/common_pitfalls.html)
- [scikit-learn: model persistence](https://scikit-learn.org/stable/model_persistence.html)
- [scikit-learn: probability calibration](https://scikit-learn.org/stable/modules/calibration.html)
- [Sentence Transformers documentation](https://www.sbert.net/)
- [Sentence-BERT paper](https://aclanthology.org/D19-1410/)

### Evaluation and interpretation

- [Multi-label classification metrics](https://scikit-learn.org/stable/modules/model_evaluation.html#multilabel-ranking-metrics)
- [Precision-recall trade-offs](https://scikit-learn.org/stable/modules/model_evaluation.html#precision-recall-f-measure-metrics)
- [SHAP documentation](https://shap.readthedocs.io/en/latest/) — use as an exploratory explanation aid, not proof that a feature caused a decision.
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)
- [Model Cards for Model Reporting](https://research.google/pubs/model-cards-for-model-reporting/)

### Topics and further modelling

- [BERTopic documentation](https://maartengr.github.io/BERTopic/)
- [Hugging Face task guides](https://huggingface.co/docs/transformers/tasks/sequence_classification)
- [Active Learning Literature Survey — Burr Settles](https://burrsettles.com/pub/settles.activelearning.pdf)
- [Datasheets for Datasets](https://dl.acm.org/doi/10.1145/3458723)

## 7. Definition of done for the first release

The first model is ready for a controlled application trial only when:

- the task, labels and data-use boundaries are documented;
- an independently labelled, de-identified snapshot exists;
- leakage-safe splits and a reproducible baseline are frozen;
- TF-IDF candidates are selected using validation data only;
- the final test comparison includes rules, support, uncertainty and prevalence impact;
- the artifact is versioned, checksum-validated and rollbackable;
- model outputs and human corrections are stored separately;
- existing summaries and trend views cannot mix analysis runs;
- application, failure and permission tests pass;
- reviewers understand the score and can correct individual assignments;
- limitations, monitoring and the next evaluation date are recorded.

If these conditions are not met, the appropriate outcome is a research result or prototype, not a production claim.

## 8. Detailed technical implementation

### 8.1 Dependency and execution boundaries

The current `pyproject.toml` has Django and application dependencies, but no ML extra. Add a tested optional `ml` group for scikit-learn, NumPy, SciPy and the chosen persistence library; add a separate embedding extra for Sentence Transformers and its runtime. Record exact resolved versions and Python version for each experiment. Choose compatible versions through installation and verification rather than copying a documentation site's latest version into the project.

Keep training off the web server. A local CPU workflow is a reasonable first implementation for sparse TF-IDF. Measure frozen-encoder encoding on the available hardware before choosing GPU infrastructure. The README describes a Lambda container runtime: assess container size, cold model loading, available memory and request duration before including an encoder in that runtime. A larger model does not automatically require a separate service; measurements should drive that decision.

Suggested command contracts, to implement before using these examples:

```powershell
python manage.py export_text_dataset --output <restricted-snapshot-directory>
python manage.py train_text_model --dataset <reviewed-data> --splits <manifest> --config ML/configs/tfidf-v1.json --output <restricted-run-directory>
python manage.py evaluate_text_model --dataset <reviewed-data> --splits <manifest> --artifact <trusted-artifact> --partition validation --output <restricted-results-directory>
```

Angle-bracket arguments are placeholders. These commands and the config file are proposed, not currently available. Export should fail if its destination would overwrite an existing snapshot. Training should never modify dataset labels or split assignments. Evaluation should write a new result directory containing model, dataset, split and configuration identities. A test evaluation needs an explicit frozen selection record; a command flag alone cannot stop a researcher looking at test results early.

Add ignore rules for the actual private dataset, cache, model and prediction directories before generating files. Retain sanitised configurations and aggregate evidence in source control. Avoid logging text or tokens while reporting failures.

### 8.2 Dataset validation and annotation contracts

Implement validation before any fit:

1. Require unique nonempty `example_id` values, a dataset schema version, text, group identity and annotation state. Decode text consistently as UTF-8 and record any Unicode/whitespace normalisation.
2. Reject nonbinary label values, missing labels on completed records, unexpected theme names and duplicate column names. Assert an explicit seven-column theme order; never derive it from alphabetical ordering or a set.
3. Exclude blank text and incomplete reviews with reason counts. Preserve explicit all-zero reviewed rows. Do not silently turn strings such as `"false"` into true booleans.
4. Keep respondent, period, question and lineage fields as metadata. Build `X` from text only and `Y` as a binary matrix with shape `(number_of_answers, 7)`.
5. Count per-label positives and negatives, label combinations, no-theme rows and multi-theme rows. Distinguish numbers of answers, response rows, people and leakage groups in the dataset report.
6. Record source type: real, manually constructed or synthetic. Preserve a synthetic generator/template family identifier. If the entire study is synthetic, state that in every headline comparison.

Stage 2 creates the snapshot and schema; Stage 3 supplies and freezes the completed reference labels. The final labelled snapshot is ready only after both stages. Keep original annotator decisions and adjudicated labels so agreement can be reproduced. An annotation guide must say that positive discussion of tools still expresses the tools theme: theme presence and dissatisfaction are different targets.

Reimport currently recreates application questions/responses/answers. Use stable IDs within the research snapshot and an independently retained mapping revision. Do not assume a foreign key to a current answer will preserve research evidence or corrections through reimport.

### 8.3 Split construction algorithm

Use a union-find structure or graph connected components to combine all known leakage relationships:

```text
Each answer starts in its own component.
Union answers sharing a reliable respondent identity.
Union exact duplicates and reviewed near-duplicate families.
Union examples generated from the same synthetic/paraphrase template.
Assign each resulting component one leakage_group_id.
Split whole components; write example_id -> partition to a manifest.
```

Use a fixed, label-independent normalisation for duplicate detection. Document manual decisions about near-duplicates; similar genuine concerns are not automatically copied answers. Anonymous keys may not link people across periods, so report uncertainty rather than claiming person-disjoint evaluation without evidence.

One implementation is a grouped holdout of roughly 15% of groups for test, followed by a grouped holdout of roughly 17.65% of the remaining groups for validation. Group size variation means answer proportions will not be exactly 70/15/15. Predeclare a small development-independent split selection procedure that checks label coverage; record rejected candidates and never select a split for favourable model scores. `GroupShuffleSplit` operates on groups, not a promise of exact row counts. [Grouped splitting documentation](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GroupShuffleSplit.html).

Assert that IDs and groups are disjoint, every eligible example occurs once, and linked families cannot cross partitions. If using grouped cross-validation, create explicit `(train_indices, validation_indices)` folds usable with the multilabel matrix. Do not assume `StratifiedGroupKFold` directly stratifies seven-label indicator targets: standard single-class stratification and multilabel balancing are different tasks. Review each fold's label support.

For temporal evaluation, set a date/period cutoff before model selection. A respondent-disjoint future test may require removing earlier observations of future test respondents from development. A future test allowing repeat respondents answers a different question; name that design explicitly.

### 8.4 Freeze the rule comparator

Extract a pure comparator or an adapter around the frozen rules. Match the current tokenisation, sentence splitting, synonyms and `0.20` similarity cutoff. Combine sentence matches by logical OR into seven answer-level decisions. Exclude survey-local approved topics from the seven-theme result matrix, since they are not reference target columns.

Use parity fixtures to verify the adapter against stored catalogue assignments. Include an answer with two sentences matching the same theme and one matching different themes. Preserve the baseline's version and any known weaknesses; correcting rules after reviewing development errors creates a new comparator version.

### 8.5 TF-IDF fit and feature inspection

An implementation skeleton for the first candidate is:

```python
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline

model = Pipeline([
    ("tfidf", TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2),
        stop_words=None, min_df=1,
    )),
    ("classifier", OneVsRestClassifier(LogisticRegression(
        C=1.0, class_weight=None, solver="liblinear",
        max_iter=2000, random_state=42,
    ))),
])

# Input validation and split-manifest loading happen before this block.
assert y_train.ndim == 2 and y_train.shape[1] == 7
assert np.isin(y_train, [0, 1]).all()
assert ((y_train.sum(axis=0) > 0) &
        (y_train.sum(axis=0) < len(y_train))).all()
model.fit(train_texts, y_train)
scores = model.predict_proba(validation_texts)
thresholds = np.full(7, 0.5)
predictions = (scores >= thresholds[None, :]).astype(np.uint8)
```

This is illustrative code for a validated dataset, not a complete training script. Verify solver compatibility in the pinned environment. Keep the sparse matrix sparse; converting a large vocabulary matrix to dense storage can dominate memory. Abort clearly on an empty vocabulary and resolve convergence warnings before accepting a fit.

Under the default smoothed IDF convention, a term's inverse-document factor is `log((1 + N) / (1 + df)) + 1`, followed by the vectoriser's normalisation. Each binary logistic model learns `sigmoid(w_j · x + b_j)` for theme `j`. Larger `C` means weaker regularisation. The independent outputs can select several labels and do not form a seven-way softmax. [Text feature extraction](https://scikit-learn.org/stable/modules/feature_extraction.html), [TF-IDF API](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html).

Run the 12 initial configurations from the existing TF-IDF plan: two n-gram choices × three `C` values × two weighting choices. Save configuration, fit duration, convergence state, vocabulary size and validation results for each. Use a recorded deterministic tie-break. Consider character n-grams only as a later ablation if misspellings or morphology are a demonstrated weakness.

Inspect each theme's largest positive and negative coefficients and a few local contributions `w_jk * x_k`. These explain contributions to the linear model's logit; they do not establish organisational causes. Check whether boilerplate, redaction markers or accidental identity fragments dominate. Restrict vocabulary-bearing inspection outputs because learned features can contain sensitive text.

### 8.6 Frozen sentence-embedding comparison

The full research question requires this comparison even if TF-IDF becomes the application's first integration. Implement the encoder path alongside the same dataset and evaluator:

1. Choose a compact candidate, for example `sentence-transformers/all-MiniLM-L6-v2`, after inspecting its model card, language coverage, licence and input limit. This is an experimental starting point, not a claim that it is best for this dataset. Record the exact downloaded revision and keep it fixed.
2. Encode de-identified answers in batches using a frozen encoder. Record device, batch size, pooling/normalisation settings, numerical dtype, token limit and runtime versions. Do not fine-tune or choose the encoder on test performance.
3. Inspect tokenised lengths. For an initial experiment, predeclare a truncation policy and report how often it applies. If chunking is needed, keep every chunk with its parent answer's partition and define a fixed pooling policy; evaluate it as a separate configuration. Chunk scores pooled by maximum are not automatically comparable to whole-answer scores.
4. Cache vectors using keys covering text content, encoder revision and preprocessing policy. Keep the cache restricted. A completely frozen, fixed encoder can transform each partition without learning from its labels; any learned scaling, dimensionality reduction or classifier fitting must use training data only.
5. Fit `OneVsRestClassifier(LogisticRegression(...))` on the dense vectors with the same small regularisation/weighting comparison and validation protocol. If adding a scaler, fit it only on training vectors and persist it with the classifier.
6. Persist classifier, encoder identity, preprocessing, thresholds and label order. Inference must reconstruct exactly that chain. Include the encoder files or a controlled model cache in the release design so prediction does not depend on an unrecorded download.
7. Measure encoding time separately from classifier fit and prediction. Report warm batch throughput and cold loading cost for both approaches. TF-IDF's simpler deployment may matter even if predictive results are similar.

Sentence encoders provide reusable vectors; their similarity is not a calibrated theme probability. [Sentence-BERT paper](https://aclanthology.org/D19-1410/), [Sentence Transformer API, including revision selection](https://www.sbert.net/docs/package_reference/sentence_transformer/model.html), [embedding usage](https://www.sbert.net/docs/sentence_transformer/usage/usage.html).

### 8.7 Selection, thresholds and calibration

Use a predeclared sequence: select hyperparameters on development results at shared `0.5` thresholds; optionally select a modest shared threshold on validation; only investigate per-theme thresholds where validation positives and negatives support that choice. Save every threshold tried and its objective. A small validation set used for many choices can itself be overfit; grouped development folds can reduce dependence on one small split.

Keep a distinction between the classification threshold, the score's calibration and the human-review policy. Improving F1 with a new cutoff does not calibrate scores. Calibration needs predictions from examples not used to fit the model being calibrated, with grouped separation retained. For independent theme classifiers, assess calibration per theme. Avoid fitting a flexible calibration method on very few positive examples. [Threshold guidance](https://scikit-learn.org/stable/modules/classification_threshold.html), [calibration guidance](https://scikit-learn.org/stable/modules/calibration.html).

For a review queue, start with distance from the selected threshold plus a separate all-out-of-vocabulary flag. Validate whether this actually finds errors; confident mistakes remain possible. Keep `review_required` separate from the seven theme decisions. Report error rate and coverage among automatically accepted predictions, plus total review workload. An all-zero theme vector is not by itself an abstention or proof of a new topic.

Retain the selected training-only fit for final testing. If later fitting a release model on more data, establish thresholds from grouped out-of-fold development predictions or another reserved calibration/validation partition under a documented protocol. Assign a new model ID; the original final-test score does not directly measure an unevaluated replacement artifact.

### 8.8 Database and inference contracts

Proposed records, extending the current `TextAnnotation` boundary:

| Record | Suggested fields and constraints |
| --- | --- |
| `TextAnalysisRun` | Survey, backend, short model ID, artifact/threshold/config identity, timestamps, status, input snapshot identity and counts. |
| Answer analysis result | Run + answer, completion/review-required state and optional seven-score payload. Unique `(run, answer)`; records successful zero-theme results. |
| Theme prediction | Run + answer + theme, floating score, decision and evidence scope. Unique `(run, answer, theme)` if retaining all seven decisions. |
| Human answer review | Stable snapshot example identity, reviewer, timestamp, guide revision, explicit completed flag and human label set; retain revision history. |
| Active analysis pointer | One selected completed run per survey, updated transactionally. |

The answer-result record matters: absence of a positive annotation otherwise cannot distinguish a completed all-negative answer from an unprocessed answer. Decide whether to retain all seven scores in application storage or only in the restricted research output, with a documented retention policy. Preserve the current integer heuristic confidence only as a compatibility field if required; use a float for the new model score.

Return a structured batch response such as `example_id`, ordered scores, selected theme IDs, backend/model ID, evidence scope and review reason. Reject score matrices with incorrect shape, nonfinite values or mismatched label order. For TF-IDF, inspect sparse row nonzero counts and flag zero-feature input. Validate trusted artifacts before prediction; checksums identify bytes, while trusted provenance determines whether the bytes should be loaded. [Artifact persistence guidance](https://scikit-learn.org/stable/model_persistence.html).

Read answers in bounded batches and load a validated artifact once per process/revision. Capture the input revision so a concurrent reimport cannot activate predictions for stale answers. Build a pending run, infer and validate outputs, save records, then atomically select the completed run. Failure leaves the previous active run selected. Test concurrent refreshes so one request cannot overwrite a newer result silently.

Update all readers in `services/text_analysis.py`, `services/imported_analytics.py` and the survey/employee templates. Preserve separate provenance for heuristic sentiment and local suggested topics. Category approval in `review_text_theme` remains distinct from human reference labels. The general demo dashboards in `services/queries.py` and `services/synthetic_repository.py` need a separate connection to imported analytics if they should display these predictions.

Start with settings such as `PEOPLE_PULSE_TEXT_BACKEND` and `PEOPLE_PULSE_TEXT_MODEL_PATH`, as proposed in the TF-IDF plan. Missing or incompatible artifacts should cause a visible analysis failure before old predictions are replaced. If timings justify background jobs, add a durable queue, retry/idempotency key, job status and a worker; do not rely on an untracked thread surviving a web request.

## 9. Evaluation calculations and evidence to produce

### 9.1 Classification and prevalence

For each theme, compute `precision = TP/(TP+FP)`, `recall = TP/(TP+FN)` and `F1 = 2TP/(2TP+FP+FN)`. Macro-F1 averages theme F1 values; micro-F1 pools decisions. Record undefined metric cases explicitly, even if library output uses `zero_division=0` for a machine-readable table. Report all seven themes, support, false-positive rates on reviewed no-theme answers and exact-set accuracy as a supplementary strict multilabel measure. [Evaluation reference](https://scikit-learn.org/stable/modules/model_evaluation.html).

For response-row prevalence, let `A_r` be all eligible written answers for response row `r`. Define `z_rj = max(y_aj for a in A_r)`, and compute `100 * sum(z_rj) / number_of_eligible_response_rows`. Repeat with predicted labels. The signed error is predicted minus human percentage; absolute error is its magnitude. Do not average answer scores or count every answer as a separate respondent.

Human-positive presence can be known from one labelled positive answer, but human-negative absence requires all relevant answers to be reviewed. Evaluate prevalence on fully covered response rows with the same denominator for predictions and reference. State that this subset may differ from the whole survey. The existing app denominator is `survey.response_count`; that measures response rows rather than verified unique people or only people providing text. If adding a text-respondent denominator, show it as a separate metric and label the change.

### 9.2 Uncertainty and comparisons

Compare models with paired predictions on the same examples. For a proposed grouped bootstrap, sample leakage groups with replacement, include all their rows and recompute both scores and their difference, for example across 1,000 seeded resamples. Report percentile intervals, group count, any invalid rare-label replicates and their handling. With few independent groups, show the uncertainty and avoid treating a narrow numerical difference as decisive.

Use separate named result tables for representative test, diagnostic challenge set, future-period evaluation and any synthetic-only test. Predeclare macro-F1 as the main selection measure and inspect important per-theme regressions. A lower aggregate prevalence error can hide opposing false positives and false negatives, so retain classification results alongside it.

### 9.3 Evidence files and operational checks

Produce:

- `dataset-report`: provenance, exclusions, review completion, theme counts and grouping limitations.
- `split-manifest` and validation output: identities, grouping algorithm, seed and coverage checks.
- `validation-runs`: one row per configuration, including failed/convergence-limited runs and selection rationale.
- `test-metrics` and `prevalence-results`: aggregate tables with denominators and uncertainty.
- `error-analysis`: categories of failures, counts and restricted example references.
- `runtime-report`: hardware, input size, load/encoding/classification time, memory, model size and end-to-end import time.
- `model-report`: exact selected artifact, intended task, limitations, adoption decision and rollback procedure.

Only add filled results after executing the experiments. In the repository, retain templates or sanitised aggregates rather than private row-level evidence. For the dissertation, show the reasoning from data quality to selection and practical usefulness; a screenshot of a completed fit does not establish generalisation.

Run dataset/artifact checks, targeted integration tests, the existing non-UI suite and Django checks when implementation lands. Run browser journeys for changed review screens. This document update does not implement those components or claim that application checks have passed.

## 10. Further inferences: concrete experiments and their limits

These work packages reuse the data pipeline, model versioning and evaluation discipline. Several useful questions are answered by statistical summaries before additional ML is needed. Each extension needs its own target, evidence and held-out evaluation where applicable.

### 10.1 Which themes occur together?

Build a response-row binary theme matrix and count pairs on eligible complete records. Report co-occurrence support and measures such as Jaccard overlap or lift alongside raw prevalence. For example, workload and tools may frequently coincide simply because both are common; compare observed overlap with what their marginal rates imply.

Bootstrap response/leakage groups for uncertainty. Inspect manually labelled subsets to see whether co-occurrence survives classification errors. Repeated pairs can suggest a joint investigation, but do not establish that one issue causes the other. This is a useful first extension because it needs no extra model or new sentiment labels.

### 10.2 Which themes are associated with low survey scores?

The current `survey_text_summary` already compares negative quantitative-answer rates between rows mentioning a theme and other rows. Extend this descriptive output deliberately rather than claiming it is a new trained capability.

Construct one row per response with seven theme indicators, quantitative outcomes, period and permitted cohort variables. Define the outcome in advance, for example a particular question's negative response. Compare an intercept/cohort/period baseline with a regularised model that also receives themes; use grouped splits, and time splits if making a future prediction claim. Train imputation/encoding only inside training folds. Report held-out predictive performance, support and uncertainty, and compare conclusions using human labels on an audited subset.

Account for people providing no written answer: missing text is not a negative theme observation. Avoid outcome leakage from text that directly repeats the target score. If using human labels to develop an outcome model but predicted labels in deployment, validate the full deployed chain; stacked training may require out-of-fold theme predictions. Correlated themes and cohort differences complicate coefficient interpretation. Describe findings as associations or predictive usefulness, not measured causes.

### 10.3 Is a theme discussed positively, negatively or in mixed terms?

Create `(answer, theme)` sentiment labels with positive, negative, neutral and mixed categories. Preserve examples containing different sentiment toward different themes. Start with manually identified theme instances so sentiment quality can be measured independently, then evaluate the joint theme-and-sentiment pipeline. Otherwise missed themes can disappear from the sentiment denominator.

Compare the existing word lists with a labelled aspect/theme-conditioned classifier. Use grouped splits, per-class macro-F1 and confusion counts, plus a negation/contrast challenge set. Show both theme mention prevalence and negative-theme prevalence with explicit denominators. This could distinguish positive tools discussion from tools complaints, which the current theme classifier cannot do. [Aspect-based sentiment task paper](https://aclanthology.org/S14-2004/).

### 10.4 What concerns fall outside the seven-theme catalogue?

Explore TF-IDF plus non-negative matrix factorisation as one topic baseline, or frozen embeddings plus clustering and, optionally, BERTopic. Include reviewed no-theme answers, high-uncertainty examples and a random sample of the whole corpus. Clustering only rejected examples can overemphasise misspellings or model failures rather than new concerns.

Inspect top terms and representative/deviant examples, repeat across seeds/subsamples and ask reviewers to name coherent groups independently. Evaluate stability, interpretability, coverage and genuinely new information. A two-dimensional embedding map is a visual aid, not evidence that separated-looking groups are reliable. New accepted categories require a new label schema, annotations and evaluation; they cannot be appended to the old seven-class score without changing the task. [NMF API](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.NMF.html), [clustering examples](https://sbert.net/examples/sentence_transformer/applications/clustering/README.html), [BERTopic](https://maartengr.github.io/BERTopic/index.html).

### 10.5 What has changed over time or between cohorts?

Reanalyse all comparable periods with one fixed model and threshold version. Compute response-row prevalence, sample counts, missing-text rates and uncertainty by period/cohort. Check question wording, respondent composition and repeated participation. Show raw and composition-adjusted comparisons separately where sample size permits.

A few quarterly points support descriptive comparisons more readily than a learned forecasting model. If enough periods accumulate, compare an anomaly/change detector or forecast with simple previous-period and seasonal baselines using rolling-origin evaluation. Never train on later periods to predict earlier ones. Classification error, changing participation and repeated hypothesis testing can all create apparent changes. A flagged movement is a reason to investigate, not evidence of a cause.

### 10.6 Which answers should reviewers label next?

Run active-learning rounds on the unlabelled development pool: combine near-threshold scores, diverse embeddings and a random sample; deduplicate before presenting a batch. Store the selection reason, model version, annotation time and reviewer correction. Compare learning curves with random sampling at equal annotation budgets.

Keep the final test set out of acquisition. An actively sampled batch is not representative for prevalence estimation or population accuracy. Maintain a separate random audit sample and report accuracy or annotation efficiency on appropriate held-out data. [Settles' survey](https://burrsettles.com/pub/settles.activelearning.pdf).

### 10.7 Can reviewers find relevant examples by meaning?

Build semantic search over authorised de-identified answers using the frozen embeddings. For a small corpus, use a simple in-memory similarity search before adding a vector database. Filter by user/survey permissions before returning candidates, honour deletion/reimport and keep model/index identities aligned. Retrieval query/document encodings may need different prompts depending on the chosen model.

Create reviewer queries with independently judged relevant answers; measure precision at `k`, ranking quality and task completion time against keyword search. Similarity is a retrieval score, not a theme confidence or a verified factual answer. This is a practical reuse of embedding work even if TF-IDF wins classification. [Semantic search implementation](https://sbert.net/examples/sentence_transformer/applications/semantic-search/README.html).

### 10.8 Can reports provide faithful summaries and useful actions?

Begin with an extractive report: counts, theme names and reviewer-selected de-identified excerpts. If adding generation later, retrieve a bounded authorised evidence set, require source references, keep numerical claims computed outside the generator and treat survey text as data rather than instructions. Preserve contrary and minority evidence.

Review summaries for unsupported statements, omitted concerns, polarity errors, identifying details and faithful source links. Evaluate claimed action items against separately labelled suggestions. A theme detector does not establish which intervention will work. Track proposed actions and later aggregate outcomes; causal impact requires a suitable comparison/design and cannot be inferred from a simple before/after change.

### 10.9 What additional context would improve classification?

Run controlled ablations for question-plus-answer input, character n-grams, multilingual encoders or hierarchical subthemes. Change one substantive factor at a time, retaining the same development protocol and independent evaluation. Question-aware models need checks against a question-only baseline and evaluation on new questions to reveal shortcuts. Multilingual reporting requires labelled examples and quality results per language; translation is a distinct pipeline to evaluate.

Choose only one or two extensions initially. A useful dissertation sequence is the three-way classifier comparison, followed by theme co-occurrence or audited theme-to-score associations. Aspect sentiment and new-topic discovery offer larger research scope but need substantial additional annotation or validation.

## 11. Prioritised reading route

Links below were checked during this review on 16 October 2026. The notes explain why each source matters for this project; documentation describes library behaviour, while the delivery choices above are proposed engineering decisions.

| Order | Reading | Use while implementing |
| --- | --- | --- |
| 1 | [Text feature extraction](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction) and [TF-IDF API](https://scikit-learn.org/stable/modules/generated/sklearn.feature_extraction.text.TfidfVectorizer.html) | Understand sparse word/phrase representations and choose explicit preprocessing settings. |
| 2 | [One-vs-rest classifier](https://scikit-learn.org/stable/modules/generated/sklearn.multiclass.OneVsRestClassifier.html) | Implement the seven-column binary target and independent theme decisions. |
| 3 | [Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html) and [grouped cross-validation](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data) | Build preprocessing inside folds and prevent respondent/duplicate leakage. Read before running experiments. |
| 4 | [Classification metrics](https://scikit-learn.org/stable/modules/model_evaluation.html) | Interpret macro/micro scores, confusion counts and rare-label support. |
| 5 | [Threshold selection](https://scikit-learn.org/stable/modules/classification_threshold.html) and [calibration](https://scikit-learn.org/stable/modules/calibration.html) | Separate binary decision policy from the reliability of a score. |
| 6 | [Sentence-BERT paper](https://aclanthology.org/D19-1410/) and [Sentence Transformers usage](https://www.sbert.net/docs/sentence_transformer/usage/usage.html) | Understand the embedding representation for the third research comparator. |
| 7 | [Model persistence](https://scikit-learn.org/stable/model_persistence.html) and [Model Cards for Model Reporting](https://research.google/pubs/model-cards-for-model-reporting/) | Plan reproducible loading, artifact trust and a clear final model report. |
| 8 | [Learning curves](https://scikit-learn.org/stable/modules/learning_curve.html) | Assess whether more labels improve performance and where annotation effort may help. |
| 9 | [Aspect-based sentiment](https://aclanthology.org/S14-2004/) | Plan labels for sentiment attached to a theme rather than an entire mixed answer. |
| 10 | [Clustering](https://sbert.net/examples/sentence_transformer/applications/clustering/README.html), [BERTopic](https://maartengr.github.io/BERTopic/index.html) and [semantic search](https://sbert.net/examples/sentence_transformer/applications/semantic-search/README.html) | Explore new topics and retrieval as separately evaluated extensions. |
| 11 | [Active Learning Literature Survey](https://burrsettles.com/pub/settles.activelearning.pdf) | Design annotation acquisition and compare it fairly with random sampling. |

For a first implementation, read items 1–4 while delivering data and TF-IDF, item 6 for the frozen-embedding comparison, and items 5 and 7 before application integration. The remaining reading supports optional experiments after the core comparison is reproducible.
