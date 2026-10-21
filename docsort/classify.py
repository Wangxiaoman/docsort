"""规则计分分类引擎：跨页累计得分，支持置信度提前终止。"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple


class Classifier:
    def __init__(self, cfg: dict):
        clf = cfg.get("classification", {})
        self.early_stop = bool(clf.get("early_stop", True))
        self.max_pages = int(clf.get("max_pages", 3))
        self.min_margin = float(clf.get("min_margin", 2))
        self.default_threshold = float(clf.get("default_threshold", 5))
        self.templates = cfg.get("templates", {})
        self._compiled: Dict[str, List[Tuple[re.Pattern, float]]] = {}
        for name, tpl in self.templates.items():
            if name == "unknown":
                continue
            rules = []
            for r in tpl.get("rules", []):
                try:
                    rx = re.compile(r["pattern"], re.IGNORECASE)
                except re.error as e:
                    print(f"[warn] 模板 {name} 规则正则无效，已跳过: {r.get('pattern')} ({e})")
                    continue
                rules.append((rx, float(r.get("weight", 1))))
            self._compiled[name] = rules

    def score_page(self, text: str) -> Tuple[Dict[str, float], List[dict]]:
        """对单页文本计分，返回 (各类别得分, 命中明细)。"""
        scores = {name: 0.0 for name in self._compiled}
        hits: List[dict] = []
        for name, rules in self._compiled.items():
            for rx, weight in rules:
                if rx.search(text):
                    scores[name] += weight
                    hits.append({"type": name, "pattern": rx.pattern, "weight": weight})
        return scores, hits

    def decide(self, total: Dict[str, float], pages_used: int) -> Tuple[str, float, bool]:
        """根据累计得分定类。

        返回 (类型, 置信度, 是否低置信度)。
        - 有类别达到自身 threshold 且领先第二名 min_margin 以上 → 确定分类
        - 否则 → unknown；若已扫满 max_pages 仍取了最高分，标记低置信度
        """
        if not total:
            return "unknown", 0.0, True
        ranked = sorted(total.items(), key=lambda kv: kv[1], reverse=True)
        best, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        threshold = float(self.templates.get(best, {}).get("threshold", self.default_threshold))
        if best_score >= threshold and (best_score - second_score) >= self.min_margin:
            confidence = round(best_score / (best_score + second_score + 1.0), 3)
            return best, confidence, False
        if best_score > 0:
            return "unknown", round(best_score / (threshold + best_score), 3), True
        return "unknown", 0.0, True

    def should_stop(self, total: Dict[str, float]) -> bool:
        """逐页判断是否满足提前终止条件（供流水线每页后调用）。"""
        if not self.early_stop or not total:
            return False
        ranked = sorted(total.items(), key=lambda kv: kv[1], reverse=True)
        best, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        threshold = float(self.templates.get(best, {}).get("threshold", self.default_threshold))
        return best_score >= threshold and (best_score - second_score) >= self.min_margin
