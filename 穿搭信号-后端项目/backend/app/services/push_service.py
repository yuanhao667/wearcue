import json
import os
from typing import Any, Dict


class PushService:
    @property
    def configured(self) -> bool:
        return bool(
            os.getenv("VAPID_PRIVATE_KEY")
            and os.getenv("VAPID_PUBLIC_KEY")
            and os.getenv("VAPID_SUBJECT")
        )

    @property
    def public_key(self) -> str:
        return os.getenv("VAPID_PUBLIC_KEY", "")

    def send(self, subscription: Dict[str, Any], message: str) -> None:
        if not self.configured:
            raise RuntimeError("Web Push Provider 尚未配置")
        from pywebpush import webpush

        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": {"p256dh": subscription["p256dh"], "auth": subscription["auth"]},
            },
            data=json.dumps({"title": "穿搭信号", "body": message}, ensure_ascii=False),
            vapid_private_key=os.environ["VAPID_PRIVATE_KEY"],
            vapid_claims={"sub": os.environ["VAPID_SUBJECT"]},
        )
