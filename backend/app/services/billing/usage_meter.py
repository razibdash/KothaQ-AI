def calculate_billable_seconds(call_duration_seconds: int) -> int:
    return max(call_duration_seconds, 0)
