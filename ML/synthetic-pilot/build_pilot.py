"""Build a fully synthetic, unreviewed annotation pilot using only the stdlib.

Examples and draft labels were authored for this pilot, not inferred by the
application rules. This script never changes an existing review file.
"""

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


THEMES = {
    "workload": "Workload and capacity",
    "manager": "Manager support",
    "career": "Career development",
    "communication": "Communication",
    "tools": "Tools and access",
    "team": "Team connection",
    "change": "Organisational change",
}

# text | proposed labels (comma-separated, or none) | annotation rationale
EXAMPLES = """I cannot finish everything assigned to me within my contracted hours.|workload|Volume exceeds available working time.
There is more assigned work than I can get through in my normal working day.|workload|Deliberate paraphrase of the preceding answer; keep the family together.
The number of tasks is manageable this month.|workload|Positive capacity experience still mentions the theme.
We have three vacant posts and the same amount of work to deliver.|workload|Staffing is discussed as a capacity constraint.
Every request is marked urgent, so I do not know which task to do first.|workload|Competing task priorities; no explicit failure of organisational information sharing.
I am not overloaded at the moment.|workload|Negation changes polarity, not theme presence.
Too much to do. Too little time.|workload|Short but self-contained capacity statement.
My supervisor makes time to help when I get stuck.|manager|Practical support from a supervisor.
I have asked my line manager for feedback twice and have not received any.|manager|Feedback from the line manager is the central issue.
Our weekly check-ins with my supervisor are useful.|manager|Positive manager interaction.
My manager is not helpful when I raise a problem.|manager|Negative manager support; helpful alone must not imply positive sentiment.
I can always get hold of the person I report to.|manager|Manager availability without the catalogue keyword.
My manager listens but rarely follows through on the help they promise.|manager|Mixed experience of manager support.
I do not need extra help from my supervisor right now.|manager|Explicit lack of need still discusses manager support.
I cannot see a route to promotion in my current role.|career|Progression opportunity.
The course I completed helped me build new skills.|career|Positive learning experience.
I would like a structured development plan for the next year.|career|Request for a development plan.
There are no opportunities to learn anything new in this role.|career|Negative learning opportunity.
I now understand what I need to demonstrate to move to the next grade.|career|Progression criteria; do not add communication for every understood statement.
I have not applied for a promotion because I like my current role.|career|Career discussion without dissatisfaction.
More chances to practise a different role would help me grow.|career|Experiential development, without a formal training keyword.
Important decisions are announced after they have already taken effect.|communication|Late decision communication.
The weekly company update explains decisions in plain language.|communication|Positive organisation-wide information sharing.
Different departments send conflicting instructions about the same process.|communication|Inconsistent information across departments.
I usually hear about decisions through rumours rather than official updates.|communication|Information channel and transparency.
The new format of the newsletter is easier to understand.|communication|A format change alone is not organisational restructuring.
Nobody explained why the travel approval process was introduced.|communication|Missing explanation; ordinary process introduction is not automatically organisational change.
The last announcement was not unclear; it answered my questions.|communication|Negation within a communication judgement.
I still cannot open the shared drive even though access was requested last week.|tools|Access permissions.
My laptop works reliably and has everything I need.|tools|Positive equipment experience.
The reporting application crashes whenever I export a large file.|tools|Software reliability.
I have to sign in to four separate systems to complete one request.|tools|System friction without an explicit workload/capacity claim.
My permissions were fixed yesterday and I can now use the dashboard.|tools|Resolved access issue still expresses the theme.
The new keyboard is comfortable to use.|tools|Equipment experience; new equipment is not organisational change.
The sofware freezes several times a day.|tools|Deliberate misspelling in a self-contained software complaint.
People in my team make me feel welcome.|team|Belonging.
I rarely speak to anyone outside my own group and feel isolated.|team|Isolation and cross-group connection.
Colleagues willingly share their knowledge with each other.|team|Peer collaboration; no explicit formal career-development claim.
Working from home has not stopped me feeling part of the group.|team|Remote belonging; do not label by remote keyword alone.
The handover between our two teams works well.|team|Cross-team collaboration.
I do not feel excluded by my colleagues.|team|Negated exclusion remains a belonging statement.
When we disagree, we work through it together rather than blaming each other.|team|Collaborative behaviour without the word team.
The merger has made me uncertain about where my role will sit.|change|Merger-related organisational uncertainty.
I feel positive about becoming part of the acquired business.|change|Positive acquisition discussion.
The restructure has left our reporting lines unsettled.|change|Structural reporting-line change, not an explicit manager-support judgement.
Bringing the two organisations together has gone more smoothly than I expected.|change|Positive integration experience.
I am not worried about the reorganisation.|change|Negation changes sentiment, not organisational topic.
Our department is being split into two separate units.|change|Organisational restructuring without a catalogue keyword.
I would prefer the old organisational structure to the current one.|change|Comparison of structural arrangements.
My manager helps me decide what to defer when there is too much work.|workload,manager|Capacity prioritisation plus practical manager support.
My supervisor encouraged me to apply for the development programme.|manager,career|Manager encouragement plus development opportunity.
The extra work after the merger is more than our current staffing can handle.|workload,change|Capacity pressure explicitly attributed by the speaker to a merger.
I am waiting for access to the learning portal so I can complete my course.|career,tools|System access plus a concrete learning activity.
The team is welcoming, but the software keeps failing.|tools,team|Two themes with different polarity.
Since the restructure, nobody has explained who makes decisions.|communication,change|Organisational change plus missing decision information.
Our manager explains decisions openly but is unavailable when I need help.|manager,communication|Decision transparency plus manager availability.
Colleagues cover for each other, although there are not enough of us for the workload.|workload,team|Peer cooperation plus staffing capacity.
The merger created opportunities to move into a more senior role.|career,change|Progression associated with integration.
The shared workspace makes it easy to collaborate with colleagues in other teams.|tools,team|A concrete shared tool supports cross-team collaboration.
Conflicting instructions mean I keep redoing tasks and cannot finish on time.|workload,communication|Inconsistent instructions plus explicit time/capacity consequences.
My manager arranged a replacement laptop after mine stopped working.|manager,tools|Practical manager help plus equipment problem.
I would like more peer mentoring so we can learn new skills together.|career,team|Skill development through peer relationships.
The integration announcement was clear, and the new structure makes sense to me.|communication,change|Communication about organisational integration.
My manager cancels our development meetings because the department is understaffed.|workload,manager,career|Staffing pressure plus manager meetings about development.
We hear little about the merger, and people in the group have stopped working together.|communication,team,change|Missing integration information plus collaboration decline.
The system is faster now, so we can handle the incoming requests without overtime.|workload,tools|Software improvement plus explicit capacity improvement.
I would value a course on the reporting software because I cannot use its advanced features.|career,tools|Training request concerning a concrete software tool.
My supervisor brought our remote group together and helped everyone feel included.|manager,team|Manager action and team belonging.
Following the restructure, my manager explained the new reporting lines and helped me settle in.|manager,communication,change|Structural change, its explanation and personal manager support.
The workload is manageable, my colleagues are supportive, and the merger has not worried me.|workload,team,change|Three explicit themes, none necessarily negative.
The pay offered for this role is below what similar jobs pay elsewhere.|none|Pay is outside the current seven themes unless linked to progression or another defined theme.
The car park fills up before I arrive.|none|Parking provision alone is outside the catalogue.
There are too few vegetarian choices in the canteen.|none|Catering preference is outside the catalogue.
I would like the annual leave allowance to be increased.|none|Leave entitlement alone is outside the catalogue.
The office is too cold in the afternoon.|none|Physical temperature alone is outside the catalogue.
My commute is expensive.|none|Commuting cost alone is outside the catalogue.
The pension contribution could be higher.|none|Benefit level alone is outside the catalogue.
I prefer to start work at eight rather than nine.|none|Personal schedule preference without a capacity or collaboration claim.
Nothing to add.|none|Self-contained non-substantive answer, not an unreviewed row.
I am satisfied overall, but I do not have a specific example to share.|none|General satisfaction does not establish a particular theme.
"""


