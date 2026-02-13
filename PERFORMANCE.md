# Performance Optimization Guide

## Problem: Ollama Burning CPU 🔥

If Ollama is using 100% CPU and making your computer hot, here are solutions:

---

## Quick Fixes (Immediate Relief)

### Option 1: Use DeepSeek Only (Fastest ⚡)

**Edit `.env`:**
```bash
USE_DEEPSEEK_ONLY=true
```

This skips Ollama entirely and uses DeepSeek API for all agents.

**Benefits:**
- ✅ No CPU usage from local models
- ✅ Faster reviews (cloud API)
- ✅ No model loading time
- ✅ Less memory usage

**Trade-offs:**
- ❌ Uses DeepSeek API credits
- ❌ Requires internet connection

---

### Option 2: Limit Ollama CPU Threads

**Edit `.env`:**
```bash
OLLAMA_NUM_THREADS=2  # Use only 2 CPU cores
```

**Levels:**
- `2` = Low CPU usage (slowest)
- `4` = Medium (balanced)
- `8` = High (fastest, default)

---

### Option 3: Use Smaller Model

Replace `qwen2.5-coder:7b` with a smaller model:

```bash
# Pull smaller model
ollama pull qwen2.5-coder:3b

# Update .env
IMPLEMENTER_MODEL=qwen2.5-coder:3b
```

**Model sizes:**
- `1.5b` = Tiny, fast, less accurate
- `3b` = Small, faster, good quality
- `7b` = Medium (current), balanced
- `14b` = Large, slow, best quality

---

## Advanced Optimizations

### 1. Reduce Context Window

```bash
OLLAMA_CONTEXT_SIZE=2048  # Default is 4096
```

Smaller context = faster processing, but less code per review.

---

### 2. Review Smaller Code Chunks

```bash
MAX_PATCH_SIZE=300  # Review max 300 lines at a time
```

Breaks large files into smaller pieces for Ollama.

---

### 3. Skip Test File Reviews

```bash
SKIP_TEST_REVIEWS=true
```

Don't waste expensive model inference on reviewing test files.

---

### 4. Use GPU (If Available)

If you have a Mac with Metal or NVIDIA GPU:

```bash
# Mac (Apple Silicon - M1/M2/M3)
OLLAMA_NUM_GPU=1  # Offload to Metal

# NVIDIA GPU (Linux/Windows)
OLLAMA_NUM_GPU=35  # Number of layers to offload
```

This moves computation from CPU to GPU.

---

## Recommended Settings for Different Scenarios

### 🎯 For Speed (Low CPU Usage)

```bash
# .env
USE_DEEPSEEK_ONLY=true
```

**Result:** No Ollama usage, fast reviews, uses API credits.

---

### ⚖️ Balanced (Some Local, Some Cloud)

```bash
# .env
USE_DEEPSEEK_ONLY=false
OLLAMA_NUM_THREADS=4
OLLAMA_CONTEXT_SIZE=2048
IMPLEMENTER_MODEL=qwen2.5-coder:3b  # Use smaller model
MAX_PATCH_SIZE=300
```

**Result:** Moderate CPU, faster than 7b model, good quality.

---

### 💪 Maximum Quality (Accept High CPU)

```bash
# .env
USE_DEEPSEEK_ONLY=false
OLLAMA_NUM_THREADS=8
OLLAMA_CONTEXT_SIZE=4096
IMPLEMENTER_MODEL=qwen2.5-coder:14b  # Largest model
```

**Result:** Best code quality, high CPU usage, slower.

---

## Monitoring Ollama Performance

### Check CPU Usage

```bash
# macOS/Linux
top -pid $(pgrep ollama)

# Or use Activity Monitor (Mac) / Task Manager (Windows)
```

### Check Ollama Status

```bash
# See loaded models
ollama list

# See running models
ollama ps

# Stop Ollama
killall ollama
```

---

## FAQ

**Q: Why is Ollama so CPU-intensive?**
A: Running a 7B parameter model on CPU is computationally expensive. Each token generation requires billions of calculations.

**Q: Will `USE_DEEPSEEK_ONLY=true` cost money?**
A: Yes, but DeepSeek is very cheap (~$0.14 per million input tokens). A typical PR review costs less than $0.01.

**Q: Can I use both Ollama and DeepSeek?**
A: Yes (current default). DeepSeek reviews, Ollama implements. Set `USE_DEEPSEEK_ONLY=false`.

**Q: What if I have a GPU?**
A: Set `OLLAMA_NUM_GPU` to offload to GPU. This dramatically reduces CPU usage.

**Q: My laptop is overheating. What should I do?**
A: Set `USE_DEEPSEEK_ONLY=true` immediately. This will stop all local model inference.

---

## Comparison Table

| Setting | CPU Usage | Speed | Quality | Cost |
|---------|-----------|-------|---------|------|
| DeepSeek Only | 🟢 None | ⚡ Fastest | 🌟 Excellent | 💰 ~$0.01/PR |
| Qwen 3B | 🟡 Medium | ⚡ Fast | ⭐ Good | 🆓 Free |
| Qwen 7B | 🔴 High | 🐌 Slower | ⭐⭐ Very Good | 🆓 Free |
| Qwen 14B | 🔥 Very High | 🐌🐌 Slowest | ⭐⭐⭐ Best | 🆓 Free |

---

## Apply Changes

After editing `.env`:

```bash
# 1. Restart Ollama (if using local models)
killall ollama
# export OLLAMA_MODELS=/path/to/your/ollama/models  # optional: set custom model path
ollama serve &

# 2. Run workflow
python -m pr_workflow.main <pr-url> --comment
```

---

## Need Help?

1. Check Ollama logs: `tail -f /tmp/ollama.log`
2. Monitor CPU: `top -pid $(pgrep ollama)`
3. Try DeepSeek-only mode first
4. Use smaller models if local inference is needed

---

**Recommendation:** For most users, `USE_DEEPSEEK_ONLY=true` provides the best balance of speed, quality, and low CPU usage.
