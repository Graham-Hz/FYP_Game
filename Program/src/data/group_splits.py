"""Deterministic, outcome-blind developer groups and partitions."""
import hashlib
import unicodedata


def normalize_developer(value):
    return " ".join(unicodedata.normalize("NFKC", str(value)).split()).casefold()


def developer_tokens(values, placeholders):
    return sorted({normalize_developer(x) for x in values} - set(placeholders))


def pc_components(records, placeholders):
    """Use all source games, so an excluded co-developed game still bridges studios."""
    parent = {}
    def find(node):
        parent.setdefault(node, node)
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != node:
            previous = parent[node]
            parent[node] = root
            node = previous
        return root
    tokens_by_id = {}
    for app_id, values in records:
        tokens = developer_tokens(values, placeholders)
        tokens_by_id[app_id] = tokens
        for token in tokens:
            find(token)
        for token in tokens[1:]:
            a, b = find(tokens[0]), find(token)
            if a != b:
                parent[max(a, b)] = min(a, b)
    return {app_id: ("pc_" + hashlib.sha256(find(tokens[0]).encode("utf-8")).hexdigest() if tokens else None)
            for app_id, tokens in tokens_by_id.items()}, tokens_by_id


def mobile_group(value, placeholders):
    normalized = normalize_developer(value)
    return None if normalized in placeholders else "mobile_" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def partition(group, platform, config):
    if group is None:
        return None, None
    def number(purpose):
        key = f"{config['seed']}|{purpose}|{platform}|{group}"
        return int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:16], 16)
    ratio = number("holdout") / 2**64
    if ratio < config["train_threshold"]:
        return "train", number("cv") % config["train_cv_folds"]
    return ("calibration", None) if ratio < config["calibration_threshold"] else ("test", None)
