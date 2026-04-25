def render_user_service(
    *,
    python_bin: str,
    server_script: str,
    host: str,
    port: int,
    working_directory: str,
) -> str:
    return f"""[Unit]
Description=Hermes Local STT Runtime
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory={working_directory}
ExecStart={python_bin} {server_script} --host {host} --port {port}
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""
