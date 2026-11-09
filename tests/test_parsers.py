import unittest

from scripts.parsers.fandom_parser import parse_rewards_from_text, parse_section_rows
from scripts.parsers.official_banners_parser import (
    GS_CHAR_RE,
    HSR_DATE_RANGE_RE,
    HSR_FIVE_RU_RE,
    HSR_FOUR_RU_BLOCK_RE,
    HSR_NAME_RU_RE,
    make_banner,
    normalize_name,
    parse_date,
    parse_month_day,
    resolve_item,
)
from scripts.sync.sync_promocodes import import_scraped_codes, is_placeholder_reward


class FandomRewardParsingTests(unittest.TestCase):
    def test_keep_up_with_mitya_rewards(self):
        row = (
            '{{Code Row|KeepUpWithMitya|G|'
            'Guide to Charity*3;"Energy-Replenishing Meal"*3;Kristallfold*3|'
            '2026-11-04|unknown}}'
        )
        desc_ru, desc_en, reward_types = parse_rewards_from_text(row, 0)
        self.assertIn("Указания о «Милосердии»", desc_ru)
        self.assertIn("Кристаллический гриб-зонтик", desc_ru)
        self.assertIn("Энергетический обед", desc_ru)
        self.assertIn("Guide to Charity", desc_en)
        self.assertNotIn("PRIMOGEM", reward_types)

    def test_unknown_rewards_do_not_fall_back_to_primary_currency(self):
        desc_ru, desc_en, reward_types = parse_rewards_from_text("Unknown Item*3", 0)
        self.assertIn("Unknown Item", desc_ru)
        self.assertIn("Unknown Item", desc_en)
        self.assertNotIn("PRIMOGEM", reward_types)
        self.assertIn("ITEM", reward_types)

    def test_unknown_expiry_is_not_synthesized(self):
        row = "{{Code Row|TESTCODE123|G|Primogem*60|2026-11-01|unknown}}"
        items = parse_section_rows(row, 0, is_section_expired=False, seen_codes=set())
        self.assertEqual(len(items), 1)
        self.assertIsNone(items[0]["expires_at"])
        self.assertEqual(items[0]["expiry_confidence"], "unknown")

    def test_bare_currency_is_a_placeholder(self):
        self.assertTrue(is_placeholder_reward("Камни Истока"))
        self.assertTrue(is_placeholder_reward("Внутриигровые награды"))
        self.assertFalse(is_placeholder_reward("60 Камней Истока"))
        self.assertFalse(is_placeholder_reward("Указания о «Милосердии» x3"))


class CodeMergeTests(unittest.TestCase):
    def test_existing_placeholder_is_repaired(self):
        data = {
            "schema_version": 1,
            "codes": [{
                "id": "scraped_0_keepupwithmitya",
                "game_type": 0,
                "code": "KEEPUPWITHMITYA",
                "rewards_description_ru": "Камни Истока",
                "rewards_description_en": "Primogems",
                "reward_types": ["PRIMOGEM"],
                "status": "ACTIVE",
                "expires_at": "2026-12-09T12:00:00Z",
                "created_at": "2026-11-04T12:00:00Z",
                "is_stream": False,
                "is_active": True,
            }],
        }
        scraped = [{
            "id": "scraped_0_keepupwithmitya",
            "game_type": 0,
            "code": "KEEPUPWITHMITYA",
            "rewards_description_ru": "Указания о «Милосердии» x3",
            "rewards_description_en": "Guide to Charity x3",
            "reward_types": ["TALENT_BOOK"],
            "status": "ACTIVE",
            "expires_at": "2026-11-15T16:00:00Z",
            "created_at": "2026-11-04T04:00:00Z",
            "is_stream": False,
            "is_active": True,
            "verification_status": "verified",
            "source_url": "https://genshin.hoyoverse.com/ru/news/detail/167189",
        }]
        import_scraped_codes(data, scraped)
        entry = data["codes"][0]
        self.assertEqual(entry["rewards_description_ru"], "Указания о «Милосердии» x3")
        self.assertEqual(entry["reward_types"], ["TALENT_BOOK"])


class OfficialParserHelpersTests(unittest.TestCase):
    def test_short_official_name_resolves_from_catalog(self):
        lookup = {2: {normalize_name("Severian Lowell"): {"name_en": "Severian Lowell"}}}
        self.assertIsNotNone(resolve_item("Severian", lookup[2]))

    def test_genshin_character_regex(self):
        content = (
            '"Rules Set at Naught" Mitya (Electro) '
            '"Fort Fulguration" Valeriy (Electro) '
            '"Lens of Verity" Charlotte (Cryo) '
            '"Thorny Benevolence" Rosaria (Cryo)'
        )
        names = GS_CHAR_RE.findall(content)
        self.assertEqual([entry[1] for entry in names], ["Mitya", "Valeriy", "Charlotte", "Rosaria"])

    def test_date_helpers(self):
        self.assertEqual(parse_date("2026/11/24 17:59"), "2026-11-24")
        self.assertEqual(parse_month_day("OCT", "22", 2026), "2026-10-22")
        self.assertEqual(parse_month_day("DEC", "24", 2026), "2026-12-24")

    def test_hsr_ru_banner_text(self):
        content = (
            "Временно повышается шанс получения эксклюзивного персонажа 5★ Жемчуг (Радость: Ледяной) "
            "и следующих персонажей 4★: Цинцюэ (Эрудиция: Квантовый), Сюэи (Разрушение: Квантовый), "
            "Миша (Разрушение: Ледяной) и Световых конусов 4★: «Беседа после операции» (Изобилие). "
            "Время Прыжка: с выхода версии 4.6 2026/09/28 до 2026/11/10 15:00 (время сервера). "
            "Возвращение эксклюзивного персонажа 5★ Мортенакс Блэйд (Небытие: Огненный). "
            "Время Прыжка: 2026/10/21 12:00 - 2026/11/10 15:00 (время сервера)."
        )
        self.assertEqual(
            [name.strip() for name in HSR_FIVE_RU_RE.findall(content)],
            ["Жемчуг", "Мортенакс Блэйд"],
        )
        block = HSR_FOUR_RU_BLOCK_RE.search(content)
        self.assertIsNotNone(block)
        self.assertEqual(
            [name.strip() for name in HSR_NAME_RU_RE.findall(block.group(1))],
            ["Цинцюэ", "Сюэи", "Миша"],
        )
        self.assertEqual(HSR_DATE_RANGE_RE.findall(content)[-1], ("2026/10/21", "2026/11/10"))

    def test_make_banner_uses_catalog_names(self):
        lookup = {
            0: {
                normalize_name("Mitya"): {"name_ru": "Митя", "name_en": "Mitya"},
                normalize_name("Valeriy"): {"name_ru": "Валерий", "name_en": "Valeriy"},
            }
        }
        banner = make_banner(
            0, "7.2", 1, "2026-11-04", "2026-11-24",
            ["Mitya"], ["Valeriy"], "https://genshin.hoyoverse.com/en/news", "1", lookup,
        )
        self.assertEqual(banner["id"], "genshin_7_2_1")
        self.assertEqual(banner["featured_five_stars_ru"], ["Митя"])
        self.assertEqual(banner["verification_status"], "verified")


if __name__ == "__main__":
    unittest.main()
