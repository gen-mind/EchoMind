# EchoMind Cloud Sizing Guide

> **No GPU** = Add external LLM API costs (~$50-500/mo depending on usage)

---

## Small: 10-30 Users (No GPU)

| Cloud | Instance | vCPU/RAM | GPU | US/mo | EU/mo |
|-------|----------|----------|-----|-------|-------|
| **GCP** | e2-standard-8 | 8 / 32 GB | — | **$197** | $226 |
| AWS | m6a.2xlarge | 8 / 32 GB | — | $253 | $326 |
| Azure | D8as_v5 | 8 / 32 GB | — | $251 | $301 |

---

## Medium: 30-50 Users — No GPU

| Cloud | Instance | vCPU/RAM | GPU | US/mo | EU/mo |
|-------|----------|----------|-----|-------|-------|
| **GCP** | e2-standard-16 | 16 / 64 GB | — | **$394** | $453 |
| AWS | m6a.4xlarge | 16 / 64 GB | — | $505 | $559 |
| Azure | D16as_v5 | 16 / 64 GB | — | $502 | $603 |

## Medium: 30-50 Users — With GPU

| Cloud | Instance | vCPU/RAM | GPU | US/mo | EU/mo |
|-------|----------|----------|-----|-------|-------|
| **AWS** | g5.4xlarge | 16 / 64 GB | 1x A10G 24GB | **$1,186** | $1,186 |
| GCP | g2-standard-24 | 24 / 96 GB | 2x L4 48GB | $2,117 | $2,438 |
| Azure | NC24ads_A100_v4 | 24 / 220 GB | 1x A100 80GB | $2,679 | $3,081 |

---

## Large: 50-200 Users — No GPU

| Cloud | Instance | vCPU/RAM | GPU | US/mo | EU/mo |
|-------|----------|----------|-----|-------|-------|
| **GCP** | e2-standard-32 | 32 / 128 GB | — | **$781** | $898 |
| AWS | m6a.8xlarge | 32 / 128 GB | — | $1,009 | $1,118 |
| Azure | D32as_v5 | 32 / 128 GB | — | $1,004 | $1,205 |

## Large: 50-200 Users — With GPU

| Cloud | Instance | vCPU/RAM | GPU | US/mo | EU/mo |
|-------|----------|----------|-----|-------|-------|
| **AWS** | g5.12xlarge | 48 / 192 GB | 4x A10G 96GB | **$4,141** | $4,141 |
| GCP | a2-highgpu-2g | 24 / 170 GB | 2x A100 80GB | $5,366 | $6,169 |
| Azure | NC48ads_A100_v4 | 48 / 440 GB | 2x A100 160GB | $5,366 | $6,169 |

---

## Extra Large: 200-500 Users — No GPU

| Cloud | Instance | vCPU/RAM | GPU | US/mo | EU/mo |
|-------|----------|----------|-----|-------|-------|
| **GCP** | e2-standard-64 | 64 / 256 GB | — | **$1,562** | $1,796 |
| AWS | m6a.16xlarge | 64 / 256 GB | — | $2,018 | $2,237 |
| Azure | D64as_v5 | 64 / 256 GB | — | $2,009 | $2,411 |

## Extra Large: 200-500 Users — With GPU

| Cloud | Instance | vCPU/RAM | GPU | US/mo | EU/mo |
|-------|----------|----------|-----|-------|-------|
| **Azure** | ND96asr_v4 | 96 / 900 GB | 8x A100 320GB | **$19,856** | $22,834 |
| AWS | p4d.24xlarge | 96 / 1152 GB | 8x A100 320GB | $23,922 | $26,317 |
| GCP | a2-megagpu-16g | 96 / 1360 GB | 16x A100 640GB | $29,200 | $33,580 |

---

## Quick Summary

| Tier | Users | Best No GPU | US/mo | Best GPU | US/mo |
|------|-------|-------------|-------|----------|-------|
| Small | 10-30 | GCP e2-std-8 | $197 | — | — |
| Medium | 30-50 | GCP e2-std-16 | $394 | AWS g5.4xl | $1,186 |
| Large | 50-200 | GCP e2-std-32 | $781 | AWS g5.12xl | $4,141 |
| XL | 200-500 | GCP e2-std-64 | $1,562 | Azure ND96asr | $19,856 |

---

## Reserved Instance Discounts

| Provider | 1-Year | 3-Year |
|----------|--------|--------|
| AWS | 35% | 55% |
| GCP | 37% | 55% |
| Azure | 40% | 62% |

---

## Notes

- Prices are on-demand, January 2025
- "No GPU" requires external LLM API (OpenAI/Anthropic)
- "With GPU" includes local embedder + vLLM 10B model
- EU pricing is ~10-20% higher than US