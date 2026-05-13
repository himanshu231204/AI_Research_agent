# 🎯 Quick Start - User Model Selection

## What You Get

✅ **No more hardcoded models**  
✅ **Dynamic model discovery** (auto finds Ollama models)  
✅ **User can pick any installed model**  
✅ **Fallback if model missing**  

---

## How It Works

### **Installation Sequence**

```
1. User opens Research Chat
   ↓
2. Clicks model selector [Auto ▼]
   ↓
3. Backend queries Ollama: /api/tags
   ↓
4. Returns all installed models:
   • llama3.2:3b ✓
   • mistral:latest ✓
   • qwen2.5-coder:7b ✓
   ↓
5. User selects from dropdown
   ↓
6. Selection saved to session
   ↓
7. All future requests use selected model
```

---

## Current Status

### ✅ What Works Now

| Feature | Works? | Notes |
|---------|--------|-------|
| Show Ollama models | ✅ | Auto-discovers from `/api/tags` |
| User selects model | ✅ | Via dropdown in chat header |
| Remember selection | ✅ | Per session |
| Switch models mid-chat | ✅ | Just click selector again |
| Auto-fallback | ✅ | If selected model missing |
| Show model status | ✅ | Health, latency, availability |
| Refresh list | ✅ | Button in selector dropdown |

### 📍 Where Is It?

**In Chat UI:**
```
┌─────────────────────────────────────────┐
│  Research Chat    │ [Auto ▼]  🔄       │  ← Click here to select model
├─────────────────────────────────────────┤
│                                         │
│  Chat messages here...                  │
│                                         │
└─────────────────────────────────────────┘
```

**Dropdown Opens:**
```
┌─────────────────────────────┐
│ Model Selection             │
├─────────────────────────────┤
│ Provider                    │
│ [Auto] [Ollama] [OpenAI]   │
├─────────────────────────────┤
│ Model (if Ollama selected)  │
│ ✓ llama3.2:3b  (50ms)      │
│   mistral:latest (55ms)    │
│   qwen2.5-coder:7b (60ms)  │
├─────────────────────────────┤
│ Routing Mode                │
│ ✓ Auto Routing             │
│   Local Only               │
│   Cloud Only               │
│   Hybrid                   │
├─────────────────────────────┤
│ 🔄 Refresh Local Models    │
│                             │
│ Active: ollama/llama3.2:3b │
└─────────────────────────────┘
```

---

## Environment Configuration

### **Current (.env)**
```bash
OLLAMA_MODEL=qwen3
```

### **What This Means**

- **NOT a requirement** anymore
- **Only a fallback** if no model selected
- **Can be any model** from Ollama
- **Or left empty** - user always picks one

### **To Use Different Default**

```bash
# Option 1: Keep as is (qwen3 is fallback if nothing selected)
OLLAMA_MODEL=qwen3

# Option 2: Set to an installed model
OLLAMA_MODEL=llama3.2:3b

# Option 3: Leave empty (user must select)
OLLAMA_MODEL=
```

---

## API Endpoints (For Developers)

### **List Local Models**
```bash
GET http://localhost:8000/api/v1/models/local

# Returns:
{
  "models": [
    {
      "name": "llama3.2:3b",
      "display_name": "Llama 3.2",
      "available": true,
      "latency_ms": 45
    }
  ],
  "count": 1
}
```

### **Select Model for Session**
```bash
POST http://localhost:8000/api/v1/models/select

{
  "session_id": "user-session-123",
  "provider": "ollama",
  "model": "llama3.2:3b",
  "routing_mode": "local_only"
}
```

### **Check Provider Status**
```bash
GET http://localhost:8000/api/v1/models/providers/status

# Returns provider health, available models, latency
```

---

## No More Hardcoding! 

### **Before (Bad)** ❌
```python
# Hardcoded in code
if model_name == "qwen3":
    call_ollama(model="qwen3")
```

### **After (Good)** ✅
```python
# Auto-discovers
available_models = await ollama.get_available_models()
# Returns: ["llama3.2:3b", "mistral:latest", ...]

# User selects from available
selected = user_selection  # "llama3.2:3b"

# System uses it
call_ollama(model=selected)
```

---

## Start Using It Now

### **1. Start Backend**
```bash
cd C:\Users\himan\Desktop\Research_agent
.\venv\Scripts\activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### **2. Start Frontend**
```bash
cd frontend
npm run dev
```

### **3. Open Browser**
```
http://localhost:3000
```

### **4. Use It**
- Open chat
- Click `[Auto ▼]` button in header
- Select `Ollama` → Choose model
- Done! ✨

---

## Troubleshooting

### **"No models found"**
- Ollama not running: `ollama serve`
- No models installed: `ollama pull llama3.2`
- Wait 2-3 seconds for auto-refresh

### **"Model not available"**
- User selected model that was removed
- System auto-falls back to first available
- Check `/api/v1/models/local` endpoint

### **Selected model ignored**
- Session ID mismatch
- API not running
- Browser cache - hard refresh (Ctrl+Shift+R)

---

## Architecture Diagram

```
User Interface
    ↓
[Model Selector Dropdown]
    ↓
useModelSelectionStore (Zustand)
    ↓
modelsApi.selectModel()
    ↓
Backend: POST /models/select
    ↓
ModelRegistry.select_model()
    ↓
Session-based Selection
    ↓
When making requests:
ModelRouter.resolve_model_for_session()
    ↓
OllamaProvider._resolve_model_name()
    ↓
HTTP POST to Ollama with selected model
```

---

**Everything is ready to use! Just run the servers and click the model selector.** 🚀
