# Synthetic annotation pilot: your review guide

Prepared: 16 October 2026. Guide version: pilot-guide-v1.

This is a fully fictional 80-answer pilot. The answer text, draft labels and grouping metadata were authored by AI for this project; they do not come from employees, an external survey dataset or the application's keyword classifier. You are reviewing proposed labels, not confirming measured model predictions.

## Files to open

- [Data preview](data-preview.md): all 80 answers, readable proposed themes, draft reasons and label counts.
- [Review CSV](review.csv): editable labels, initially prefilled with AI suggestions. No row is human-reviewed yet.
- [Blind review CSV](blind-review.csv): the same answers with empty label columns, for independent annotation before looking at the suggestions.
- [Manifest](manifest.json): provenance, designed coverage, grouping links and initial checksums. Checksums describe the initial files; your edited review file is expected to differ.
- [Build script](build_pilot.py): the curated source and reproducible export. It refuses to overwrite existing output files so it cannot erase your edits.

Because every example is artificial and contains no real personal data, these pilot files can remain in the project. Do not add real employee answers to these public-style fixtures.

## How to review

1. Open `data-preview.md` for reading and `review.csv` in a spreadsheet editor for changes. Alternatively, annotate `blind-review.csv` first if you want to make your judgements without seeing AI suggestions. Work in one chosen CSV rather than editing both copies.
2. Read the whole answer and decide whether each of the seven themes is explicitly expressed or reasonably implied. Use the definitions below. Label the answer text itself; there is no hidden survey-question context.
3. Set every theme column to `1` for present or `0` for absent. More than one `1` is allowed. Topic presence does not depend on whether the writer is happy or unhappy.
4. If the answer fits none of the themes, set all seven columns to `0`. This is a valid completed negative example. Do not add an eighth `none` theme.
5. Add your initials or reviewer ID in `reviewer`. Record uncertainty, a correction or a proposed guide change in `annotation_notes`.
6. Once you have checked all seven decisions, set `review_complete` to `1` and change `label_source` to `human_reviewed_ai_draft`. For a blind annotation, use `human_independent`. If a decision remains unresolved, leave `review_complete=0` and explain why.
7. Keep IDs, source type, grouping metadata and answer text unchanged during the first pass. If text itself is flawed or you want a new theme, note that rather than quietly changing the prediction task.
8. Save as CSV UTF-8, preserving the header and all 80 rows. You can also send corrections in chat, for example `SYN-005: add communication; reason: ...`, and they can be applied to the CSV.

For a manageable first pass, review SYN-001–014, then continue in blocks. Pay particular attention to SYN-005, 019, 028, 033, 038, 048, 059 and 078: the draft guide deliberately sets boundaries around implied themes. Disagreeing with a suggestion is useful feedback for refining the guide.

## Theme definitions

The fixed order is `workload, manager, career, communication, tools, team, change`.

| CSV column | Theme and inclusion rule | Exclusions / boundaries |
| --- | --- | --- |
| `workload` | Workload and capacity: volume, pace, staffing capacity, deadlines, overtime caused by work, or competing task priorities. Includes manageable workload. | Do not add merely because a tool is inconvenient or a schedule is preferred. Require a capacity, prioritisation or time-demand claim. |
| `manager` | Manager support: direct manager/supervisor availability, feedback, listening, coaching, encouragement or practical help. Includes supportive and unsupportive experiences. | Generic company decisions or reporting-line structures are not automatically manager support. Peer support belongs to team. |
| `career` | Career development: learning opportunities, courses, skill development, mentoring for growth, promotion or role progression. | Salary, benefits and general peer cooperation alone do not establish career development. |
| `communication` | Communication: clarity, timeliness, consistency or transparency of information, instructions, announcements and explanations. | Do not add to every answer that says "understand" or "clear". Clear promotion criteria can be career only unless information-sharing quality is also expressed. |
| `tools` | Tools and access: software, devices, equipment, shared digital workspaces, permissions or system access/reliability. | A physical office temperature or parking complaint alone is outside this operational-tool definition. Broaden the catalogue only through a documented guide change. |
| `team` | Team connection: belonging, inclusion, peer support, collaboration, interpersonal working or relationships within/across groups. | The word "team" alone is insufficient when it only identifies who has too much work. Remote working alone is not a connection judgement. |
| `change` | Organisational change: merger/acquisition, integration, restructuring, reorganisation or uncertainty about organisational arrangements. | A new keyboard, changed newsletter format or ordinary process update is not automatically structural organisational change. |

## Worked examples

| Answer | Labels | Why |
| --- | --- | --- |
| My manager is not helpful when I raise a problem. | manager | Negation affects sentiment; the manager topic remains present. |
| The team is welcoming, but the software keeps failing. | tools, team | Two themes with different sentiment; no separate sentiment labelling in this pilot. |
| The workload is manageable this month. | workload | Positive experiences still count as theme mentions. |
| The pay for this role is too low. | all seven 0 | Pay is outside the current catalogue; this may motivate an additional theme later. |
| Nothing to add. | all seven 0 | A reviewed no-theme answer, rather than missing annotation. |

Where a concrete experience supports two themes, assign both. Do not infer an unstated consequence: software failure may cause overload, but tools alone is appropriate until capacity pressure is expressed. Do not require exact catalogue keywords, and do not use the application's rules as the reference labels.

## Independent annotation and disagreements

Your checking of draft labels is assisted human review. Agreement with the AI is not inter-annotator agreement between independent humans. If a second person is available, give them an untouched copy of `blind-review.csv` and the guide before they see draft labels or your decisions. Retain their original file separately, compare per-theme decisions and adjudicate disagreements. Start with a shared subset and record its size and selection.

If no second annotator is available, complete your review and document that limitation. A later repeat pass can help identify inconsistent definitions, but is not independent second-person annotation.

## What happens after your review

Validate the edited CSV, summarise corrections and update the guide where needed. Revisit affected examples after any definition change and record the guide revision. Only completed human-reviewed rows can become reference labels.

There are no train/test assignments yet. SYN-001 and SYN-002 are a deliberate paraphrase family; SYN-015 and SYN-052 share a fictional respondent. Preserve these links in future grouped splits and inspect other semantic similarities. The metadata demonstrates grouping mechanics; it does not represent real people or survey periods.

This visible pilot is development material, not an untouched final evaluation set. A later synthetic held-out set can assess performance within its documented generation setting, but cannot establish real-world accuracy. The pilot's deliberate mix of themes and writing styles also cannot estimate genuine employee theme prevalence.
