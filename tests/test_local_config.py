import os
import stat
import tempfile
import unittest
from pathlib import Path

from local_config import (
    LocalConfigError,
    get_config_status,
    get_entry_id,
    get_refresh_token,
    save_local_config,
    save_refresh_token,
)


class LocalConfigTests(unittest.TestCase):

    def setUp(self):
        self._old_entry = os.environ.pop(
            "FPL_ENTRY_ID",
            None,
        )
        self._old_token = os.environ.pop(
            "FPL_REFRESH_TOKEN",
            None,
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.env_file = (
            Path(self.temp_dir.name)
            / ".env"
        )

    def tearDown(self):
        os.environ.pop(
            "FPL_ENTRY_ID",
            None,
        )
        os.environ.pop(
            "FPL_REFRESH_TOKEN",
            None,
        )

        if self._old_entry is not None:
            os.environ["FPL_ENTRY_ID"] = (
                self._old_entry
            )

        if self._old_token is not None:
            os.environ["FPL_REFRESH_TOKEN"] = (
                self._old_token
            )

        self.temp_dir.cleanup()

    def test_new_installation_is_not_configured(self):
        status = get_config_status(
            self.env_file
        )

        self.assertFalse(
            status["configured"]
        )
        self.assertIsNone(
            status["entry_id"]
        )
        self.assertFalse(
            status["refresh_token_configured"]
        )

    def test_save_local_config_creates_private_env_file(self):
        status = save_local_config(
            1234567,
            "refresh-token-value",
            env_file=self.env_file,
        )

        self.assertTrue(
            status["configured"]
        )
        self.assertEqual(
            get_entry_id(self.env_file),
            1234567,
        )
        self.assertEqual(
            get_refresh_token(self.env_file),
            "refresh-token-value",
        )

        mode = stat.S_IMODE(
            self.env_file.stat().st_mode
        )
        self.assertEqual(
            mode,
            0o600,
        )

    def test_existing_token_is_preserved_when_entry_id_is_added(self):
        self.env_file.write_text(
            "FPL_REFRESH_TOKEN=existing-token\n",
            encoding="utf-8",
        )

        save_local_config(
            7654321,
            env_file=self.env_file,
        )

        self.assertEqual(
            get_entry_id(self.env_file),
            7654321,
        )
        self.assertEqual(
            get_refresh_token(self.env_file),
            "existing-token",
        )

    def test_refresh_token_can_be_rotated_without_losing_entry_id(self):
        save_local_config(
            1234567,
            "first-token",
            env_file=self.env_file,
        )

        save_refresh_token(
            "second-token",
            env_file=self.env_file,
        )

        self.assertEqual(
            get_entry_id(self.env_file),
            1234567,
        )
        self.assertEqual(
            get_refresh_token(self.env_file),
            "second-token",
        )

    def test_token_is_required_on_first_setup(self):
        with self.assertRaises(
            LocalConfigError
        ):
            save_local_config(
                1234567,
                env_file=self.env_file,
            )

    def test_multiline_token_is_rejected(self):
        with self.assertRaises(
            LocalConfigError
        ):
            save_local_config(
                1234567,
                "bad\ntoken",
                env_file=self.env_file,
            )


if __name__ == "__main__":
    unittest.main()
