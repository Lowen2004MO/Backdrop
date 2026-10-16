def add_period_changes(rows):
    """Compare category shares with the preceding available period in each group."""
    categories = list(dict.fromkeys(item['category'] for row in rows for item in row['items']))
    previous_by_group = {}
    changes = []
    for row in rows:
        current = {item['category']: item for item in row['items']}
        row['items'] = [current.get(category, {'category': category, 'count': 0, 'percentage': 0}) for category in categories]
        group = row.get('group', row.get('label', ''))
        previous = previous_by_group.get(group)
        if previous:
            earlier = {item['category']: item for item in previous['items']}
            changes.append({
                'survey': row['survey'], 'previous_survey': previous['survey'], 'group': group,
                'items': [{
                    'category': item['category'], 'percentage': item['percentage'],
                    'previous_percentage': earlier[item['category']]['percentage'],
                    'change': item['percentage'] - earlier[item['category']]['percentage'],
                } for item in row['items']],
            })
        previous_by_group[group] = row
    return changes
