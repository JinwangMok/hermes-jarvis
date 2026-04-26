from __future__ import annotations

from jinwang_jarvis.cli import build_parser


def test_cli_exposes_news_center_and_podcast_commands() -> None:
    parser = build_parser()

    args = parser.parse_args([
        "generate-news-center",
        "--taxonomy",
        "config/personal-radar/naver-news-taxonomy.yaml",
        "--output-dir",
        "data/news-center",
    ])
    assert args.command == "generate-news-center"
    assert args.per_source_limit == 5

    append_args = parser.parse_args([
        "append-news-center-to-daily-report",
        "--daily-report",
        "daily.md",
        "--news-markdown",
        "news.md",
    ])
    assert append_args.command == "append-news-center-to-daily-report"

    podcast_args = parser.parse_args([
        "generate-podcast-script",
        "--daily-report",
        "daily.md",
        "--output-path",
        "podcast.md",
    ])
    assert podcast_args.command == "generate-podcast-script"