def main():
    destination = Path(__file__).resolve().parent
    outputs = [destination / name for name in (
        "review.csv", "blind-review.csv", "data-preview.md", "manifest.json"
    )]
    if any(path.exists() for path in outputs):
        raise SystemExit("Refusing to overwrite pilot files or reviewer edits.")

    rows = []
    rationale = {}
    counts = Counter()
    for number, line in enumerate(EXAMPLES.strip().splitlines(), start=1):
        text, labels, reason = line.split("|")
        selected = [] if labels == "none" else labels.split(",")
        assert set(selected) <= THEMES.keys()
        assert len(set(selected)) == len(selected)
        example_id = f"SYN-{number:03d}"
        family = "family-001" if number == 2 else f"family-{number:03d}"
        # Rows 15 and 52 are deliberately linked as a fictional repeat respondent.
        respondent = "person-015" if number == 52 else f"person-{number:03d}"
        # Components combine the paraphrase and respondent links.
        group = "group-001" if number == 2 else (
            "group-015" if number == 52 else f"group-{number:03d}"
        )
        row = {
            "example_id": example_id,
            "snapshot_version": "synthetic-pilot-v1",
            "source_type": "synthetic_ai_authored",
            "text": text,
            "respondent_group_id": respondent,
            "template_family_id": family,
            "leakage_group_id": group,
            **{label: int(label in selected) for label in THEMES},
            "label_source": "ai_draft_not_human_reference",
            "review_complete": 0,
            "reviewer": "",
            "annotation_notes": "",
        }
        rows.append(row)
        rationale[example_id] = reason
        counts.update(selected)

    assert len(rows) == 80
    assert len({row["example_id"] for row in rows}) == len(rows)
    assert len({row["text"] for row in rows}) == len(rows)
    fields = list(rows[0])
    for path, blind in ((outputs[0], False), (outputs[1], True)):
        # UTF-8 BOM makes the CSV easier to open in Windows spreadsheet tools.
        with path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                item = dict(row)
                if blind:
                    item.update({theme: "" for theme in THEMES})
                    item["label_source"] = "unlabelled"
                writer.writerow(item)

    preview = [
        "# Synthetic pilot: all 80 answers and draft labels",
        "",
        "**All text, people and grouping metadata are fictional. No human review is complete.**",
        "",
        "Use `review.csv` to correct the labels. The labels and reasons below are AI-authored suggestions, not ground truth. For independent annotation, use `blind-review.csv` without consulting this page first. See [the review guide](review-guide.md).",
        "",
        "## Draft coverage",
        "",
        "| Theme | Draft positives | Draft negatives |",
        "| --- | ---: | ---: |",
    ]
    for key, name in THEMES.items():
        preview.append(f"| {name} | {counts[key]} | {len(rows) - counts[key]} |")
    no_theme = sum(not any(row[key] for key in THEMES) for row in rows)
    multi = sum(sum(row[key] for key in THEMES) > 1 for row in rows)
    preview += [
        "",
        f"{len(rows)} answers: {len(rows) - no_theme - multi} single-theme, {multi} multi-theme, {no_theme} no-theme. These are designed counts, not survey prevalence estimates.",
        "",
        "## Examples for review",
        "",
        "| ID | Synthetic answer | Proposed themes | Draft reasoning |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        names = ", ".join(THEMES[key] for key in THEMES if row[key]) or "None of the seven"
        preview.append(
            f'| {row["example_id"]} | {row["text"]} | {names} | {rationale[row["example_id"]]} |'
        )
    outputs[2].write_text("\n".join(preview) + "\n", encoding="utf-8")
    manifest = {
        "dataset_version": "synthetic-pilot-v1",
        "prepared": "2026-10-16",
        "source": "Entirely AI-authored fictional examples and draft labels; no employee data or application-rule labelling.",
        "purpose": "Annotation pilot and pipeline development; not real-world accuracy evidence.",
        "theme_order": list(THEMES),
        "answer_count": len(rows),
        "draft_positive_counts": dict(counts),
        "single_theme_count": len(rows) - no_theme - multi,
        "multi_theme_count": multi,
        "no_theme_count": no_theme,
        "human_reviewed_count": 0,
        "leakage_group_count": len({row["leakage_group_id"] for row in rows}),
        "known_links": [
            "SYN-001 and SYN-002 are deliberate paraphrases.",
            "SYN-015 and SYN-052 share a fictional respondent.",
        ],
        "split_status": "No train/validation/test splits assigned; review first.",
        "generation": "Curated examples embedded in build_pilot.py; no random template expansion or API calls.",
        "limitations": [
            "Artificial theme balance, style and overlap do not represent employee feedback.",
            "Human checking of AI labels is assisted review, not independent inter-annotator agreement.",
            "Unrecorded semantic similarities may remain; review family grouping before future splitting.",
            "This visible pilot must not later be described as an untouched final test set.",
        ],
        "initial_file_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in outputs[:3]
        },
    }
    outputs[3].write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "answers": len(rows), "draft_positive_counts": dict(counts),
        "single_theme": len(rows) - no_theme - multi,
        "multi_theme": multi, "no_theme": no_theme,
        "human_reviewed": 0, "files_created": [path.name for path in outputs],
    }, indent=2))


if __name__ == "__main__":
    main()
