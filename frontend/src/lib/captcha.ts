// Optional reCAPTCHA v3: only active when VITE_RECAPTCHA_SITE_KEY is set at build time.
const SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY as string | undefined;

type Grecaptcha = {
  ready: (cb: () => void) => void;
  execute: (key: string, opts: { action: string }) => Promise<string>;
};

let loading: Promise<Grecaptcha> | null = null;

function load(): Promise<Grecaptcha> {
  loading ??= new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://www.google.com/recaptcha/api.js?render=${SITE_KEY}`;
    script.async = true;
    script.onload = () => {
      const g = (window as unknown as { grecaptcha: Grecaptcha }).grecaptcha;
      g.ready(() => resolve(g));
    };
    script.onerror = () => reject(new Error("captcha failed to load"));
    document.head.appendChild(script);
  });
  return loading;
}

export async function captchaToken(action: string): Promise<string | null> {
  if (!SITE_KEY) return null;
  const g = await load();
  return g.execute(SITE_KEY, { action });
}
