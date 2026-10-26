"""The viewer serves public fixtures only; restricted match assets are never requested."""

import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from viewer.__main__ import PUBLIC, Handler


class ViewerServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_static_modules_and_configuration_have_correct_types(self):
        for path, content_type in [("/", "text/html"), ("/app.mjs", "text/javascript"),
                                   ("/core.mjs", "text/javascript"), ("/worker.mjs", "text/javascript"),
                                   ("/styles.css", "text/css"), ("/config.json", "application/json")]:
            with self.subTest(path=path), urlopen(self.url + path) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), content_type)
                self.assertIn("media-src blob:", response.headers["Content-Security-Policy"])
                if path == "/config.json":
                    config = json.load(response)
                    self.assertEqual(config["frames"], 199319)
                    self.assertEqual(config["publicWindow"], [11185, 18684])

    def test_no_repository_browsing_upload_or_arbitrary_ground_truth_route(self):
        for path in ("/data/tactical/anything", "/../.git/config", "/evaluation/gt/private.csv", "/"):
            method = "POST" if path == "/" else "GET"
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                urlopen(Request(self.url + path, method=method))
            self.assertIn(error.exception.code, (404, 501))

    def test_only_published_ground_truth_is_served(self):
        with urlopen(self.url + "/public-ground-truth.csv") as response:
            self.assertEqual(response.headers.get_content_type(), "text/csv")
            self.assertEqual(response.read(), PUBLIC.read_bytes())
