from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List
import json


class ProductLoader:
    def __init__(self, base_path: Path):
        self.base_path = base_path

    def load(self, product_id: str) -> Dict[str, Any]:
        path = self.base_path / "products" / product_id / "product_config.json"
        if not path.exists():
            raise FileNotFoundError(f"product_config.json not found: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_products(self) -> List[Dict[str, Any]]:
        products_dir = self.base_path / "products"
        results = []
        if not products_dir.exists():
            return results
        for config in products_dir.glob("*/product_config.json"):
            try:
                results.append(json.loads(config.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
        return results
