# Operations

## Recommended deployment split
If Hermes runs inside a Linux VM without GPU passthrough, do **not** run the hot STT runtime there. Run the runtime on the Windows 11 host that owns the GPU, then point Hermes in the VM at `http://WINDOWS_HOST_IP:8177`.

## 1. Create the local runtime uv env
Linux host:
```bash
cd ~/workspace/discord-voice-stt-enhance
./runtime/setup.sh
```

Windows 11 GPU host:
```bat
cd %USERPROFILE%\workspace\discord-voice-stt-enhance
runtime\setup-windows.bat
```

## 2. Start the STT runtime manually
Linux host:
```bash
cd ~/workspace/discord-voice-stt-enhance
./runtime/launch.sh
```

Windows 11 GPU host:
```bat
cd %USERPROFILE%\workspace\discord-voice-stt-enhance
set HERMES_LOCAL_STT_HOST=0.0.0.0
runtime\launch-windows.bat
```

## 3. Check health
Linux host:
```bash
cd ~/workspace/discord-voice-stt-enhance
./runtime/healthcheck.sh
```
Expected response:
```json
{"status":"ok","model":"large-v3-turbo", ...}
```

Windows 11 GPU host:
```bat
cd %USERPROFILE%\workspace\discord-voice-stt-enhance
runtime\healthcheck-windows.bat
```

## 4. Optional: install as a user systemd service
```bash
cd ~/workspace/discord-voice-stt-enhance
./service/install-systemd.sh
```

To remove it later:
```bash
cd ~/workspace/discord-voice-stt-enhance
./service/uninstall-systemd.sh
```

## 5. Wire Hermes to the STT runtime
```bash
cd ~/workspace/discord-voice-stt-enhance
HERMES_LOCAL_STT_SERVER_URL=http://WINDOWS_HOST_IP:8177 ./scripts/configure-hermes-local-stt.sh
```
Then copy the printed env and YAML snippet into `~/.hermes/.env` and `~/.hermes/config.yaml`.

If Hermes and the runtime are on the same Linux machine, keep the default `http://127.0.0.1:8177`.
If Hermes is in the Linux VM and the runtime is on Windows, use the Windows host IP reachable from the VM.

## 6. Restart Hermes gateway
```bash
cd ~/.hermes/hermes-agent
./venv/bin/python -m hermes_cli.main gateway run --replace
```

## 7. What to watch for in logs
- Hermes should log `provider=local_command` behavior instead of `faster_whisper: Processing audio ...` from the in-process path.
- The local STT runtime should log `Transcribed ... via large-v3-turbo`.
- If the runtime cannot load on CUDA, it will warn and fall back to CPU.
