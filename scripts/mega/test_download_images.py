import unittest
from download_images import valid_image


class ImageValidationTests(unittest.TestCase):
    def test_image_magic_and_mime_must_agree(self):
        self.assertTrue(valid_image(b'\x89PNG\r\n\x1a\ncontent', 'image/png'))
        self.assertTrue(valid_image(b'\xff\xd8\xffcontent', 'image/jpeg'))
        self.assertTrue(valid_image(b'RIFF1234WEBPcontent', 'image/webp'))
        self.assertFalse(valid_image(b'<html>not an image</html>', 'image/png'))
        self.assertFalse(valid_image(b'\x89PNG\r\n\x1a\n', 'image/jpeg'))


if __name__ == '__main__':
    unittest.main()
