# Vision Service

> **Service:** `echomind-vision`
> **Protocol:** NATS (subscriber)
> **Port:** 8080 (health check only)

---

## What It Does

The Vision Service **analyzes images and video frames** using BLIP and OCR:

- Receives image/video files from Semantic service
- Generates image captions using BLIP
- Extracts text from images using OCR (Tesseract/EasyOCR)
- Combines caption + OCR text for semantic indexing
- Returns description for further processing
- Supports multiple image formats (JPEG, PNG, WebP, etc.)

---

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph VisionService["echomind-vision"]
        NATS_SUB[NATS Subscriber]
        ROUTER[Content Router]
        BLIP[BLIP Captioner]
        OCR[OCR Engine]
        DOWNLOADER[MinIO Downloader]
    end

    subgraph External
        NATS[(NATS)]
        MINIO[(MinIO)]
        DB[(PostgreSQL)]
    end

    NATS -->|image.analyze| NATS_SUB
    NATS_SUB --> DOWNLOADER
    DOWNLOADER --> MINIO
    DOWNLOADER --> ROUTER
    ROUTER --> BLIP
    ROUTER --> OCR
    BLIP --> DB
    OCR --> DB
```

### Processing Flow

```mermaid
sequenceDiagram
    participant S as Semantic
    participant N as NATS
    participant V as Vision
    participant M as MinIO
    participant B as BLIP
    participant O as OCR
    participant DB as PostgreSQL

    S->>N: image.analyze
    N->>V: ImageAnalyzeRequest

    V->>M: Download image/video
    M-->>V: File bytes

    alt Image file
        V->>B: Generate caption
        B-->>V: Caption text
        V->>O: Extract text (OCR)
        O-->>V: OCR text
        V->>V: Combine caption + OCR
    else Video file
        V->>V: Extract keyframes
        loop Each keyframe
            V->>B: Generate caption
            V->>O: Extract text
        end
        V->>V: Combine all descriptions
    end

    V->>DB: Update document (content = description)

    Note over V,S: Option A: Direct DB update
    Note over V,S: Option B: Publish response to NATS
```

---

## Technology Stack

| Component | Technology |
|-----------|------------|
| NATS Client | nats-py (async) |
| Image Captioning | BLIP (Salesforce) |
| OCR | Tesseract / EasyOCR |
| Video Processing | OpenCV, ffmpeg |
| MinIO Client | minio-py |
| GPU Support | CUDA |

---

## Database Tables Used

| Table | Operations | Reference |
|-------|------------|-----------|
| `documents` | Update (add description) | [DB Schema](../db-schema.md#documents) |

---

## Proto Definitions Used

| Proto | Direction | Description |
|-------|-----------|-------------|
| `ImageAnalyzeRequest` | Subscribe | Incoming from semantic |
| `ImageAnalyzeResponse` | (internal) | Description result |

See [Proto Definitions](../proto-definitions.md#imageanalyzerequest)

---

## NATS Messaging

### Subscriptions (Incoming)

| Subject | Payload | From |
|---------|---------|------|
| `image.analyze` | `ImageAnalyzeRequest` | Semantic |

### Publications (Outgoing)

Currently, the Vision service writes directly to the database rather than publishing a response. Future versions may add:

| Subject | Payload | To |
|---------|---------|-----|
| `image.analyze.response` | `ImageAnalyzeResponse` | Semantic |

### Consumer Configuration

```python
subscriber = JetStreamEventSubscriber(
    nats_url="nats://nats:4222",
    stream_name="ECHOMIND",
    subjects=["image.analyze"],
    durable_name="vision-consumer",
    queue_group="vision-workers"
)
```

---

## BLIP Configuration

### Model Variants

| Model | Size | VRAM | Quality | Speed |
|-------|------|------|---------|-------|
| `blip-base` | 385M | ~2GB | Good | Fast |
| `blip-large` | 930M | ~4GB | Better | Medium |
| `blip2-opt-2.7b` | 2.7B | ~8GB | Best | Slow |

### Captioning Code

```python
from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image

class BLIPCaptioner:
    """BLIP-based image captioning."""

    def __init__(self, model_name: str = "Salesforce/blip-image-captioning-base"):
        self.processor = BlipProcessor.from_pretrained(model_name)
        self.model = BlipForConditionalGeneration.from_pretrained(model_name)

    async def caption(self, image_path: str) -> str:
        image = Image.open(image_path).convert("RGB")
        inputs = self.processor(image, return_tensors="pt")

        output = self.model.generate(**inputs, max_new_tokens=100)
        caption = self.processor.decode(output[0], skip_special_tokens=True)

        return caption
