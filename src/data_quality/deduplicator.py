class Deduplicator:
    def __init__(self):
        self.seen_ids = set()

    def is_duplicate(self, event: dict) -> bool:
        event_id = f"{event.get('chain')}:{event.get('transaction_hash')}:{event.get('log_index', 0)}"
        if event_id in self.seen_ids:
            return True
        self.seen_ids.add(event_id)
        return False

    def reset(self):
        self.seen_ids.clear()
