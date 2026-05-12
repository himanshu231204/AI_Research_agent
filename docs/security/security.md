# Security Documentation

## Purpose

This document provides comprehensive documentation of the security architecture. It explains browser isolation, RBAC, tenant isolation, secrets management, and API security. This documentation is essential for security engineers and operators ensuring the platform meets security requirements.

---

## 1. Security Architecture Overview

The platform implements defense-in-depth security:

```mermaid
flowchart TB
    subgraph "Perimeter Security"
        FW[Firewall]
        LB[Load Balancer]
        WAF[Web Application Firewall]
    end

    subgraph "Authentication"
        JWT[JWT Auth]
        OAUTH[OAuth 2.0]
        APIK[API Keys]
    end

    subgraph "Authorization"
        RBAC[RBAC]
        ABAC[ABAC]
    end

    subgraph "Network Security"
        NP[Network Policies]
        TL[Transport Layer Security]
        VI[VPC Isolation]
    end

    subgraph "Application Security"
        BI[Browser Isolation]
        SI[Sandbox Isolation]
        VA[Input Validation]
    end

    subgraph "Data Security"
        EN[Encryption at Rest]
        ET[Encryption in Transit]
        KM[Key Management]
    end

    FW --> LB
    LB --> WAF
    WAF --> JWT
    JWT --> RBAC
    RBAC --> NP
    NP --> BI
    BI --> EN
```

---

## 2. Browser Isolation

### Isolation Architecture

The Browser Agent runs in an isolated container with restricted access:

```mermaid
flowchart TB
    subgraph "Browser Sandbox"
        BC[Browser Container<br/>Ephemeral]
        BW[Browser Worker<br/>Playwright]
        NF[Network Filter<br/>Egress Only]
        FS[Filesystem<br/>Restricted]
    end

    subgraph "Security Controls"
        TO[Timeout<br/>15 min max]
        SC[Session Control<br/>One-time]
        CL[Content Filter<br/>No malicious]
    end

    BC --> TO
    BC --> SC
    BC --> CL
    BC --> NF
    BC --> FS
```

### Browser Security Configuration

```python
class BrowserSandbox:
    def __init__(self):
        self.timeout = 900  # 15 minutes
        self.ephemeral = True

    async def launch_browser(self) -> Browser:
        """Launch isolated browser"""
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-software-rasterizer',
                '--disable-extensions',
                '--disable-background-networking',
                '--disable-default-apps',
                '--disable-sync',
                '--disable-translate',
                '--no-first-run',
                '--single-process',
            ]
        )

        # Create ephemeral context
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            ignore_https_errors=True,
        )

        return browser, context
```

### Network Restrictions

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: browser-sandbox-policy
spec:
  podSelector:
    matchLabels:
      app: browser-worker
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector: {}
      podSelector:
        matchLabels:
          k8s-app: kube-dns
    ports:
    - protocol: TCP
      port: 53
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0
        except:
        - 10.0.0.0/8
        - 172.16.0.0/12
        - 192.168.0.0/16
    ports:
    - protocol: TCP
      port: 443
    - protocol: TCP
      port: 80
```

---

## 3. Role-Based Access Control (RBAC)

### Role Definitions

```python
class Role(str, Enum):
    ADMIN = "admin"
    RESEARCHER = "researcher"
    VIEWER = "viewer"
    API_USER = "api_user"

class Permission(str, Enum):
    CREATE_RESEARCH = "research:create"
    READ_RESEARCH = "research:read"
    DELETE_RESEARCH = "research:delete"
    MANAGE_USERS = "users:manage"
    VIEW_LOGS = "logs:view"
    MANAGE_SETTINGS = "settings:manage"

