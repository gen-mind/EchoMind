# Voice Service

> **Service:** `echomind-voice`
> **Protocol:** NATS (subscriber)
> **Port:** 8080 (health check only)

---

## What It Does

The Voice Service **transcribes audio files** using OpenAI Whisper:

- Receives audio files from Semantic service
- Transcribes speech to text
- Detects language (if not specified)
- Returns transcript for further processing
- Supports multiple audio formats (MP3, WAV, M4A, etc.)

---

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph VoiceService["echomind-voice"]
        NATS_SUB[NATS Subscriber]
        WHISPER[Whisper Model]
        CACHE[Model Cache]
        DOWNLOADER[MinIO Downloader]
    end

    subgraph External
        NATS[(NATS)]
        MINIO[(MinIO)]
        DB[(PostgreSQL)]
    end

    NATS -->|audio.transcribe| NATS_SUB
    NATS_SUB --> DOWNLOADER
    DOWNLOADER --> MINIO
    DOWNLOADER --> WHISPER
    WHISPER --> CACHE
    WHISPER --> DB
```

### Transcription Flow

```mermaid
sequenceDiagram
    participant S as Semantic
    participant N as NATS
    participant V as Voice
    participant M as MinIO
    participant W as Whisper
    participant DB as PostgreSQL

    S->>N: audio.transcribe
    N->>V: AudioTranscribeRequest

    V->>M: Download audio file
    M-->>V: Audio bytes

    V->>W: Transcribe
    W-->>V: Transcript + metadata

    V->>DB: Update document (content = transcript)

    Note over V,S: Option A: Direct DB update
    Note over V,S: Option B: Publish response to NATS
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| NATS Client | nats-py (async) |
| Transcription | openai-whisper |
| Audio Processing | ffmpeg, pydub |
| MinIO Client | minio-py |
| GPU Support | CUDA |

---

## Database Tables Used

