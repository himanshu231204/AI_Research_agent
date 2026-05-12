# Troubleshooting Guide

## Purpose

This document provides comprehensive troubleshooting guidance for common issues. It covers websocket failures, Redis issues, Celery failures, Ollama issues, Docker issues, and Kubernetes issues. This documentation is essential for operators and developers debugging production issues.

---

## 1. WebSocket Issues

### Connection Failures

**Symptom**: WebSocket connection fails or disconnects frequently

**Diagnosis**:
```bash
# Check API logs
docker-compose logs api | grep -i websocket

# Check network connectivity
curl -i -N -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  http://localhost:8000/ws/test
```

**Solutions**:

1. **Check WebSocket endpoint**:
```python
# Verify endpoint is registered
from api.routes import websocket
print(websocket.router.routes)
```

2. **Check CORS configuration**:
```python
# Ensure WebSocket is allowed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origins
    allow_methods=["*"],
    allow_headers=["*"],
)
```

3. **Check timeout settings**:
```yaml
# Increase timeout in ingress
nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
```

---

## 2. Redis Issues

### Connection Refused

**Symptom**: `Error: Connection refused to Redis`

**Diagnosis**:
```bash
# Check Redis is running
docker-compose ps redis

# Test connection
docker-compose exec redis redis-cli ping
```

**Solutions**:

1. **Start Redis**:
```bash
docker-compose up -d redis
```

2. **Check connection string**:
```python
# Verify REDIS_URL format
import os
print(os.getenv("REDIS_URL"))  # Should be: redis://host:port/db
```

3. **Check firewall**:
```bash
# Allow Redis port
sudo ufw allow 6379/tcp
```

### Memory Issues

**Symptom**: Redis out of memory errors

**Diagnosis**:
```bash
# Check Redis memory usage
docker-compose exec redis redis-cli INFO memory

# Check keys
docker-compose exec redis redis-cli DBSIZE
```

**Solutions**:

1. **Set memory limit**:
```python
# In redis.conf
maxmemory 2gb
maxmemory-policy allkeys-lru
```

2. **Clear old sessions**:
```python
# Delete old session keys
redis-cli KEYS "session:*" | xargs redis-cli DEL
```

---

## 3. Celery Issues

### Worker Not Starting

**Symptom**: Celery worker fails to start

**Diagnosis**:
```bash
# Check worker logs
docker-compose logs celery-worker

# Check broker connection
celery -A workers.celery_app inspect ping
```

**Solutions**:

1. **Verify broker URL**:
```bash
# Test Redis connection
redis-cli PING

# Check broker URL in config
grep -r "broker" workers/celery_app.py
```

2. **Fix import errors**:
```bash
# Install missing dependencies
pip install -r requirements.txt

# Check Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

3. **Check queue configuration**:
```python
# Verify queue exists
from workers.queues import QUEUES
print(QUEUES.keys())
```

### Task Timeout

**Symptom**: Tasks timing out before completion

**Diagnosis**:
```bash
# Check task status
celery -A workers.celery_app inspect active

# View task result
celery -A workers.celery_app result <task_id>
```

**Solutions**:

1. **Increase timeout**:
```python
@celery.task(
    time_limit=600,  # 10 minutes
    soft_time_limit=480  # 8 minutes
)
def my_task():
    pass
```

2. **Check worker concurrency**:
```bash
# Increase worker processes
celery -A workers worker --concurrency=4
```

---

## 4. Ollama Issues

### Model Not Available

**Symptom**: Ollama model not found or not loaded

**Diagnosis**:
```bash
# List available models
curl http://localhost:11434/api/tags

# Check model status
ollama list
```

**Solutions**:

1. **Pull required model**:
```bash
ollama pull qwen3
ollama pull llama3
ollama pull mistral
```

2. **Check model name**:
```python
# Verify model name in code
from models.ollama_client import OllamaClient
client = OllamaClient()
print(client.model_name)  # Should match pulled model
```

3. **Restart Ollama**:
```bash
# Restart Ollama service
docker-compose restart ollama
```

### GPU Memory Exhausted

**Symptom**: CUDA out of memory error

**Diagnosis**:
```bash
# Check GPU usage
nvidia-smi

