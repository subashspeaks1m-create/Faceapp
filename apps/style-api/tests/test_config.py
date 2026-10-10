import unittest

from styleapi.config import ConfigError, load_settings

BASE = {"APP_ENV": "production", "ALLOWED_ORIGINS": "https://a.example", "RATE_LIMIT_BACKEND": "upstash"}


class ConfigTest(unittest.TestCase):
    def test_defaults(self) -> None:
        s = load_settings(BASE)
        self.assertEqual(s.openai_model, "gpt-image-2")
        self.assertEqual(s.openai_quality, "medium")
        self.assertFalse(s.provider_configured)
        self.assertEqual(s.allowed_origins, ("https://a.example",))

    def test_production_refuses_unsafe_settings(self) -> None:
        for env in (
            {**BASE, "ALLOWED_ORIGINS": "*"},
            {**BASE, "ALLOWED_ORIGINS": "http://a.example"},
            {**BASE, "RATE_LIMIT_BACKEND": "memory"},
            {**BASE, "RATE_LIMIT_BACKEND": "disabled"},
            {**BASE, "OPENAI_IMAGE_MODEL": "dall-e-2"},
            {**BASE, "OPENAI_BASE_URL": "http://proxy"},
            {**BASE, "APP_ENV": "staging"},
            {**BASE, "MAX_UPLOAD_BYTES": "9000000"},
        ):
            with self.assertRaises(ConfigError, msg=str(env)):
                load_settings(env)

    def test_secrets_not_in_repr(self) -> None:
        s = load_settings({**BASE, "OPENAI_API_KEY": "sk-abc-secret", "UPSTASH_REDIS_REST_TOKEN": "tok-secret", "RATE_LIMIT_SALT": "salt-secret"})
        self.assertTrue(s.provider_configured)
        for secret in ("sk-abc-secret", "tok-secret", "salt-secret"):
            self.assertNotIn(secret, repr(s))
            self.assertNotIn(secret, str(s))

    def test_upstash_kv_aliases(self) -> None:
        s = load_settings({**BASE, "KV_REST_API_URL": "https://kv.example/", "KV_REST_API_TOKEN": "t"})
        self.assertEqual(s.upstash_url, "https://kv.example")
        assert s.upstash_token is not None
        self.assertEqual(s.upstash_token.get_secret_value(), "t")

    def test_provider_selection(self) -> None:
        self.assertEqual(load_settings(BASE).image_provider, "openai")
        self.assertEqual(load_settings({**BASE, "OPENAI_API_KEY": "a", "GEMINI_API_KEY": "b"}).image_provider, "openai")
        only_gemini = load_settings({**BASE, "GEMINI_API_KEY": "b", "GEMINI_PAID_TIER": "true"})
        self.assertEqual(only_gemini.image_provider, "gemini")
        self.assertTrue(only_gemini.provider_configured)
        self.assertEqual(only_gemini.active_model, "gemini-3.1-flash-image")
        explicit = load_settings({**BASE, "IMAGE_PROVIDER": "gemini", "OPENAI_API_KEY": "a", "GEMINI_PAID_TIER": "true"})
        self.assertEqual(explicit.image_provider, "gemini")
        self.assertFalse(explicit.provider_configured)
        with self.assertRaises(ConfigError):
            load_settings({**BASE, "IMAGE_PROVIDER": "digen"})
        with self.assertRaises(ConfigError):
            load_settings({**BASE, "GEMINI_IMAGE_MODEL": "../evil"})

    def test_gemini_production_requires_paid_tier(self) -> None:
        with self.assertRaises(ConfigError):
            load_settings({**BASE, "GEMINI_API_KEY": "b"})
        dev = load_settings({"APP_ENV": "development", "RATE_LIMIT_BACKEND": "memory", "GEMINI_API_KEY": "b"})
        self.assertEqual(dev.image_provider, "gemini")

    def test_gemini_key_not_in_repr(self) -> None:
        s = load_settings({**BASE, "GEMINI_API_KEY": "gem-secret", "GEMINI_PAID_TIER": "true"})
        self.assertNotIn("gem-secret", repr(s))

    def test_development_allows_http_origin(self) -> None:
        s = load_settings({"APP_ENV": "development", "ALLOWED_ORIGINS": "http://localhost:8081", "RATE_LIMIT_BACKEND": "memory"})
        self.assertEqual(s.allowed_origins, ("http://localhost:8081",))


if __name__ == "__main__":
    unittest.main()
