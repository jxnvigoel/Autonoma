# Ollama Local Setup

## Overview

Ollama was configured on an Apple M4 Mac to run a Large Language Model (LLM) locally without requiring a cloud API key.

## Hardware

- **Device:** MacBook Pro
- **Chip:** Apple M4
- **CPU:** 10 cores (4 Performance + 6 Efficiency)
- **Memory:** 16 GB
- **Architecture:** ARM64 (`arm64`)
- **GPU acceleration:** Apple GPU / Metal
- **NVIDIA CUDA:** Not applicable on this Mac

## 1. Verify Mac Architecture

The Mac architecture was checked using:

```bash
uname -m
```

Output:

```text
arm64
```

This confirms that the machine uses Apple Silicon.

Hardware information was also checked with:

```bash
system_profiler SPHardwareDataType
```

Memory was verified with:

```bash
sysctl -n hw.memsize
```

The result was:

```text
17179869184
```

which corresponds to 16 GB of RAM.

## 2. Install Ollama

Ollama was installed on macOS using the official Ollama macOS installer.

After installation, the installation was verified with:

```bash
ollama --version
```

Installed version:

```text
ollama version 0.35.0
```

> Note: The exact Ollama version may change if Ollama is updated in the future.

## 3. Check Installed Models

The available local models were checked using:

```bash
ollama list
```

Initially, the list was empty because no model had been downloaded.

## 4. Download the LLM

The initial model selected for the 16 GB Mac was **Llama 3.2 3B**.

It was downloaded using:

```bash
ollama pull llama3.2:3b
```

The download completed successfully with:

```text
success
```

## 5. Verify the Model

After downloading, the model was verified with:

```bash
ollama list
```

The installed model appeared as:

```text
NAME            ID              SIZE
llama3.2:3b     a80c4f17acd5    2.0 GB
```

## 6. Run the Local Model

The model was started using:

```bash
ollama run llama3.2:3b
```

This opened the Ollama interactive prompt:

```text
>>>
```

A test prompt was sent:

```text
hello
```

The model successfully generated a response, confirming that local inference was working.

The interactive session can be exited using:

```text
/bye
```

## 7. Current Ollama Setup

The current local AI environment is:

```text
MacBook Pro
    │
    ├── Apple M4
    ├── 16 GB RAM
    └── ARM64
          │
          ▼
       Ollama
       v0.35.0
          │
          ▼
    Llama 3.2 3B
       ~2.0 GB
          │
          ▼
    Apple GPU / Metal
```

## 8. Important Hardware Note

This Mac has an Apple M4 GPU, not an NVIDIA GPU.

Therefore, NVIDIA drivers and CUDA were **not installed**.

Ollama can use Apple's hardware acceleration through the Apple GPU/Metal stack. NVIDIA/CUDA support would only be relevant when running the application on a compatible NVIDIA-based machine.

## 9. Useful Commands

### Check Ollama version

```bash
ollama --version
```

### List downloaded models

```bash
ollama list
```

### Download a model

```bash
ollama pull <model-name>
```

### Run a model

```bash
ollama run <model-name>
```

### Exit an interactive model session

```text
/bye
```

## 10. Result

Ollama is successfully installed and configured on the Apple M4 Mac.

The following have been verified:

- [x] Apple Silicon / ARM64 detected
- [x] Ollama installed
- [x] Ollama CLI working
- [x] Llama 3.2 3B downloaded
- [x] Local model visible through `ollama list`
- [x] Local inference tested successfully
- [x] Apple GPU/Metal used instead of NVIDIA CUDA

The next step is to connect Ollama to the planned **React + Tauri desktop application** through Ollama's local API.
