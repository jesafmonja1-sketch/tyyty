from dataclasses import dataclass

from world_cup_intel.analysis.predictions import PredictionDiagnostic
from world_cup_intel.schema import MatchPrediction


@dataclass(frozen=True)
class CliMatchAnalysisPayload:
    match_label: str
    prediction: MatchPrediction
    diagnostic: PredictionDiagnostic


def _pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def _line(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2f}"


def render_cli_match_analysis(payload: CliMatchAnalysisPayload) -> str:
    prediction = payload.prediction
    diagnostic = payload.diagnostic

    score_parts = [part.strip() for part in prediction.likely_scorelines.split(",") if part.strip()]
    primary_scores = ", ".join(score_parts[:3]) if score_parts else "N/A"
    defensive_score = score_parts[3] if len(score_parts) > 3 else "N/A"

    market_probability_lines = diagnostic.market_probability_summary or "N/A"
    value_edge_summary = diagnostic.value_edge_summary or "N/A"
    risk_lines = diagnostic.issue_hints[:4] if diagnostic.issue_hints else ["N/A"]

    totals_summary = prediction.calibration_summary_json.get("totals", {}) if prediction.calibration_summary_json else {}
    totals_market_line = totals_summary.get("market_line")
    if totals_market_line is None:
        totals_market_line = prediction.fair_total_line
        totals_line_source = "fair_total_line"
    else:
        totals_line_source = totals_summary.get("line_source") or "market_total_line"

    lines = [
        f"比赛结论 | {payload.match_label}",
        f"总结: {diagnostic.summary_conclusion}",
        f"是否建议下: {diagnostic.match_suitability_label}",
        f"原因: {diagnostic.match_suitability_reason}",
        "",
        "胜平负",
        f"原始概率: 主胜 {_pct(prediction.home_win_probability)} / 平 {_pct(prediction.draw_probability)} / 客胜 {_pct(prediction.away_win_probability)}",
        f"校准概率: 主胜 {_pct(prediction.calibrated_home_win_probability)} / 平 {_pct(prediction.calibrated_draw_probability)} / 客胜 {_pct(prediction.calibrated_away_win_probability)}",
        market_probability_lines,
        value_edge_summary,
        "",
        "让球",
        f"市场线: {_line(prediction.market_handicap_line)}",
        f"公平线: {_line(prediction.fair_handicap_line)}",
        f"cover / push / fail: {_pct(prediction.handicap_cover_probability)} / {_pct(prediction.handicap_push_probability)} / {_pct(prediction.handicap_fail_probability)}",
        f"推荐方向: {diagnostic.recommended_handicap_side}",
        f"是否建议碰: {diagnostic.handicap_suitability_label}",
        f"原因: {diagnostic.handicap_suitability_reason}",
        "",
        "大小球",
        f"当前线: {_line(totals_market_line)} ({totals_line_source})",
        f"fair total line: {_line(prediction.fair_total_line)}",
        f"over / push / under: {_pct(prediction.totals_over_probability)} / {_pct(prediction.totals_push_probability)} / {_pct(prediction.totals_under_probability)}",
        f"推荐方向: {diagnostic.recommended_totals_side or 'N/A'}",
        f"是否建议碰: {diagnostic.totals_suitability_label}",
        f"原因: {diagnostic.totals_suitability_reason}",
        "",
        "比分",
        f"主比分: {primary_scores}",
        f"防冷比分: {defensive_score}",
        "",
        "风险点",
    ]
    lines.extend(f"- {line}" for line in risk_lines)
    lines.extend(
        [
            "",
            "核心理由",
            f"- {diagnostic.summary_conclusion}",
            f"- 让球: {diagnostic.handicap_suitability_reason}",
            f"- 大小球: {diagnostic.totals_suitability_reason}",
        ]
    )
    return "\n".join(lines)
