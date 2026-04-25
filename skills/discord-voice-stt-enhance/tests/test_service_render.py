from service.render import render_user_service


def test_render_user_service_includes_repo_python_and_port():
    rendered = render_user_service(
        python_bin="/opt/stt/.venv/bin/python",
        server_script="/workspace/discord-voice-stt-enhance/runtime/server.py",
        host="127.0.0.1",
        port=8177,
        working_directory="/workspace/discord-voice-stt-enhance",
    )

    assert "ExecStart=/opt/stt/.venv/bin/python /workspace/discord-voice-stt-enhance/runtime/server.py --host 127.0.0.1 --port 8177" in rendered
    assert "WorkingDirectory=/workspace/discord-voice-stt-enhance" in rendered
    assert "Restart=on-failure" in rendered