| Table | Operations | Reference |
|-------|------------|-----------|
| `documents` | Update (add transcript) | [DB Schema](../db-schema.md#documents) |

---

## Proto Definitions Used

| Proto | Direction | Description |
|-------|-----------|-------------|
| `AudioTranscribeRequest` | Subscribe | Incoming from semantic |
| `AudioTranscribeResponse` | (internal) | Transcript result |

See [Proto Definitions](../proto-definitions.md#audiotranscriberequest)

---

## NATS Messaging

### Subscriptions (Incoming)

| Subject | Payload | From |
|---------|---------|------|
| `audio.transcribe` | `AudioTranscribeRequest` | Semantic |

### Publications (Outgoing)

Currently, the Voice service writes directly to the database rather than publishing a response. Future versions may add:

| Subject | Payload | To |
|---------|---------|-----|
| `audio.transcribe.response` | `AudioTranscribeResponse` | Semantic |

### Consumer Configuration

```python
subscriber = JetStreamEventSubscriber(
    nats_url="nats://nats:4222",
    stream_name="ECHOMIND",
    subjects=["audio.transcribe"],
    durable_name="voice-consumer",
    queue_group="voice-workers"
)
```

---

## Whisper Configuration

### Model Sizes

| Model | Size | VRAM | Quality | Speed |
|-------|------|------|---------|-------|
| `tiny` | 39M | ~1GB | Low | Fastest |
| `base` | 74M | ~1GB | OK | Fast |
| `small` | 244M | ~2GB | Good | Medium |
| `medium` | 769M | ~5GB | Better | Slow |
| `large-v3` | 1.5B | ~10GB | Best | Slowest |

### Transcription Code

```python
import whisper

class WhisperTranscriber:
    """Whisper-based audio transcription."""

    def __init__(self, model_name: str = "base"):
        self.model = whisper.load_model(model_name)

    async def transcribe(
        self,
        audio_path: str,
        language: str | None = None
    ) -> TranscriptResult:
        result = self.model.transcribe(
            audio_path,
            language=language,  # None = auto-detect
            task="transcribe",
            verbose=False
        )

        return TranscriptResult(
            text=result["text"],
            language=result["language"],
            duration=result.get("duration", 0),
            segments=result.get("segments", [])
        )
```

---

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| MP3 | `.mp3` | Most common |
| WAV | `.wav` | Uncompressed |
| M4A | `.m4a` | Apple format |
| FLAC | `.flac` | Lossless |
| OGG | `.ogg` | Open format |
| WebM | `.webm` | Web audio |

**Requires:** ffmpeg installed for format conversion.

---

## Service Structure

```
src/services/voice/
├── main.py                 # Entry point
├── nats/
│   └── subscriber.py
├── logic/
│   ├── voice_service.py
│   ├── transcriber.py      # Whisper wrapper
│   ├── downloader.py       # MinIO download
│   └── exceptions.py
├── middleware/
│   └── error_handler.py
└── config.py
```

---

## Configuration

```bash
# NATS
NATS_URL=nats://nats:4222
NATS_STREAM_NAME=ECHOMIND

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=documents

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/echomind

# Whisper
WHISPER_MODEL=base           # tiny, base, small, medium, large-v3
WHISPER_DEVICE=cuda          # cuda, cpu

# Processing
VOICE_TEMP_DIR=/tmp/voice    # Temp storage for audio files
VOICE_MAX_DURATION=3600      # Max audio duration (seconds)
```

---

## GPU Support

Whisper benefits significantly from GPU acceleration:

| Device | Speed (1h audio) |
|--------|------------------|
| CPU | ~10-30 min |
| CUDA GPU | ~1-5 min |

```python
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
model = whisper.load_model("base", device=device)
```

---

## Error Handling

| Error | Handling |
|-------|----------|
| File not found | NAK message, retry |
| Unsupported format | Mark document as failed |
| Transcription error | NAK message, retry up to 3x |
| GPU OOM | Fallback to CPU |

---

## Health Check

```bash
GET :8080/healthz

# Response
{
  "status": "healthy",
  "nats": "connected",
  "minio": "connected",
  "whisper_model": "base",
  "device": "cuda"
}
```

---

## Future: Real-Time Voice

Current scope: **batch processing** of audio files.

Future enhancement: real-time voice streaming
- WebSocket audio input
- Streaming transcription
- Speaker diarization
- Voice synthesis responses

---

## Unit Testing (MANDATORY)

All service logic MUST have unit tests. See [Testing Standards](../../.claude/rules/testing.md).

### Test Location

```
tests/unit/voice/
├── test_voice_service.py
├── test_whisper_transcriber.py
└── test_downloader.py
```

### What to Test

| Component | Test Coverage |
|-----------|---------------|
| VoiceService | Event handling, error handling |
| WhisperTranscriber | Transcription result parsing |
| Downloader | MinIO download logic |

### Example

```python
# tests/unit/voice/test_whisper_transcriber.py
class TestWhisperTranscriber:
    @pytest.fixture
    def mock_model(self):
        model = MagicMock()
        model.transcribe.return_value = {
            "text": "Hello world",
            "language": "en",
            "duration": 2.5,
            "segments": []
        }
        return model

    @pytest.mark.asyncio
    async def test_transcribe_returns_text(self, mock_model):
        with patch("whisper.load_model", return_value=mock_model):
            transcriber = WhisperTranscriber(model_name="base")
            result = await transcriber.transcribe("/path/to/audio.mp3")

        assert result.text == "Hello world"
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_transcribe_with_language_hint(self, mock_model):
        with patch("whisper.load_model", return_value=mock_model):
            transcriber = WhisperTranscriber(model_name="base")
            await transcriber.transcribe("/path/to/audio.mp3", language="es")

        mock_model.transcribe.assert_called_with(
            "/path/to/audio.mp3",
            language="es",
            task="transcribe",
            verbose=False
        )
```

### Minimum Coverage

- **70%** for service classes
- **80%** for transcription logic

---

## References

- [NATS Messaging](../nats-messaging.md) - Message flow documentation
- [Proto Definitions](../proto-definitions.md) - Message schemas
- [Semantic Service](./semantic-service.md) - Sends audio.transcribe
- [OpenAI Whisper](https://github.com/openai/whisper) - Transcription model
