from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawSourceRun(Base):
    __tablename__ = "raw_source_runs"
    __table_args__ = (
        Index("ix_raw_source_runs_source_name_captured_at_status", "source_name", "captured_at", "status"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(100))
    endpoint: Mapped[str] = mapped_column(String(255))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30))


class RawPayload(Base):
    __tablename__ = "raw_payloads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_run_id: Mapped[int] = mapped_column(ForeignKey("raw_source_runs.id"))
    payload_json: Mapped[str] = mapped_column(Text)


class Coach(Base):
    __tablename__ = "coaches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120), unique=True)


class NationalTeam(Base):
    __tablename__ = "national_teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fifa_code: Mapped[str] = mapped_column(String(3), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    confederation: Mapped[str] = mapped_column(String(10))
    coach_id: Mapped[int | None] = mapped_column(ForeignKey("coaches.id"), nullable=True)
    tactical_labels: Mapped[list[str]] = mapped_column(JSON, default=list)
    common_formations: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    position: Mapped[str] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    club_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role_tags: Mapped[list[str]] = mapped_column(JSON, default=list)


class TeamSquad(Base):
    __tablename__ = "team_squads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    announced_at: Mapped[datetime] = mapped_column(DateTime)
    squad_name: Mapped[str] = mapped_column(String(120))


class PlayerAvailability(Base):
    __tablename__ = "player_availability"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30))
    details: Mapped[str] = mapped_column(Text, default="")
    expected_to_start: Mapped[bool] = mapped_column(Boolean, default=True)
    minutes_risk: Mapped[float] = mapped_column(Float, default=0.0)


