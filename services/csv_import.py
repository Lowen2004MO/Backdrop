from collections import Counter
from dataclasses import dataclass

from django.db import transaction
from django.utils.crypto import salted_hmac

from apps.pulse.models import ImportedAnswer, ImportedQuestion, ImportedResponse, SurveyImport
from services.question_mapping import normalize_question, suggest_question_mappings


AGREEMENT_VALUES = {
    'strongly disagree',
    'disagree',
    'neither agree nor disagree',
    'neutral',
    'agree',
    'strongly agree',
}
BINARY_VALUES = {'yes', 'no', 'unsure', 'not sure'}
WRITTEN_HINTS = (
    'comment',
    'detail',
    'explain',
    'influenced',
    'suggest',
    'what would',
    'why',
)
NAME_HEADERS = ('what is your name', 'name')
IDENTITY_HEADERS = ('email', *NAME_HEADERS)
COHORT_HEADERS = ('what is your primary area of work', 'primary area of work')
DIMENSION_HINTS = (
    'area of work',
    'work area',
    'acquisition',
    'acquired',
    'buyout',
    'joined through',
    'new to the company',
    'new to iig',
    'legacy organisation',
    'legacy organization',
    'tenure band',
)


@dataclass(frozen=True)
class ImportResult:
    saved_import: SurveyImport
    created: bool
    total: int
    valid: int
    duplicates: int
    repeated: int
    invalid: int
    unmapped: int
    mappings: tuple


def _question_text(header):
    text = header.strip()
    prefix = 'Please rate your agreement with these statements about your work experience:'
    if ':.' in text:
        text = text.rsplit(':.', 1)[-1].strip()
    elif text.casefold().startswith(prefix.casefold()):
        text = text[len(prefix):].lstrip(' .:-')
    return text


def _infer_response_type(mapping, values):
    if mapping.target:
        response_type = mapping.target.response_type
        return 'choice' if response_type == 'multiple_choice' else response_type

    populated = [value.strip() for value in values if value.strip()]
    normalised = {value.casefold() for value in populated}
    if normalised and normalised <= AGREEMENT_VALUES:
        return 'agreement'
    if normalised and normalised <= BINARY_VALUES:
        return 'binary'
    if populated:
        try:
            numeric = [float(value) for value in populated]
            header = normalize_question(mapping.source_header)
            if (
                numeric
                and all(value.is_integer() and 0 <= value <= 10 for value in numeric)
                and ('recommend' in header or 'likely' in header)
            ):
                return 'recommendation'
            return 'numeric'
        except ValueError:
            pass

    header = mapping.source_header.casefold()
    average_words = (
        sum(len(value.split()) for value in populated) / len(populated)
        if populated else 0
    )
    if any(hint in header for hint in WRITTEN_HINTS) or average_words >= 4:
        return 'written'
    return 'choice'


def _find_column(headers, candidates):
    normalised = [normalize_question(header) for header in headers]
    for candidate in candidates:
        if candidate in normalised:
            return normalised.index(candidate)
    return None


def _is_dimension(mapping, response_type):
    header = normalize_question(mapping.source_header)
    if mapping.target and mapping.target.slug == 'primary-area':
        return True
    return (
        response_type in ('binary', 'choice')
        and any(hint in header for hint in DIMENSION_HINTS)
    )


def _cell(row, position):
    if position is None or position >= len(row):
        return ''
    return row[position].strip()


@transaction.atomic
def persist_csv_import(*, cleaned_data, filename, headers, rows, user):
    headers = [header.strip() for header in headers]
    mappings = tuple(suggest_question_mappings(headers))
    width = len(headers)
    padded_rows = [
        tuple((list(row) + [''] * width)[:width])
        for row in rows
    ]
    valid_rows = [row for row in padded_rows if any(value.strip() for value in row)]
    invalid = len(padded_rows) - len(valid_rows)
    duplicates = sum(count - 1 for count in Counter(valid_rows).values() if count > 1)

    name_position = _find_column(headers, NAME_HEADERS)
    identity_position = _find_column(headers, IDENTITY_HEADERS)
    cohort_position = _find_column(headers, COHORT_HEADERS)
    respondent_keys = []
    for number, row in enumerate(valid_rows, start=1):
        identity = _cell(row, identity_position)
        if not identity:
            # Microsoft Forms response IDs restart for each export. Anonymous
            # rows must therefore remain local to one survey period.
            identity = ':'.join((
                'anonymous', cleaned_data['survey_name'],
                cleaned_data['financial_year'], cleaned_data['quarter'],
                str(number),
            ))
        respondent_keys.append(
            salted_hmac('pulse.imported-response', identity.casefold()).hexdigest()
        )
    repeated = sum(
        count - 1 for count in Counter(respondent_keys).values() if count > 1
    )

    mapping_counts = dict(Counter(item.state for item in mappings))
    unmapped = mapping_counts.get('New question', 0)
    saved_import, created = SurveyImport.objects.update_or_create(
        name=cleaned_data['survey_name'],
        financial_year=cleaned_data['financial_year'],
        quarter=cleaned_data['quarter'],
        defaults={
            'source_filename': filename,
            'response_count': len(valid_rows),
            'valid_rows': len(valid_rows),
            'exact_duplicates': duplicates,
            'possible_repeats': repeated,
            'invalid_rows': invalid,
            'unmapped_questions': unmapped,
            'mapping_counts': mapping_counts,
            'status': 'Ready',
            'created_by': user,
        },
    )
    saved_import.questions.all().delete()
    saved_import.responses.all().delete()

    question_positions = [
        position
        for position, mapping in enumerate(mappings)
        if mapping.state != 'Ignored'
    ]
    questions = []
    for position in question_positions:
        mapping = mappings[position]
        values = [_cell(row, position) for row in valid_rows]
        response_type = _infer_response_type(mapping, values)
        questions.append(
            ImportedQuestion(
                survey_import=saved_import,
                source_header=headers[position],
                text=mapping.target.text if mapping.target else _question_text(headers[position]),
                response_type=response_type,
                mapping_state=mapping.state,
                canonical_slug=mapping.target.slug if mapping.target else '',
                position=position,
                is_dimension=_is_dimension(mapping, response_type),
            )
        )
    ImportedQuestion.objects.bulk_create(questions)
    questions_by_position = {question.position: question for question in questions}

    responses = []
    for number, (row, respondent_key) in enumerate(
        zip(valid_rows, respondent_keys), start=1
    ):
        display_name = _cell(row, name_position) or f'Respondent {number}'
        responses.append(
            ImportedResponse(
                survey_import=saved_import,
                respondent_key=respondent_key,
                display_name=display_name,
                cohort=_cell(row, cohort_position),
                row_number=number,
            )
        )
    ImportedResponse.objects.bulk_create(responses)

    answers = []
    for response, row in zip(responses, valid_rows):
        for position, question in questions_by_position.items():
            answers.append(
                ImportedAnswer(
                    response=response,
                    question=question,
                    value=_cell(row, position),
                )
            )
    ImportedAnswer.objects.bulk_create(answers)

    from services.text_analysis import analyse_survey
    analyse_survey(saved_import)

    return ImportResult(
        saved_import=saved_import,
        created=created,
        total=len(padded_rows),
        valid=len(valid_rows),
        duplicates=duplicates,
        repeated=repeated,
        invalid=invalid,
        unmapped=unmapped,
        mappings=mappings,
    )
