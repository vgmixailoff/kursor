"""Theme patch adds Dzen RSS enclosure from featured image."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from excalibur_blog_theme_contract_deploy import patch_functions  # noqa: E402


STUB = """<?php
function custom_theme_add_faq_to_single( $content ) {
	if ( is_single() && 'post' === get_post_type() ) {
		return $content;
	}
	return $content;
}
add_filter( 'the_content', 'custom_theme_add_faq_to_single', 99 );
"""


class ThemeRssEnclosureTest(unittest.TestCase):
    def test_patch_adds_enclosure_hook(self) -> None:
        once = patch_functions(STUB)
        self.assertIn("function excalibur_blog_rss_enclosure()", once)
        self.assertIn("add_action( 'rss2_item', 'excalibur_blog_rss_enclosure', 11 )", once)
        twice = patch_functions(once)
        self.assertEqual(once.count("function excalibur_blog_rss_enclosure()"), 1)
        self.assertEqual(twice, once)


if __name__ == "__main__":
    unittest.main()
