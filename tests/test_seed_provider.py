import json
from pathlib import Path

from paper_writer_agent.models import PageArtifact
from paper_writer_agent.providers import Seed2ProProvider


def test_seed_provider_sends_multimodal_responses_request(tmp_path):
    image_path = tmp_path / "page.png"
    text_path = tmp_path / "page.txt"
    image_path.write_bytes(b"png-bytes")
    text_path.write_text("Abstract\nThis is raw page text.", encoding="utf-8")
    captured = {}

    def fake_http_post(url, headers, payload):
        captured["url"] = url
        captured["headers"] = headers
        captured["payload"] = payload
        return {
            "output": [
                {
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps(
                                {
                                    "page": 1,
                                    "sections": [
                                        {
                                            "name": "Abstract",
                                            "paragraphs": ["This is the abstract."],
                                            "source_pages": [1],
                                        }
                                    ],
                                    "excluded_content": [],
                                }
                            ),
                        }
                    ]
                }
            ]
        }

    provider = Seed2ProProvider(api_key="secret-api-key", http_post=fake_http_post)

    result = provider.extract_page(
        PageArtifact(
            page_number=1,
            image_path=image_path,
            text_path=text_path,
            raw_text="Abstract\nThis is raw page text.",
        ),
        target_sections=("Title", "Abstract"),
    )

    assert result["sections"][0]["name"] == "Abstract"
    assert captured["url"] == "https://ark.cn-beijing.volces.com/api/v3/responses"
    assert captured["headers"]["Authorization"] == "Bearer secret-api-key"
    assert captured["payload"]["model"] == "doubao-seed-2-0-pro-260215"
    content = captured["payload"]["input"][0]["content"]
    assert content[0]["type"] == "input_text"
    assert "Use the raw PDF text as the primary source" in content[0]["text"]
    assert content[1]["type"] == "input_image"
    assert content[1]["image_url"].startswith("data:image/png;base64,")
