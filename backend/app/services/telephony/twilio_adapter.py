def build_say_response(message: str) -> str:
    return f"<?xml version='1.0' encoding='UTF-8'?><Response><Say>{message}</Say></Response>"
