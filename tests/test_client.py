import unittest

import httpx

from gitpulse.github import GitHubClient


class ClientTests(unittest.TestCase):
    def test_multiple_pages_and_fixed_origin(self) -> None:
        requested: list[str] = []

        def response(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            page = int(request.url.params["page"])
            rows = [{"id": index + 1, "login": f"user-{index}"} for index in range(100)] if page == 1 else []
            return httpx.Response(200, json=rows, headers={"Link": '<https://untrusted.invalid>; rel="next"'})

        with httpx.Client(transport=httpx.MockTransport(response)) as transport:
            result = GitHubClient("example", client=transport).people("followers")
        self.assertEqual(len(result), 100)
        self.assertEqual(len(requested), 2)
        self.assertTrue(all(url.startswith("https://api.github.com/users/example/") for url in requested))

    def test_rate_limit_error_redacted(self) -> None:
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(403, text="private-detail"))
        ) as transport:
            with self.assertRaises(RuntimeError) as caught:
                GitHubClient("example", client=transport).people("following")
        self.assertNotIn("private-detail", str(caught.exception))

    def test_redirect_is_not_followed(self) -> None:
        with httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(302, headers={"Location": "https://untrusted.invalid"})
            )
        ) as transport:
            with self.assertRaises(RuntimeError):
                GitHubClient("example", client=transport).people("followers")

    def test_invalid_payload_is_rejected(self) -> None:
        with httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=[{"id": True, "login": "valid"}]))
        ) as transport:
            with self.assertRaises(ValueError):
                GitHubClient("example", client=transport).people("followers")
