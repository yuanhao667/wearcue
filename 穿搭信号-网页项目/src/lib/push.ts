function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(normalized);
  const output = new Uint8Array(raw.length);
  for (let index = 0; index < raw.length; index += 1) {
    output[index] = raw.charCodeAt(index);
  }
  return output;
}

export type PushStatus = "enabled" | "unsupported" | "denied" | "provider_missing" | "error";

export async function ensurePushSubscription(): Promise<PushStatus> {
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    return "unsupported";
  }
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") return "denied";

    const registration = await navigator.serviceWorker.register("/sw.js");
    const keyResponse = await fetch("/api/backend/notifications/public-key");
    if (!keyResponse.ok) return "error";
    const payload = (await keyResponse.json()) as { configured?: boolean; public_key?: string };
    if (!payload.configured || !payload.public_key) return "provider_missing";

    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(payload.public_key) as BufferSource,
      });
    }

    const json = subscription.toJSON();
    const saveResponse = await fetch("/api/backend/notifications/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        endpoint: subscription.endpoint,
        p256dh: json.keys?.p256dh,
        auth: json.keys?.auth,
      }),
    });
    if (!saveResponse.ok) return "error";
    return "enabled";
  } catch {
    return "error";
  }
}