ROLE_PERMISSIONS = {
    Role.ADMIN: [
        Permission.CREATE_RESEARCH,
        Permission.READ_RESEARCH,
        Permission.DELETE_RESEARCH,
        Permission.MANAGE_USERS,
        Permission.VIEW_LOGS,
        Permission.MANAGE_SETTINGS,
    ],
    Role.RESEARCHER: [
        Permission.CREATE_RESEARCH,
        Permission.READ_RESEARCH,
    ],
    Role.VIEWER: [
        Permission.READ_RESEARCH,
    ],
    Role.API_USER: [
        Permission.CREATE_RESEARCH,
    ],
}
```

### RBAC Middleware

```python
async def require_permission(permission: Permission):
    """Decorator to require specific permission"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            user = get_current_user()
            role = user.role

            if permission not in ROLE_PERMISSIONS.get(role, []):
                raise HTTPException(
                    status_code=403,
                    detail="Insufficient permissions"
                )

            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Usage
@app.post("/research")
@require_permission(Permission.CREATE_RESEARCH)
async def create_research(request: ResearchRequest):
    # Create research session
    pass
```

---

## 4. Tenant Isolation

### Multi-Tenant Architecture

```mermaid
flowchart TB
    subgraph "Tenant A"
        UA[User A1]
        SA[Session A1]
        DA[Data A]
    end

    subgraph "Tenant B"
        UB[User B1]
        SB[Session B1]
        DB[Data B]
    end

    subgraph "Isolation Layer"
        TI[Tenant Context<br/>Middleware]
        QD[Query Filter<br/>Data Isolation]
    end

    UA --> TI
    UB --> TI
    TI --> QD
    QD --> SA
    QD --> SB
    QD --> DA
    QD --> DB
```

### Tenant Context

```python
class TenantContext:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id

    def get_filter(self) -> Dict:
        """Get tenant filter for queries"""
        return {"tenant_id": self.tenant_id}

    def get_table_prefix(self) -> str:
        """Get table prefix for tenant"""
        return f"tenant_{self.tenant_id}_"

# Middleware to extract tenant
async def tenant_middleware(request: Request, call_next):
    # Extract tenant from JWT
    tenant_id = request.state.user.tenant_id

    # Set tenant context
    request.state.tenant = TenantContext(tenant_id)

    response = await call_next(request)
    return response
```

---

## 5. Secrets Management

### Secrets Configuration

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: research-secrets
  namespace: research-agent
type: Opaque
stringData:
  database-url: postgresql://user:pass@postgres:5432/research
  redis-url: redis://redis:6379/0
  ollama-url: http://ollama:11434
  jwt-secret: ${JWT_SECRET}
  openai-api-key: ${OPENAI_API_KEY}
  anthropic-api-key: ${ANTHROPIC_API_KEY}
```

### Secrets Injection

```python
from kubernetes import client, config

def load_secrets():
    """Load secrets from Kubernetes"""
    config.load_incluster_config()
    v1 = client.CoreV1Api()

    secrets = v1.read_namespaced_secret(
        name="research-secrets",
        namespace="research-agent"
    )

    return {
        key: value
        for key, value in secrets.data.items()
    }
```

---

## 6. API Security

### Rate Limiting

```python
from fastapi_limiter import Limiter
from fastapi_limiter.depends import RateLimiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/research/start")
@limiter.limit("10/minute")
async def start_research(request: Request, body: ResearchRequest):
    # Start research
    pass
```

### Input Validation

```python
from pydantic import BaseModel, validator

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=5000)
    max_reflections: int = Field(default=3, ge=1, le=10)
    options: Optional[ResearchOptions] = None

    @validator('query')
    def validate_query(cls, v):
        # Sanitize input
        v = v.strip()
        # Check for malicious patterns
        if '<script>' in v.lower():
            raise ValueError('Invalid characters in query')
        return v
```

### CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.research-agent.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

## 7. Audit Logging

### Audit Events

```python
class AuditEvent(BaseModel):
    timestamp: datetime
    user_id: str
    tenant_id: str
    action: str
    resource: str
    result: str
    ip_address: str
    user_agent: str

async def log_audit(event: AuditEvent):
    """Log audit event"""
    await audit_log.insert(event.dict())
```

### Audit Log Queries

| Event Type | Description | Retention |
|------------|-------------|-----------|
| login | User login | 1 year |
| logout | User logout | 1 year |
| research_create | Research started | 3 years |
| research_access | Research accessed | 3 years |
| settings_change | Settings modified | 5 years |
| admin_action | Admin operations | 5 years |

---

## 8. Security Checklist

### Deployment Security

- [ ] TLS enabled for all endpoints
- [ ] Strong JWT secret configured
- [ ] API keys stored in secrets manager
- [ ] Network policies applied
- [ ] RBAC configured
- [ ] Rate limiting enabled
- [ ] Audit logging enabled
- [ ] Browser isolation configured

### Runtime Security

- [ ] Regular security updates
- [ ] Vulnerability scanning
- [ ] Penetration testing
- [ ] Security monitoring
- [ ] Incident response plan

---

## Related Documentation

- [System Overview](../architecture/system-overview.md)
- [Kubernetes Deployment](../deployment/kubernetes.md)
- [Observability](../observability/observability.md)