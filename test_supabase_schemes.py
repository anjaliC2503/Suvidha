from io import BytesIO
import os
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import supabase_schemes


class SupabaseSchemeTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "OPENAI_API_KEY": "test-openai-key",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SERVICE_ROLE_KEY": "test-supabase-key",
        }

    def test_search_passes_cosine_rpc_parameters(self):
        with patch.dict(os.environ, self.environment, clear=True), \
             patch("supabase_schemes.openai_embeddings", return_value=[[0.1] * 1536]), \
             patch("supabase_schemes.request_json", return_value=[]) as request_json:
            self.assertEqual(supabase_schemes.search_records("farmer support", "Rajasthan", 3), [])

        _, kwargs = request_json.call_args
        self.assertEqual(kwargs["payload"]["match_count"], 12)
        self.assertEqual(kwargs["payload"]["requested_state"], "Rajasthan")
        self.assertEqual(len(kwargs["payload"]["query_embedding"]), 1536)

    def test_upsert_attaches_openai_embeddings(self):
        records = [{"id": "fp:benefits-0", "chunk_text": "support", "slug": "fp"}]
        with patch.dict(os.environ, self.environment, clear=True), \
             patch("supabase_schemes.openai_embeddings", return_value=[[0.2] * 1536]), \
             patch("supabase_schemes.request_json") as request_json:
            supabase_schemes.upsert_records(records)

        self.assertEqual(len(records[0]["embedding"]), 1536)
        self.assertIn("scheme_chunks?on_conflict=id", request_json.call_args.args[0])

    def test_transient_http_error_retries(self):
        error = HTTPError("https://example.test", 503, "Unavailable", None, BytesIO(b"retry"))
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"{}"
        with patch("supabase_schemes.urllib.request.urlopen", side_effect=[error, response]), \
             patch("supabase_schemes.time.sleep") as sleep:
            self.assertEqual(supabase_schemes.request_json("https://example.test"), {})
        sleep.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
