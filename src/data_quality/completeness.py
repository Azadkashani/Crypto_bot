class CompletenessChecker:
    @staticmethod
    def check(event: dict) -> bool:
        if 'value' in event and event['value'] is not None:
            if event['value'] < 0:
                return False
        return True
