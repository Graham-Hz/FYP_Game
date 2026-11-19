"""Shared presentation taxonomy for heterogeneous Steam source labels.

This is an explicit project mapping, not a claim that Steam publishes this exact
taxonomy. Preserve all source labels, keep unknown labels in a separate bucket,
and never change eligibility, stored CSVs, model features or research partitions.
"""
VERSION = 'market_label_taxonomy_v1'
GAMEPLAY_GENRES = frozenset({
    'Action', 'Adventure', 'Casual', 'RPG', 'Racing', 'Simulation', 'Sports', 'Strategy',
})
TAG_BUCKETS = (
    ('production', '製作／發行標籤', frozenset({'Indie'})),
    ('release', '發行階段', frozenset({'Early Access'})),
    ('pricing', '收費模式標籤', frozenset({'Free To Play'})),
    ('feature', '遊玩形式', frozenset({'Massively Multiplayer'})),
    ('content', '內容描述', frozenset({'Sexual Content', 'Nudity', 'Violent', 'Gore'})),
    ('software_media', '軟件／媒體用途', frozenset({
        'Accounting', 'Animation & Modeling', 'Audio Production', 'Design & Illustration',
        'Education', 'Game Development', 'Photo Editing', 'Software Training', 'Utilities',
        'Video Production', 'Web Publishing', '360 Video', 'Documentary', 'Episodic',
        'Movie', 'Short', 'Tutorial',
    })),
)


def gameplay(labels):
    return sorted(set(labels) & GAMEPLAY_GENRES)


def other_labels(labels):
    return sorted(set(labels) - GAMEPLAY_GENRES)


def tag_groups(labels):
    remaining = set(labels) - GAMEPLAY_GENRES
    groups = []
    for ident, label, members in TAG_BUCKETS:
        values = sorted(remaining & members)
        if values:
            groups.append({'id': ident, 'label': label, 'values': values})
            remaining.difference_update(values)
    if remaining:
        groups.append({'id': 'other', 'label': '其他來源標籤（未分類）', 'values': sorted(remaining)})
    return groups


def metadata():
    return {
        'version': VERSION,
        'gameplay_genres': sorted(GAMEPLAY_GENRES),
        'basis': 'Explicit project presentation mapping of existing source labels; not a new verified Steam taxonomy.',
        'policy': 'Keep source labels unchanged; show gameplay genres separately from production, release, pricing, play form, content and software/media labels. Unknown labels remain separately selectable.',
        'mobile_policy': 'Retain the existing Google Play game categories; do not merge them into a Steam taxonomy.',
    }
