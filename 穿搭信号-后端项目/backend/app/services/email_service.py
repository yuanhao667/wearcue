import hashlib
import hmac
import logging
import os
import secrets
import smtplib
import ssl
from email.message import EmailMessage


logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


def delivery_mode() -> str:
    configured = os.getenv("EMAIL_DELIVERY_MODE", "").strip().lower()
    if configured:
        return configured
    return "smtp" if os.getenv("APP_ENV") == "production" else "console"


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def code_digest(email: str, purpose: str, code: str) -> str:
    secret = os.getenv("EMAIL_CODE_SECRET", "").strip()
    if not secret:
        if os.getenv("APP_ENV") == "production":
            raise EmailDeliveryError("邮箱验证码密钥尚未配置")
        secret = "wearcue-local-development-only"
    message = f"{email.strip().casefold()}\n{purpose}\n{code}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def send_verification_email(email: str, code: str, purpose: str) -> None:
    mode = delivery_mode()
    if mode == "console":
        if os.getenv("APP_ENV") == "production":
            raise EmailDeliveryError("生产环境不允许使用控制台模拟发送验证码")
        logger.info("WearCue %s email code for %s: %s", purpose, email, code)
        return
    if mode != "smtp":
        raise EmailDeliveryError("EMAIL_DELIVERY_MODE 仅支持 smtp 或 console")

    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", username).strip()
    if not host or not sender:
        raise EmailDeliveryError("邮件发送服务尚未配置")

    subject = "WearCue 注册验证码" if purpose == "register" else "WearCue 密码重置验证码"
    action = "完成注册" if purpose == "register" else "重置密码"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = sender
    message["To"] = email
    message.set_content(
        f"你的 WearCue 验证码是：{code}\n\n验证码 10 分钟内有效，仅用于{action}。"
        "如果不是你本人操作，请忽略这封邮件。"
    )

    try:
        port = int(os.getenv("SMTP_PORT", "465"))
        use_ssl = os.getenv("SMTP_USE_SSL", "true").strip().lower() in {"1", "true", "yes"}
        use_starttls = os.getenv("SMTP_USE_STARTTLS", "false").strip().lower() in {"1", "true", "yes"}
        if not use_ssl and not use_starttls:
            raise EmailDeliveryError("邮件发送必须启用 TLS 加密")
        smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        tls_options = {"context": ssl.create_default_context()} if use_ssl else {}
        with smtp_class(host, port, timeout=10, **tls_options) as client:
            if use_starttls and not use_ssl:
                client.starttls(context=ssl.create_default_context())
            if username:
                client.login(username, password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        raise EmailDeliveryError("验证码邮件发送失败，请稍后重试") from exc