```

---

## OCR Configuration

### Engine Options

| Engine | Language Support | Speed | Accuracy |
|--------|------------------|-------|----------|
| Tesseract | 100+ | Fast | Good |
| EasyOCR | 80+ | Medium | Better |
| PaddleOCR | 80+ | Fast | Best |

### OCR Code

```python
import easyocr

class OCREngine:
    """EasyOCR-based text extraction."""

    def __init__(self, languages: list[str] = ["en"]):
        self.reader = easyocr.Reader(languages, gpu=True)

    async def extract_text(self, image_path: str) -> str:
        results = self.reader.readtext(image_path)
        # results: [(bbox, text, confidence), ...]

        text_blocks = [text for _, text, conf in results if conf > 0.5]
        return "\n".join(text_blocks)
```

---

## Supported Formats

### Images

| Format | Extension | Notes |
|--------|-----------|-------|
| JPEG | `.jpg`, `.jpeg` | Most common |
| PNG | `.png` | Lossless |
| WebP | `.webp` | Modern format |
| BMP | `.bmp` | Uncompressed |
| TIFF | `.tiff` | High quality |
| GIF | `.gif` | First frame only |

### Videos

| Format | Extension | Notes |
|--------|-----------|-------|
| MP4 | `.mp4` | Most common |
| AVI | `.avi` | Legacy |
| MKV | `.mkv` | Container |
| MOV | `.mov` | Apple format |
| WebM | `.webm` | Web video |

**Requires:** ffmpeg installed for video frame extraction.

---

## Video Processing

For video files, the service extracts keyframes:

```python
import cv2
import numpy as np

class VideoProcessor:
    """Extract keyframes from video for analysis."""

    def __init__(self, max_frames: int = 10):
        self.max_frames = max_frames

    async def extract_keyframes(self, video_path: str) -> list[str]:
        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # Sample frames evenly
        frame_indices = np.linspace(0, total_frames - 1, self.max_frames, dtype=int)

        keyframes = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                frame_path = f"/tmp/frame_{idx}.jpg"
                cv2.imwrite(frame_path, frame)
                keyframes.append(frame_path)

        cap.release()
        return keyframes
```

---

## Service Structure

```
src/services/vision/
├── main.py                 # Entry point
├── nats/
│   └── subscriber.py
├── logic/
│   ├── vision_service.py
│   ├── captioner.py        # BLIP wrapper
│   ├── ocr.py              # OCR wrapper
│   ├── video_processor.py  # Frame extraction
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

# BLIP
BLIP_MODEL=Salesforce/blip-image-captioning-base
BLIP_DEVICE=cuda

# OCR
OCR_ENGINE=easyocr            # tesseract, easyocr, paddleocr
OCR_LANGUAGES=en,es,fr        # Comma-separated

# Video Processing
VISION_MAX_FRAMES=10          # Max keyframes to extract
VISION_TEMP_DIR=/tmp/vision   # Temp storage
```

---

## GPU Support

Both BLIP and OCR benefit from GPU acceleration:

| Component | CPU | GPU |
|-----------|-----|-----|
| BLIP captioning | ~5s/image | ~0.5s/image |
| EasyOCR | ~2s/image | ~0.3s/image |

```python
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"
model = BlipForConditionalGeneration.from_pretrained(model_name).to(device)
```

---

## Error Handling

| Error | Handling |
|-------|----------|
| File not found | NAK message, retry |
| Unsupported format | Mark document as failed |
| BLIP error | NAK message, retry up to 3x |
| OCR error | Continue with caption only |
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
  "blip_model": "blip-image-captioning-base",
  "ocr_engine": "easyocr",
  "device": "cuda"
}
```

---

## Output Format

The combined description follows this format:

```
[Caption]
A person working on a laptop in a modern office with large windows.

[Extracted Text]
Q4 Revenue Report
Total: $1.2M
Growth: 15%
```

This combined text is stored in the document's `content` field and sent to Semantic for chunking and embedding.

---

## References

- [NATS Messaging](../nats-messaging.md) - Message flow documentation
- [Proto Definitions](../proto-definitions.md) - Message schemas
- [Semantic Service](./semantic-service.md) - Sends image.analyze
- [Salesforce BLIP](https://github.com/salesforce/BLIP) - Image captioning model
- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - OCR library
