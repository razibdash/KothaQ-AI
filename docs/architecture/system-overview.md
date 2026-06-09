# System Overview

```txt
Caller
  ↓
Telephony Provider / SIP / Twilio
  ↓
Voice Webhook API
  ↓
Voice Orchestrator
  ↓
Language Router → Knowledge Search → Answer Policy → TTS/Telephony Response
  ↓
Call Logs, Leads, Unknown Questions, Analytics
```