# Check Ollama logs
docker-compose logs ollama
```

**Solutions**:

1. **Unload unused models**:
```bash
ollama rm <unused_model>
```

2. **Reduce batch size**:
```python
# In embedding generation
batch_size = 8  # Reduce from 32
```

3. **Use smaller model**:
```python
# Switch to smaller model
model_name = "llama3:8b"  # Instead of 70b
```

---

## 5. Docker Issues

### Container Won't Start

**Symptom**: Container exits immediately after starting

**Diagnosis**:
```bash
# Check container logs
docker-compose logs <service>

# Inspect container
docker inspect <container_id>
```

**Solutions**:

1. **Check environment variables**:
```bash
# Verify .env file exists
cat .env

# Check required variables
grep -E "^[A-Z_]+=" .env
```

2. **Check port conflicts**:
```bash
# Find port conflicts
lsof -i :8000

# Change port in docker-compose.yml
```

3. **Check volume permissions**:
```bash
# Fix volume permissions
sudo chown -R $(id -u):$(id -g) ./data
```

### Image Build Fails

**Symptom**: Docker build fails with error

**Diagnosis**:
```bash
# Build with verbose output
docker-compose build --no-cache

# Check build logs
docker-compose build 2>&1 | tail -50
```

**Solutions**:

1. **Check base image**:
```dockerfile
# Use specific version
FROM python:3.11-slim
```

2. **Fix dependency issues**:
```dockerfile
# Install in correct order
RUN pip install --no-cache-dir -r requirements.txt
```

3. **Clear Docker cache**:
```bash
docker system prune -a
```

---

## 6. Kubernetes Issues

### Pod CrashLoopBackOff

**Symptom**: Pod keeps restarting

**Diagnosis**:
```bash
# Check pod status
kubectl get pods -n research-agent

# View pod logs
kubectl logs <pod-name> -n research-agent

# Describe pod
kubectl describe pod <pod-name> -n research-agent
```

**Solutions**:

1. **Check resource limits**:
```yaml
resources:
  requests:
    memory: "1Gi"
  limits:
    memory: "2Gi"
```

2. **Fix liveness/readiness probes**:
```yaml
livenessProbe:
  httpGet:
    path: /api/v1/health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

3. **Check volume mounts**:
```yaml
volumeMounts:
  - name: data
    mountPath: /data
```

### Service Unavailable

**Symptom**: 503 Service Unavailable errors

**Diagnosis**:
```bash
# Check service endpoints
kubectl get endpoints -n research-agent

# Check pod selectors
kubectl get svc <service> -n research-agent -o yaml
```

**Solutions**:

1. **Verify pod labels**:
```yaml
selector:
  app: research-api
```

2. **Check pod readiness**:
```bash
kubectl get pods -n research-agent -o wide
```

3. **Restart deployment**:
```bash
kubectl rollout restart deployment/research-api -n research-agent
```

---

## 7. Performance Issues

### High Latency

**Diagnosis**:
```bash
# Check API response time
time curl http://localhost:8000/api/v1/health

# Check database query time
# Enable query logging
```

**Solutions**:

1. **Add caching**:
```python
from functools import lru_cache

@lru_cache()
def get_cached_data():
    pass
```

2. **Optimize database queries**:
```sql
-- Add indexes
CREATE INDEX idx_sessions_user ON sessions(user_id);
```

3. **Scale workers**:
```bash
kubectl scale deployment/celery-worker --replicas=10 -n research-agent
```

---

## 8. Emergency Procedures

### Full System Restart

```bash
# Stop everything
docker-compose down

# Clear data (if needed)
rm -rf ./data/*

# Restart
docker-compose up -d

# Check health
curl http://localhost:8000/api/v1/health
```

### Database Recovery

```bash
# Connect to database
docker-compose exec postgres psql -U postgres -d research_agent

# Check connections
SELECT * FROM pg_stat_activity;

# Kill idle connections
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle';
```

---

## Related Documentation

- [Setup](setup.md)
- [Local Development](local-development.md)
- [Contributing](contributing.md)