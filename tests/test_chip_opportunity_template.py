import unittest
from pathlib import Path

from flask import Flask, render_template


class ChipOpportunityTemplateTests(unittest.TestCase):

    def test_coordinated_schedule_items_render_as_list(self):
        template_dir = (
            Path(__file__).resolve().parent.parent
            / "templates"
        )
        app = Flask(
            __name__,
            template_folder=str(template_dir),
        )

        opportunity = {
            "gameweek": 6,
            "rows": [],
            "curves": [],
            "schedule": {
                "items": [
                    {
                        "short": "TC",
                        "status": "unscheduled",
                        "gameweek": None,
                        "value": None,
                        "model_confidence": None,
                        "fixture_certainty": None,
                        "reason": (
                            "No remaining window currently "
                            "clears the evidence threshold."
                        ),
                    }
                ],
                "note": (
                    "Only evidence-backed CANDIDATE "
                    "windows can be scheduled."
                ),
            },
            "note": "Opportunity snapshot.",
        }

        with app.app_context():
            html = render_template(
                "chips_opportunity.html",
                opportunity=opportunity,
            )

        self.assertIn(
            "Coordinated chip plan",
            html,
        )
        self.assertIn(
            "UNSCHEDULED",
            html,
        )
        self.assertIn(
            "No remaining window currently",
            html,
        )


if __name__ == "__main__":
    unittest.main()
