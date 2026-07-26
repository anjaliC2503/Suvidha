import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from pinecone_api import app


class PineconeSchemeSearchEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_search_requires_valid_tool_key_and_returns_pinecone_results(self):
        with patch.dict(os.environ, {"SUVIDHA_TOOL_API_KEY": "secret"}, clear=True), patch(
            "pinecone_api.search_pinecone_schemes",
            return_value=[{"slug": "fp", "chunk_text": "Farmer support", "score": 0.9}],
        ) as search:
            unauthorized = self.client.post("/v1/pinecone/schemes/search", json={"query": "farmer support"})
            response = self.client.post(
                "/v1/pinecone/schemes/search",
                headers={"Authorization": "Bearer secret"},
                json={"query": "farmer support", "top_k": 1},
            )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["slug"], "fp")
        search.assert_called_once_with("farmer support", 1)


if __name__ == "__main__":
    unittest.main()
