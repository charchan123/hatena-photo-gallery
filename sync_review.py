"""Read-only stable review identifiers. Never grants publication permission."""
from collections import Counter
from article_sync import digest, observation_groups, payload_hash


def identity(article_hash, url_hash, ordinal):
    return 'sync-' + payload_hash([article_hash, url_hash, ordinal])


def occurrence_rows(portal):
    counts = Counter()
    result = {}
    observation_groups(portal)
    for row in portal['observations']:
        key = (digest(row['article']['article_id']), digest(row['src']))
        ordinal = counts[key]; counts[key] += 1
        result[(*key, ordinal)] = row
    return result


def photo_fingerprint(article, image, observation):
    # Ignore transient article_N and production order; include all classification
    # evidence and the entire article inventory (including updated timestamp hash).
    return payload_hash({'article': article, 'image': image,
                         'classification': observation.get('classification') if observation else None,
                         'name': observation.get('gallery_name') if observation else None})
