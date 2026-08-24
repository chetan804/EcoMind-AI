from typing import Dict


class WasteClassifier:
    """
    Service responsible for waste classification.

    This implementation currently uses deterministic keyword
    classification. It is structured as a service so that a
    trained ML model can replace the classification logic later.
    """

    WASTE_CATEGORIES = {
        "plastic",
        "paper",
        "glass",
        "metal",
        "organic",
        "e-waste",
        "other",
    }

    KEYWORDS: Dict[str, list[str]] = {
        "plastic": [
            "plastic",
            "polythene",
            "polybag",
            "wrapper",
            "plastic bottle",
            "plastic bag",
        ],
        "paper": [
            "paper",
            "newspaper",
            "cardboard",
            "carton",
            "book",
            "magazine",
        ],
        "glass": [
            "glass",
            "glass bottle",
            "broken glass",
        ],
        "metal": [
            "metal",
            "iron",
            "steel",
            "aluminium",
            "aluminum",
            "copper",
            "tin",
        ],
        "organic": [
            "food",
            "vegetable",
            "fruit",
            "organic",
            "kitchen waste",
            "food waste",
            "leaves",
            "garden waste",
        ],
        "e-waste": [
            "electronic",
            "electronics",
            "computer",
            "laptop",
            "mobile",
            "phone",
            "charger",
            "battery",
            "television",
            "tv",
        ],
    }

    def classify(self, description: str) -> str:
        """
        Classify waste from a textual description.

        Returns:
            One of the supported waste categories.
        """

        if not description or not description.strip():
            return "other"

        text = description.lower().strip()

        matched_category = self._find_category(text)

        return matched_category or "other"

    def _find_category(self, text: str) -> str | None:
        """
        Find the first matching waste category.
        """

        for category, keywords in self.KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    return category

        return None