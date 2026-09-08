import unittest
from decimal import Decimal

from fastapi import HTTPException

from app.ai.assistant import FallbackAssistant
from app.ai.complaint_analyzer import KeywordComplaintAnalyzer
from app.ai.waste_classifier import KeywordWasteClassifier
from app.models.collection import WasteCollection
from app.models.carbon import CarbonCredit
from app.models.municipality import Municipality, ServiceArea
from app.models.waste_report import WasteReport
from app.services.carbon_service import purchase_credit
from app.services.collection_service import update_collection_status
from app.services.municipality_service import build_municipality_summary
from app.services.route_optimizer import optimize_collections
from app.services.waste_classifier import WasteClassifier


class WasteClassifierTests(unittest.TestCase):
    def test_supported_keyword_returns_confident_prediction(self):
        prediction = WasteClassifier().classify_with_confidence(
            "broken glass bottle"
        )

        self.assertEqual(prediction, ("glass", 0.9))

    def test_unknown_description_returns_low_confidence_other(self):
        prediction = WasteClassifier().classify_with_confidence(
            "unidentified debris"
        )

        self.assertEqual(prediction, ("other", 0.2))

    def test_prediction_contains_model_traceability(self):
        prediction = KeywordWasteClassifier().predict("paper carton")

        self.assertEqual(prediction.label, "paper")
        self.assertEqual(prediction.model_name, "keyword-waste-classifier")
        self.assertEqual(prediction.model_version, "1.0.0")
        self.assertGreaterEqual(prediction.inference_time_ms, 0)


class AIRecommendationTests(unittest.TestCase):
    def test_complaint_analysis_recommends_hazard_priority(self):
        analysis = KeywordComplaintAnalyzer().analyze(
            "Chemical spill",
            "Hazardous chemical waste reported near the road",
        )

        self.assertEqual(analysis.category, "hazardous_waste")
        self.assertEqual(analysis.priority, "critical")
        self.assertIn("chemical", analysis.keywords)

    def test_assistant_falls_back_to_guidance(self):
        response = FallbackAssistant().answer(
            "How do I recycle e-waste?",
            {"report_count": 0, "role_id": 5},
        )

        self.assertTrue(response.is_fallback)
        self.assertIn("electronics", response.answer.lower())


class CollectionServiceTests(unittest.TestCase):
    def test_collection_moves_to_collected(self):
        collection = WasteCollection(status="assigned")

        update_collection_status(collection, "in_progress")
        update_collection_status(collection, "collected")

        self.assertEqual(collection.status, "collected")
        self.assertIsNotNone(collection.collected_at)

    def test_collected_collection_cannot_be_reopened(self):
        collection = WasteCollection(status="collected")

        with self.assertRaises(ValueError):
            update_collection_status(collection, "in_progress")


class RouteOptimizerTests(unittest.TestCase):
    def test_nearest_neighbor_orders_coordinate_stops(self):
        first = WasteCollection(
            report=WasteReport(latitude=20.01, longitude=77.0)
        )
        second = WasteCollection(
            report=WasteReport(latitude=20.1, longitude=77.0)
        )

        plan = optimize_collections(
            [second, first],
            start_latitude=20.0,
            start_longitude=77.0,
        )

        self.assertEqual(plan.stops[0].collection, first)
        self.assertEqual(plan.stops[1].collection, second)

    def test_missing_coordinates_are_not_routed(self):
        collection = WasteCollection(
            report=WasteReport(location="unknown")
        )

        plan = optimize_collections([collection])

        self.assertEqual(plan.stops, [])
        self.assertEqual(plan.total_distance_km, 0)


class CarbonServiceTests(unittest.TestCase):
    def _session_for(self, credit):
        class Query:
            def filter(self, *args, **kwargs):
                return self

            def with_for_update(self):
                return self

            def first(self):
                return credit

        class Session:
            def query(self, model):
                return Query()

            def add_all(self, objects):
                self.objects = objects

        return Session()

    def test_purchase_decrements_available_credit(self):
        credit = CarbonCredit(
            owner_id=2,
            amount=Decimal("10.000"),
            status="available",
        )
        session = self._session_for(credit)

        transaction = purchase_credit(session, 3, 1, Decimal("4.500"))

        self.assertEqual(credit.amount, Decimal("5.500"))
        self.assertEqual(transaction.amount, Decimal("4.500"))
        self.assertEqual(transaction.seller_id, 2)

    def test_purchase_rejects_insufficient_credit(self):
        credit = CarbonCredit(
            owner_id=2,
            amount=Decimal("1.000"),
            status="available",
        )
        session = self._session_for(credit)

        with self.assertRaises(HTTPException):
            purchase_credit(session, 3, 1, Decimal("2.000"))


class MunicipalityIntegrationTests(unittest.TestCase):
    def test_municipality_summary_counts_active_service_areas(self):
        municipality = Municipality(
            name="Nairobi County",
            code="NBO",
            region="Central",
        )
        municipality.service_areas = [
            ServiceArea(name="West Ward", code="WST", status="active"),
            ServiceArea(name="East Ward", code="EST", status="inactive"),
        ]

        summary = build_municipality_summary(municipality)

        self.assertEqual(summary["code"], "NBO")
        self.assertEqual(summary["total_service_areas"], 2)
        self.assertEqual(summary["active_service_areas"], 1)
        self.assertEqual(summary["region"], "Central")


if __name__ == "__main__":
    unittest.main()
