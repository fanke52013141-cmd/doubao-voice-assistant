import io
import os
import tempfile
import unittest
from unittest.mock import patch

from server import app, socketio


PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
)


class PcToPhoneTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_patch = patch.dict(os.environ, {"APPDATA": self.temp_dir.name})
        self.env_patch.start()
        self.client = app.test_client()

    def tearDown(self):
        self.env_patch.stop()
        self.temp_dir.cleanup()

    def post_message(self):
        return self.client.post(
            "/api/pc/messages",
            data={
                "text": "电脑发送的测试文字",
                "files": (io.BytesIO(PNG_BYTES), "测试图片.png", "image/png"),
            },
            content_type="multipart/form-data",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )

    def test_publish_persists_lists_and_downloads_image(self):
        response = self.post_message()
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        message = response.get_json()["message"]
        self.assertEqual(message["text"], "电脑发送的测试文字")
        self.assertEqual(message["attachments"][0]["name"], "测试图片.png")

        listed = self.client.get("/api/messages?after=0&limit=100").get_json()["messages"]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], message["id"])

        attachment = message["attachments"][0]
        preview = self.client.get(attachment["view_url"])
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.mimetype, "image/png")
        self.assertEqual(preview.data, PNG_BYTES)
        preview.close()

        download = self.client.get(attachment["download_url"])
        self.assertEqual(download.status_code, 200)
        self.assertIn("attachment", download.headers.get("Content-Disposition", ""))
        download.close()

    def test_publish_emits_realtime_pc_message(self):
        phone = socketio.test_client(app)
        try:
            phone.get_received()
            response = self.post_message()
            self.assertEqual(response.status_code, 200)
            events = [item for item in phone.get_received() if item["name"] == "pc_message"]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["args"][0]["text"], "电脑发送的测试文字")
        finally:
            phone.disconnect()

    def test_publish_endpoint_rejects_lan_callers(self):
        response = self.client.post(
            "/api/pc/messages",
            data={"text": "not local"},
            environ_base={"REMOTE_ADDR": "192.168.1.50"},
        )
        self.assertEqual(response.status_code, 403)

    def test_common_document_can_be_transferred_and_forces_download(self):
        document_bytes = b"PK\x03\x04fake-docx-content"
        response = self.client.post(
            "/api/pc/messages",
            data={
                "text": "document",
                "files": (
                    io.BytesIO(document_bytes),
                    "report.docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            },
            content_type="multipart/form-data",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        attachment = response.get_json()["message"]["attachments"][0]
        downloaded = self.client.get(attachment["view_url"])
        self.assertEqual(downloaded.data, document_bytes)
        self.assertIn("attachment", downloaded.headers.get("Content-Disposition", ""))
        downloaded.close()

    def test_executable_attachment_is_rejected(self):
        response = self.client.post(
            "/api/pc/messages",
            data={"files": (io.BytesIO(b"MZ"), "unsafe.exe", "application/octet-stream")},
            content_type="multipart/form-data",
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        self.assertEqual(response.status_code, 415)

    def test_initial_sync_returns_latest_messages(self):
        for index in range(3):
            response = self.client.post(
                "/api/pc/messages",
                data={"text": f"message-{index}"},
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            )
            self.assertEqual(response.status_code, 200)
        messages = self.client.get("/api/messages?after=0&limit=2").get_json()["messages"]
        self.assertEqual([item["text"] for item in messages], ["message-1", "message-2"])

    def test_phone_page_contains_compact_download_and_share_controls(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertIn("socket.on('pc_message'", page)
        self.assertIn("download.textContent = '下载'", page)
        self.assertIn("share.textContent = '转发'", page)
        self.assertIn("navigator.share", page)
        self.assertNotIn("history-attachment-name", page)
        self.assertIn("history-file-name", page)
        self.assertIn("history-file-icon ${iconInfo.type}", page)
        self.assertIn("'xls', 'xlsx'", page)
        self.assertIn("fileDownload.textContent = '下载'", page)
        self.assertNotIn("下载视频", page)
        self.assertIn("-webkit-touch-callout: default", page)
        self.assertIn("serverRecordIds", page)


if __name__ == "__main__":
    unittest.main()
