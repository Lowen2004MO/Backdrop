import math


AGREEMENT_SCORES = {
    'strongly disagree': 1,
    'disagree': 2,
    'neither agree nor disagree': 3,
    'neutral': 3,
    'agree': 4,
    'strongly agree': 5,
}


def answer_change(current, previous, response_type, *, concise=False):
    current, previous = current.strip(), previous.strip()
    if not previous:
        return 'No previous answer'
    if not current:
        if concise:
            return 'No response this period'
        return f'{previous} → No response'
    if current.casefold() == previous.casefold():
        return 'No change'
    transition = f'{previous} → {current}'
    if response_type == 'agreement':
        current_score = AGREEMENT_SCORES.get(current.casefold())
        previous_score = AGREEMENT_SCORES.get(previous.casefold())
        if current_score is not None and previous_score is not None:
            movement = current_score - previous_score
            unit = 'scale point' if abs(movement) == 1 else 'scale points'
            if concise:
                return f'{movement:+d} {unit}'
            return f'{transition} ({movement:+d} {unit})'
    if response_type in ('numeric', 'recommendation'):
        try:
            movement = float(current) - float(previous)
            if math.isfinite(movement):
                unit = (' recommendation point' + ('' if abs(movement) == 1 else 's')) if response_type == 'recommendation' else ''
                if concise:
                    return f'{movement:+g}{unit}'
                return f'{transition} ({movement:+g}{unit})'
        except ValueError:
            pass
    return 'Changed' if concise else transition
