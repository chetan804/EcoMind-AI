import unittest
from decimal import Decimal

from fastapi import HTTPException

from app.models.collection import WasteCollection
from app.models.carbon import CarbonCredit
from app.models.waste_report import WasteReport
from app.services.carbon_service import purchase_credit
from app.services.collection_service import update_collection_status
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


if __name__ == "__main__":
    unittest.main()
