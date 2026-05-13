# Ollama Model Routing System - Debug & Fix Summary

## Problem Statement

The frontend displayed "GPU Status → Unavailable" even when Ollama was healthy, models were loaded, and latency was returned. This indicated multiple issues with GPU detection logic, Ollama telemetry parsing, and frontend state mapping.

## Root Causes Identified

1. **`get_gpu_info()`** always returned `gpu_available: True` when Ollama API responded, regardless of actual GPU detection from `/api/ps`
2. **No CPU fallback** was implemented when no GPU was detected
3. **Frontend** only showed "Available" or "Unavailable" without CPU mode handling
4. **GPUMonitor** didn't properly parse GPU data from Ollama's `/api/ps` response

## Files Modified

### Backend Files

| File | Changes |
|------|---------|
| `models/providers/local.py` | Added GPUInfo dataclass, fixed get_gpu_info(), added nvidia-smi and AMD checks |
| `models/providers/base.py` | Added gpu_count and inference_mode to ProviderHealth |
| `models/routing/gpu_scheduler.py` | Enhanced GPUMonitor with detailed status and display messages |
| `api/routes/models.py` | Added GPUStatusDetail model, enhanced endpoints, added /models/gpu-status |
| `models/routing/router.py` | Added routing telemetry logging |
| `models/routing/gpu_telemetry.py` | NEW - Structured logging for GPU and routing events |

### Frontend Files

| File | Changes |
|------|---------|
| `frontend/types/index.ts` | Extended GPUStatus with mode, status, memory, display fields |
| `frontend/features/models/model-dashboard.tsx` | Complete rewrite of GPU status rendering with CPU mode support |
| `frontend/components/ui/progress.tsx` | Added indicatorClassName prop |
| `frontend/services/api.ts` | Added getGPUStatus() method |

### Deployment Files

| File | Changes |
|------|---------|
| `deployment/docker-compose.yml` | Added GPU passthrough to Ollama and API containers |

### Test Files

| File | Changes |
|------|---------|
| `tests/models/test_gpu_detection.py` | NEW - Comprehensive GPU detection tests |
| `frontend/tests/models/gpu-status.test.ts` | NEW - Frontend state tests |

## Key Features Implemented

### 1. Multi-Source GPU Detection
```python
# 1. Ollama's /api/ps endpoint (primary)
# 2. Direct nvidia-smi command (verification)
# 3. AMD rocm-smi (fallback)
# 4. CPU-only mode detection
```

### 2. Inference Modes
- **NVIDIA**: Full GPU acceleration
- **AMD**: ROCm-based GPU
- **CPU**: Graceful fallback when no GPU available

### 3. GPU Status States
- `available`: GPU ready for inference
- `busy`: GPU under load (>70% memory)
- `saturated`: GPU heavily loaded (>90% memory)
- `cpu_mode`: Running on CPU (Ollama healthy, no GPU)
- `error`: Detection failed

### 4. Structured Logging
- GPU state change tracking
- Routing decision logging with inference mode
- Model load events
- Error logging with context

## API Response Format

```json
{
  "timestamp": "2026-05-12T10:00:00Z",
  "providers": [{
    "name": "ollama",
    "type": "local",
    "status": "healthy",
    "available": true,
    "inference_mode": "nvidia",
    "gpu_count": 1,
    "gpu_available": true,
    "memory_percent": 33.3
  }],
  "gpu_status": {
    "available": true,
    "mode": "nvidia",
    "status": "available",
    "gpu_count": 1,
    "memory": {
      "total_mb": 24576,
      "used_mb": 8192,
      "free_mb": 16384,
      "percent": 33.3
    },
    "compute_utilization": 35,
    "temperature": 65,
    "driver_version": "525.85.05",
    "model_loaded": "qwen3",
    "display_status": "GPU Available",
    "display_icon": "available"
  }
}
```

## Frontend Display States

| State | Display | Color |
|-------|---------|-------|
| GPU Available | "GPU Available" | Green |
| GPU Busy | "GPU Busy (73%)" | Yellow |
| GPU Saturated | "GPU Saturated (95%)" | Red (pulsing) |
| CPU Mode | "CPU Inference Mode" | Blue |
| Error | Error message | Red |

## Docker GPU Passthrough

```yaml
ollama:
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu, compute, utility]
```

## Test Results

```
51 passed tests covering:
- GPU detection with NVIDIA GPU
- CPU fallback mode
- API error handling
- GPU monitor functionality
- Telemetry logging
- Routing decisions with fallback
```

## Usage

### Backend Health Check
```bash
curl http://localhost:8000/api/v1/models/status
curl http://localhost:8000/api/v1/models/gpu-status
```

### Docker GPU Verification
```bash
docker exec ollama nvidia-smi
```

### Expected Behavior

1. **With NVIDIA GPU**: Shows "GPU Available" with VRAM usage
2. **Without NVIDIA GPU**: Shows "CPU Inference Mode" (NOT "Unavailable")
3. **GPU Unavailable but Ollama Running**: Shows "CPU Inference Mode"
4. **Ollama Down**: Shows connection error

## Migration Notes

- Frontend must handle new `mode` field (nvidia/amd/cpu)
- Frontend must handle new `status` field (available/busy/saturated/cpu_mode/error)
- Frontend should use `display_status` for user-facing messages
- Backward compatible with existing API structure (legacy fields still present)
