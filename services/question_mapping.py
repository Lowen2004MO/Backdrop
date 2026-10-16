import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from .synthetic_repository import Question, repository

IGNORED_HEADERS = {
    'id','start time','completion time','email','name','what is your name',
}

@dataclass(frozen=True)
class MappingSuggestion:
    source_header: str
    state: str
    target: Question | None
    confidence: int
    reason: str

def normalize_question(value: str) -> str:
    value = value.strip().casefold()
    if ':.' in value:
        value = value.rsplit(':.', 1)[-1]
    value = re.sub(r'[^a-z0-9]+', ' ', value)
    value = ' '.join(value.split())
    matrix_prefix = (
        'please rate your agreement with these statements about your work experience '
    )
    if value.startswith(matrix_prefix):
        value = value.removeprefix(matrix_prefix)
    return value

def suggest_question_mappings(headers, declared_types=None):
    declared_types = declared_types or {}
    candidates = []
    for question in repository.questions():
        for label in (question.text, *question.aliases):
            candidates.append((normalize_question(label), question))
    suggestions = []
    for header in headers:
        normalized = normalize_question(header)
        if normalized in IGNORED_HEADERS:
            suggestions.append(MappingSuggestion(header,'Ignored',None,100,'Identity or collection metadata'))
            continue
        exact = next((question for label,question in candidates if label == normalized),None)
        if exact:
            supplied_type = declared_types.get(header)
            if supplied_type and supplied_type != exact.response_type:
                suggestions.append(MappingSuggestion(header,'Not comparable',exact,100,'Question matches but response type changed'))
            else:
                suggestions.append(MappingSuggestion(header,'Confirmed',exact,100,'Normalised wording match'))
            continue
        scores = [(SequenceMatcher(None,normalized,label).ratio(),question) for label,question in candidates]
        score, question = max(scores,key=lambda item:item[0])
        if score >= .82:
            suggestions.append(MappingSuggestion(header,'Needs review',question,round(score*100),'Similar wording; human confirmation required'))
        else:
            suggestions.append(MappingSuggestion(header,'New question',None,round(score*100),'No sufficiently similar canonical question'))
    return suggestions