class TeamRanking(Base):
    __tablename__ = "team_rankings"
    __table_args__ = (
        UniqueConstraint("national_team_id", "ranking_date", name="uq_team_rankings_team_date"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    ranking_date: Mapped[datetime] = mapped_column(DateTime)
    fifa_rank: Mapped[int] = mapped_column(Integer)
    ranking_points: Mapped[float] = mapped_column(Float)


class Venue(Base):
    __tablename__ = "venues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str] = mapped_column(String(80))
    country: Mapped[str] = mapped_column(String(80))
    altitude_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    pitch_surface: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pitch_length_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    pitch_width_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    climate_tag: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (
        Index("ix_matches_status_kickoff_at", "status", "kickoff_at"),
        Index("ix_matches_home_team_id_kickoff_at", "home_team_id", "kickoff_at"),
        Index("ix_matches_away_team_id_kickoff_at", "away_team_id", "kickoff_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(80), unique=True)
    competition: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(60))
    kickoff_at: Mapped[datetime] = mapped_column(DateTime)
    home_team_id: Mapped[int | None] = mapped_column(ForeignKey("national_teams.id"), nullable=True)
    away_team_id: Mapped[int | None] = mapped_column(ForeignKey("national_teams.id"), nullable=True)
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"), nullable=True)
    home_slot_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    away_slot_label: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_neutral_site: Mapped[bool] = mapped_column(Boolean, default=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    half_time_score: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30))


class MatchTeamStat(Base):
    __tablename__ = "match_team_stats"
    __table_args__ = (
        UniqueConstraint("match_id", "national_team_id", name="uq_match_team_stats_match_team"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    possession: Mapped[float | None] = mapped_column(Float, nullable=True)
    shots: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shots_on_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    corners: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fouls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yellow_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    red_cards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expected_goals: Mapped[float | None] = mapped_column(Float, nullable=True)


class MatchKeyEvent(Base):
    __tablename__ = "match_key_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    national_team_id: Mapped[int | None] = mapped_column(ForeignKey("national_teams.id"), nullable=True)
    minute: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(40))
    details: Mapped[str] = mapped_column(Text)


class OddsMarket(Base):
    __tablename__ = "odds_markets"
    __table_args__ = (
        Index("ix_odds_markets_match_id_market_type_bookmaker_name", "match_id", "market_type", "bookmaker_name"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    source_name: Mapped[str] = mapped_column(String(80))
    bookmaker_name: Mapped[str] = mapped_column(String(80))
    market_type: Mapped[str] = mapped_column(String(30))


class OddsQuote(Base):
    __tablename__ = "odds_quotes"
    __table_args__ = (
        Index("ix_odds_quotes_odds_market_id_captured_at", "odds_market_id", "captured_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    odds_market_id: Mapped[int] = mapped_column(ForeignKey("odds_markets.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    line_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    draw_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    over_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    under_price: Mapped[float | None] = mapped_column(Float, nullable=True)


class MatchWeatherSnapshot(Base):
    __tablename__ = "match_weather_snapshots"
    __table_args__ = (
        UniqueConstraint("match_id", "captured_at", "source_name", name="uq_match_weather_match_captured_source"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    source_name: Mapped[str] = mapped_column(String(80))
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_speed_kph: Mapped[float | None] = mapped_column(Float, nullable=True)
    precipitation_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    apparent_temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class MatchRefereeSnapshot(Base):
    __tablename__ = "match_referee_snapshots"
    __table_args__ = (
        UniqueConstraint("match_id", "captured_at", "source_name", name="uq_match_referee_match_captured_source"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    source_name: Mapped[str] = mapped_column(String(80))
    referee_name: Mapped[str] = mapped_column(String(120))
    nationality: Mapped[str | None] = mapped_column(String(80), nullable=True)
    average_yellow_cards: Mapped[float | None] = mapped_column(Float, nullable=True)
    penalty_tendency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    foul_strictness_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    var_intervention_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    pace_disruption_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class MatchContextSnapshot(Base):
    __tablename__ = "match_context_snapshots"
    __table_args__ = (
        UniqueConstraint("match_id", "captured_at", "source_name", name="uq_match_context_match_captured_source"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    source_name: Mapped[str] = mapped_column(String(80))
    advanced_metrics: Mapped[dict] = mapped_column(JSON, default=dict)
    schedule_fatigue: Mapped[dict] = mapped_column(JSON, default=dict)
    motivation: Mapped[dict] = mapped_column(JSON, default=dict)
    scenario_projection: Mapped[dict] = mapped_column(JSON, default=dict)


class TeamPowerSnapshot(Base):
    __tablename__ = "team_power_snapshots"
    __table_args__ = (
        UniqueConstraint("national_team_id", "captured_at", name="uq_team_power_snapshots_team_captured"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    overall_score: Mapped[float] = mapped_column(Float)
    attack_score: Mapped[float] = mapped_column(Float)
    defense_score: Mapped[float] = mapped_column(Float)
    midfield_control_score: Mapped[float] = mapped_column(Float)
    set_piece_score: Mapped[float] = mapped_column(Float)
    squad_completeness_score: Mapped[float] = mapped_column(Float)
    recent_form_score: Mapped[float] = mapped_column(Float)


class TeamTacticalProfile(Base):
    __tablename__ = "team_tactical_profiles"
    __table_args__ = (
        UniqueConstraint("national_team_id", "captured_at", name="uq_team_tactical_profiles_team_captured"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    main_formation: Mapped[str] = mapped_column(String(20))
    pressing_intensity: Mapped[str] = mapped_column(String(20))
    possession_tendency: Mapped[str] = mapped_column(String(20))
    transition_reliance: Mapped[str] = mapped_column(String(20))
    progression_focus: Mapped[str] = mapped_column(String(20))
    tactical_stability_score: Mapped[float] = mapped_column(Float)


class TeamFormSnapshot(Base):
    __tablename__ = "team_form_snapshots"
    __table_args__ = (
        UniqueConstraint("national_team_id", "captured_at", name="uq_team_form_snapshots_team_captured"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    recent_record: Mapped[str] = mapped_column(String(30))
    adjusted_form_score: Mapped[float] = mapped_column(Float)
    scoring_trend: Mapped[float] = mapped_column(Float)
    conceding_trend: Mapped[float] = mapped_column(Float)


class TeamEnvironmentProfile(Base):
    __tablename__ = "team_environment_profiles"
    __table_args__ = (
        UniqueConstraint("national_team_id", "captured_at", name="uq_team_environment_profiles_team_captured"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    heat_adaptation_score: Mapped[float] = mapped_column(Float)
    altitude_adaptation_score: Mapped[float] = mapped_column(Float)
    humidity_adaptation_score: Mapped[float] = mapped_column(Float)
    travel_recovery_score: Mapped[float] = mapped_column(Float)
    fast_start_score: Mapped[float] = mapped_column(Float)
    training_intensity_preference: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text, default="")


class PlayerImpactRating(Base):
    __tablename__ = "player_impact_ratings"
    __table_args__ = (
        UniqueConstraint("player_id", "captured_at", name="uq_player_impact_ratings_player_captured"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    impact_score: Mapped[float] = mapped_column(Float)
    impact_reason: Mapped[str] = mapped_column(Text)


class PredictionRun(Base):
    __tablename__ = "prediction_runs"
    __table_args__ = (
        Index("ix_prediction_runs_match_id_captured_at", "match_id", "captured_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    model_version: Mapped[str] = mapped_column(String(40))


class MarketCalibrationProfile(Base):
    __tablename__ = "market_calibration_profiles"
    __table_args__ = (
        UniqueConstraint(
            "market_family",
            "bucket_key",
            "profile_version",
            name="uq_market_calibration_profiles_family_bucket_version",
        ),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    market_family: Mapped[str] = mapped_column(String(40))
    bucket_key: Mapped[str] = mapped_column(String(120))
    profile_version: Mapped[str] = mapped_column(String(40))
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    fallback_bucket_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profile_json: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class MatchFeatureSnapshot(Base):
    __tablename__ = "match_feature_snapshots"
    __table_args__ = (
        UniqueConstraint("prediction_run_id", name="uq_match_feature_snapshots_prediction_run"),
        Index("ix_match_feature_snapshots_prediction_run_id", "prediction_run_id"),
        Index("ix_match_feature_snapshots_match_id_captured_at", "match_id", "captured_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_run_id: Mapped[int] = mapped_column(ForeignKey("prediction_runs.id"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    model_version: Mapped[str] = mapped_column(String(40))
    home_overall_score: Mapped[float] = mapped_column(Float)
    away_overall_score: Mapped[float] = mapped_column(Float)
    home_attack_score: Mapped[float] = mapped_column(Float)
    away_attack_score: Mapped[float] = mapped_column(Float)
    home_defense_score: Mapped[float] = mapped_column(Float)
    away_defense_score: Mapped[float] = mapped_column(Float)
    home_recent_form_score: Mapped[float] = mapped_column(Float)
    away_recent_form_score: Mapped[float] = mapped_column(Float)
    power_delta: Mapped[float] = mapped_column(Float)
    attack_delta: Mapped[float] = mapped_column(Float)
    defense_delta: Mapped[float] = mapped_column(Float)
    form_delta: Mapped[float] = mapped_column(Float)
    home_learning_readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    away_learning_readiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    home_learning_momentum_score: Mapped[float] = mapped_column(Float, default=0.0)
    away_learning_momentum_score: Mapped[float] = mapped_column(Float, default=0.0)
    home_tactical_continuity_score: Mapped[float] = mapped_column(Float, default=0.0)
    away_tactical_continuity_score: Mapped[float] = mapped_column(Float, default=0.0)
    learning_delta: Mapped[float] = mapped_column(Float, default=0.0)
    tactical_continuity_delta: Mapped[float] = mapped_column(Float, default=0.0)
    home_availability_alert_count: Mapped[int] = mapped_column(Integer, default=0)
    away_availability_alert_count: Mapped[int] = mapped_column(Integer, default=0)
    home_minutes_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    away_minutes_risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    discipline_delta: Mapped[float] = mapped_column(Float, default=0.0)
    environment_delta: Mapped[float] = mapped_column(Float, default=0.0)
    weather_delta: Mapped[float] = mapped_column(Float, default=0.0)
    referee_delta: Mapped[float] = mapped_column(Float, default=0.0)
    motivation_delta: Mapped[float] = mapped_column(Float, default=0.0)
    fatigue_delta: Mapped[float] = mapped_column(Float, default=0.0)
    scenario_pressure_delta: Mapped[float] = mapped_column(Float, default=0.0)
    goal_difference_pressure_delta: Mapped[float] = mapped_column(Float, default=0.0)
    market_handicap_line: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_total_line: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_home_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_draw_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_away_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_over_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_under_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    lambda_home: Mapped[float] = mapped_column(Float)
    lambda_away: Mapped[float] = mapped_column(Float)
    projected_tempo_score: Mapped[float] = mapped_column(Float, default=0.0)
    learning_adjustment: Mapped[float] = mapped_column(Float, default=0.0)
    feature_payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class MatchPrediction(Base):
    __tablename__ = "match_predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_run_id: Mapped[int] = mapped_column(ForeignKey("prediction_runs.id"))
    home_win_probability: Mapped[float] = mapped_column(Float)
    draw_probability: Mapped[float] = mapped_column(Float)
    away_win_probability: Mapped[float] = mapped_column(Float)
    calibrated_home_win_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrated_draw_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrated_away_win_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    expected_home_goals: Mapped[float] = mapped_column(Float, default=0.0)
    expected_away_goals: Mapped[float] = mapped_column(Float, default=0.0)
    over_2_5_probability: Mapped[float] = mapped_column(Float, default=0.0)
    under_2_5_probability: Mapped[float] = mapped_column(Float, default=0.0)
    handicap_cover_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    handicap_push_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    handicap_fail_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    totals_over_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    totals_push_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    totals_under_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    fair_handicap_line: Mapped[float] = mapped_column(Float)
    fair_total_line: Mapped[float] = mapped_column(Float, default=2.5)
    market_handicap_line: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_handicap_side: Mapped[str] = mapped_column(String(40))
    recommended_totals_side: Mapped[str | None] = mapped_column(String(40), nullable=True)
    totals_tendency: Mapped[str] = mapped_column(String(40))
    likely_scorelines: Mapped[str] = mapped_column(Text)
    confidence_level: Mapped[str] = mapped_column(String(20))
    summary_conclusion: Mapped[str] = mapped_column(Text)
    calibration_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)


class PredictionFactor(Base):
    __tablename__ = "prediction_factors"
    __table_args__ = (
        Index("ix_prediction_factors_prediction_run_id_factor_name", "prediction_run_id", "factor_name"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_run_id: Mapped[int] = mapped_column(ForeignKey("prediction_runs.id"))
    factor_name: Mapped[str] = mapped_column(String(60))
    factor_value: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)


class MatchReview(Base):
    __tablename__ = "match_reviews"
    __table_args__ = (
        Index("ix_match_reviews_match_id_team_id_created_at", "match_id", "national_team_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    summary_text: Mapped[str] = mapped_column(Text)
    tactical_change_summary: Mapped[str] = mapped_column(Text)
    strength_change_summary: Mapped[str] = mapped_column(Text)
    next_match_impact_summary: Mapped[str] = mapped_column(Text)


class TeamLearningSnapshot(Base):
    __tablename__ = "team_learning_snapshots"
    __table_args__ = (
        UniqueConstraint("national_team_id", "match_id", name="uq_team_learning_snapshots_team_match"),
        Index("ix_team_learning_snapshots_team_id_captured_at", "national_team_id", "captured_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    readiness_score: Mapped[float] = mapped_column(Float)
    momentum_score: Mapped[float] = mapped_column(Float)
    availability_alert_count: Mapped[int] = mapped_column(Integer)
    tactical_continuity_score: Mapped[float] = mapped_column(Float)
    learning_summary: Mapped[str] = mapped_column(Text)
    next_match_focus: Mapped[str] = mapped_column(Text)


class PostMatchRefreshRun(Base):
    __tablename__ = "post_match_refresh_runs"
    __table_args__ = (
        UniqueConstraint("match_id", name="uq_post_match_refresh_runs_match"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    processed_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(30))
    notes: Mapped[str] = mapped_column(Text, default="")


class TeamChangeLog(Base):
    __tablename__ = "team_change_logs"
    __table_args__ = (
        Index("ix_team_change_logs_team_id_created_at", "national_team_id", "created_at"),
        Index("ix_team_change_logs_match_id_created_at", "match_id", "created_at"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    change_type: Mapped[str] = mapped_column(String(50))
    details: Mapped[str] = mapped_column(Text)


class SentReport(Base):
    __tablename__ = "sent_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    sent_at: Mapped[datetime] = mapped_column(DateTime)
    recipient: Mapped[str] = mapped_column(String(120))
    subject: Mapped[str] = mapped_column(String(255))
    body_text: Mapped[str] = mapped_column(Text)


@event.listens_for(Base.metadata, "after_create")
def _upgrade_existing_sqlite_matches_table(target, connection, **kwargs) -> None:
    if connection.dialect.name != "sqlite":
        return

    inspector = inspect(connection)
    if "matches" not in inspector.get_table_names():
        return

    columns = {column["name"]: column for column in inspector.get_columns("matches")}
    needs_slot_columns = "home_slot_label" not in columns or "away_slot_label" not in columns
    needs_nullable_team_ids = not columns["home_team_id"]["nullable"] or not columns["away_team_id"]["nullable"]

    if not needs_slot_columns and not needs_nullable_team_ids:
        return

    if not needs_nullable_team_ids:
        if "home_slot_label" not in columns:
            connection.execute(text("ALTER TABLE matches ADD COLUMN home_slot_label VARCHAR(40)"))
        if "away_slot_label" not in columns:
            connection.execute(text("ALTER TABLE matches ADD COLUMN away_slot_label VARCHAR(40)"))
        return

    connection.execute(text("PRAGMA foreign_keys=OFF"))
    try:
        connection.execute(
            text(
                """
                CREATE TABLE matches__schema_upgrade (
                    id INTEGER PRIMARY KEY,
                    external_id VARCHAR(80) UNIQUE NOT NULL,
                    competition VARCHAR(120) NOT NULL,
                    stage VARCHAR(60) NOT NULL,
                    kickoff_at DATETIME NOT NULL,
                    home_team_id INTEGER,
                    away_team_id INTEGER,
                    venue_id INTEGER,
                    home_slot_label VARCHAR(40),
                    away_slot_label VARCHAR(40),
                    is_neutral_site BOOLEAN NOT NULL,
                    home_score INTEGER,
                    away_score INTEGER,
                    half_time_score VARCHAR(20),
                    status VARCHAR(30) NOT NULL,
                    FOREIGN KEY(home_team_id) REFERENCES national_teams (id),
                    FOREIGN KEY(away_team_id) REFERENCES national_teams (id),
                    FOREIGN KEY(venue_id) REFERENCES venues (id)
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO matches__schema_upgrade (
                    id,
                    external_id,
                    competition,
                    stage,
                    kickoff_at,
                    home_team_id,
                    away_team_id,
                    is_neutral_site,
                    home_score,
                    away_score,
                    half_time_score,
                    status
                )
                SELECT
                    id,
                    external_id,
                    competition,
                    stage,
                    kickoff_at,
                    home_team_id,
                    away_team_id,
                    is_neutral_site,
                    home_score,
                    away_score,
                    half_time_score,
                    status
                FROM matches
                """
            )
        )
        connection.execute(text("DROP TABLE matches"))
        connection.execute(text("ALTER TABLE matches__schema_upgrade RENAME TO matches"))
    finally:
        connection.execute(text("PRAGMA foreign_keys=ON"))
