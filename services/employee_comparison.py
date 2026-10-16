from services.question_mapping import normalize_question
from services.response_comparison import answer_change


def employee_comparison(context, load_period, *, periods=(), most_recent=False, all_periods=False, explicit=False):
    """Build question rows in chronological order using only the chosen periods."""
    imported = context['is_imported']
    def period_key(survey):
        return str(survey.pk) if imported else survey.slug

    available = list({period_key(survey): survey for survey in context['surveys']}.values())
    if most_recent:
        chosen = available[-1:]
    elif all_periods:
        chosen = available
    elif periods or explicit:
        chosen = [survey for survey in available if period_key(survey) in periods]
    else:
        current_index = next(index for index, survey in enumerate(available) if survey == context['selected_survey'])
        chosen = available[max(0, current_index - 1):current_index + 1]

    results = [load_period(period_key(survey)) for survey in chosen]
    grouped = {'answers': {}, 'written_answers': {}}
    for index, result in enumerate(results):
        for section in grouped:
            for item in result[section]:
                question = item['question']
                identifier = (question.canonical_slug or normalize_question(question.text)) if imported else question.slug
                key = (identifier, question.response_type)
                row = grouped[section].setdefault(key, {'question': question, 'by_period': {}})
                row['question'] = question
                row['by_period'][index] = item

    for section in grouped:
        for row in grouped[section].values():
            cells = []
            previous = None
            for index, survey in enumerate(chosen):
                item = row['by_period'].get(index)
                if item is None:
                    cell = {'survey': survey, 'answer': 'Not asked in this period', 'change_summary': 'No comparable answer', 'annotations': []}
                else:
                    raw = item['raw_value']
                    if index == 0:
                        change = 'First selected period'
                    elif previous is None:
                        change = 'No comparable earlier answer'
                    else:
                        change = answer_change(raw, previous['raw_value'], row['question'].response_type, concise=True)
                    cell = {'survey': survey, 'answer': item['answer'], 'change_summary': change, 'annotations': item.get('annotations', [])}
                cells.append(cell)
                previous = item
            row['cells'] = cells
            del row['by_period']

    context.update({
        'comparison_periods': chosen,
        'comparison_answers': list(grouped['answers'].values()),
        'comparison_written_answers': list(grouped['written_answers'].values()),
        'all_surveys': [{'slug': period_key(survey), 'label': survey.label} for survey in available],
        'selected': [period_key(survey) for survey in chosen],
        'most_recent_checked': most_recent,
        'all_periods_checked': all_periods and not most_recent,
    })
    return context
