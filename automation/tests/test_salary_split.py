"""Owner, 14 Nov 2026: when SEEK's salary options split the band, choose the option that starts at $70,000."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import answers  # noqa: E402
import common  # noqa: E402

Q = "What's your expected annual base salary?"
SPLIT = ['$60,000 - $70,000', '$70,000 - $80,000', '$80,000 - $90,000', '$90,000+']


def gate(options, pay):
    return answers.answer(Q, options, common.FACTS, pay=pay)


class SalarySplit(unittest.TestCase):
    def test_no_pay_stated_and_the_band_is_split_picks_the_option_starting_at_70000(self):
        r = gate(SPLIT, 'not stated')
        self.assertEqual((r['status'], r['answer']), ('answered', '$70,000 - $80,000'), r)

    def test_a_single_option_holding_the_whole_band_still_wins(self):
        r = gate(['$50,000 - $64,999', '$65,000 - $75,000', '$75,001 - $90,000'], 'not stated')
        self.assertEqual(r['answer'], '$65,000 - $75,000', r)

    def test_advertised_lower_end_on_a_boundary_picks_the_option_starting_there(self):
        r = gate(SPLIT, '$70,000 - $85,000 per year')
        self.assertEqual((r['status'], r['answer']), ('answered', '$70,000 - $80,000'), r)

    def test_no_option_starts_at_70000_stays_unanswered(self):
        r = gate(['$55,000 - $72,000', '$68,000 - $90,000'], 'not stated')
        self.assertEqual(r['status'], 'unanswered', r)

    def test_pay_unknown_still_unanswered(self):
        self.assertEqual(gate(SPLIT, None)['status'], 'unanswered')


if __name__ == '__main__':
    unittest.main()
