import unittest
from decimal import Decimal
from unittest.mock import patch

from fastapi import HTTPException

from app.ai.assistant import FallbackAssistant
from app.ai.complaint_analyzer import KeywordComplaintAnalyzer
from app.ai.waste_classifier import KeywordWasteClassifier
from app.core.roles import RoleID, RoleName
from app.core.security import require_role, require_roles
from app.integrations.routing.osrm_adapter import OSRMAdapter
from app.integrations.routing.base import RouteLeg
from app.models.collection import WasteCollection
from app.models.carbon import CarbonCredit
from app.models.municipality import Municipality, ServiceArea
from app.models.role import Role
from app.models.user import User
from app.models.waste_report import WasteReport
from app.schemas.waste_report import WasteReportCreate
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

    def test_waste_report_schema_allows_image_path(self):
        payload = WasteReportCreate(
            waste_type="plastic",
            description="Plastic bottle",
            location="Main Road",
            image_path="uploads/plastic-bottle.jpg",
        )

        self.assertEqual(payload.image_path, "uploads/plastic-bottle.jpg")


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


class AuthorizationTests(unittest.TestCase):
    def _user(self, role_name: str) -> User:
        return User(role=Role(name=role_name), role_id=int(RoleID.ADMIN))

    def test_named_role_allows_matching_user(self):
        checker = require_role(RoleName.ADMIN)

        self.assertIsNotNone(checker(current_user=self._user("admin")))

    def test_legacy_role_id_uses_persisted_role_name(self):
        checker = require_role(RoleID.COLLECTOR)

        self.assertIsNotNone(checker(current_user=self._user("collector")))

    def test_named_role_rejects_wrong_user(self):
        checker = require_role(RoleName.ADMIN)

        with self.assertRaises(HTTPException):
            checker(current_user=self._user("citizen"))

    def test_multiple_named_roles_are_supported(self):
        checker = require_roles(RoleName.ADMIN, RoleName.COLLECTOR)

        self.assertIsNotNone(checker(current_user=self._user("collector")))


class RoutingAdapterTests(unittest.TestCase):
    def test_osrm_adapter_converts_route_legs_to_domain_units(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def __getattr__(self, name):
                if name == "read":
                    return lambda: b'{"code":"Ok","routes":[{"legs":[{"distance":2500,"duration":600}]}]}'
                raise AttributeError(name)

        with patch("app.integrations.routing.osrm_adapter.urlopen", return_value=Response()):
            legs = OSRMAdapter("http://osrm").route([(20.0, 77.0), (20.1, 77.1)])

        self.assertEqual(legs[0].distance_km, 2.5)
        self.assertEqual(legs[0].duration_minutes, 10)

    def test_route_planner_applies_provider_legs_without_start_coordinate(self):
        class Adapter:
            def route(self, coordinates):
                return [RouteLeg(3.0, 12.0)]

        first = WasteCollection(report=WasteReport(latitude=20.01, longitude=77.0))
        second = WasteCollection(report=WasteReport(latitude=20.1, longitude=77.0))
        plan = optimize_collections([first, second], routing_adapter=Adapter())

        self.assertEqual(plan.stops[0].distance_from_previous_km, 0)
        self.assertEqual(plan.stops[1].distance_from_previous_km, 3.0)
        self.assertEqual(plan.total_distance_km, 3.0)

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
