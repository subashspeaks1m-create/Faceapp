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

    def test_development_allows_http_origin(self) -> None:
        s = load_settings({"APP_ENV": "development", "ALLOWED_ORIGINS": "http://localhost:8081", "RATE_LIMIT_BACKEND": "memory"})
        self.assertEqual(s.allowed_origins, ("http://localhost:8081",))


if __name__ == "__main__":
    unittest.main()
