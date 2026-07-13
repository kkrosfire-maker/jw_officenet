import base64
from abc import ABC, abstractmethod
from pathlib import Path

import anthropic


class CreditExhaustedError(Exception):
    """Anthropic API 크레딧이 소진됐을 때 발생."""

_PROMPT = (
    "이 이미지에서 제약사(회사) 이름을 추출해줘. "
    "'제약사', '제약회사' 필드에 있는 값이야. "
    "'주식회사'는 '(주)'로 바꿔줘. "
    "제약사가 정확히 하나이면 회사명만 답해. "
    "제약사가 두 개 이상 보이면 '변환불가'라고만 답해. "
    "회사명 또는 '변환불가' 외에 다른 말은 절대 하지 마."
)


class CompanyExtractor(ABC):
    @abstractmethod
    def extract(self, image_path: Path) -> str: ...


class AnthropicExtractor(CompanyExtractor):
    def __init__(self, api_key: str):
        self._client = anthropic.Anthropic(api_key=api_key)

    def extract(self, image_path: Path) -> str:
        with open(image_path, "rb") as f:
            data = base64.standard_b64encode(f.read()).decode()

        ext = image_path.suffix.lower()
        media = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"

        try:
            resp = self._client.messages.create(
                model="claude-opus-4-8",
                max_tokens=50,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image",
                         "source": {"type": "base64", "media_type": media, "data": data}},
                        {"type": "text", "text": _PROMPT},
                    ],
                }],
            )
        except (anthropic.BadRequestError, anthropic.PermissionDeniedError) as e:
            body = e.body if isinstance(e.body, dict) else {}
            err_obj = body.get("error", {})
            msg = err_obj.get("message", "")
            etype = err_obj.get("type", "")
            if "credit" in msg.lower() or etype == "billing_error":
                raise CreditExhaustedError(
                    "API 크레딧이 소진됐습니다. console.anthropic.com → Billing에서 충전해주세요."
                ) from e
            raise
        return resp.content[0].text.strip()
