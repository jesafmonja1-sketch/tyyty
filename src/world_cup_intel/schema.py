from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawSourceRun(Base):
    __tablename__ = "raw_source_runs"
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
    tactical_labels: Mapped[str] = mapped_column(Text, default="[]")
    common_formations: Mapped[str] = mapped_column(Text, default="[]")
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True)


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    position: Mapped[str] = mapped_column(String(20))
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    club_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role_tags: Mapped[str] = mapped_column(Text, default="[]")


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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    ranking_date: Mapped[datetime] = mapped_column(DateTime)
    fifa_rank: Mapped[int] = mapped_column(Integer)
    ranking_points: Mapped[float] = mapped_column(Float)


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(80), unique=True)
    competition: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(60))
    kickoff_at: Mapped[datetime] = mapped_column(DateTime)
    home_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    away_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    is_neutral_site: Mapped[bool] = mapped_column(Boolean, default=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    half_time_score: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30))


class MatchTeamStat(Base):
    __tablename__ = "match_team_stats"
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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    source_name: Mapped[str] = mapped_column(String(80))
    bookmaker_name: Mapped[str] = mapped_column(String(80))
    market_type: Mapped[str] = mapped_column(String(30))


class OddsQuote(Base):
    __tablename__ = "odds_quotes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    odds_market_id: Mapped[int] = mapped_column(ForeignKey("odds_markets.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    line_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    home_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    draw_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    away_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    over_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    under_price: Mapped[float | None] = mapped_column(Float, nullable=True)


class TeamPowerSnapshot(Base):
    __tablename__ = "team_power_snapshots"
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
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    recent_record: Mapped[str] = mapped_column(String(30))
    adjusted_form_score: Mapped[float] = mapped_column(Float)
    scoring_trend: Mapped[float] = mapped_column(Float)
    conceding_trend: Mapped[float] = mapped_column(Float)


class PlayerImpactRating(Base):
    __tablename__ = "player_impact_ratings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    impact_score: Mapped[float] = mapped_column(Float)
    impact_reason: Mapped[str] = mapped_column(Text)


class PredictionRun(Base):
    __tablename__ = "prediction_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime)
    model_version: Mapped[str] = mapped_column(String(40))


class MatchPrediction(Base):
    __tablename__ = "match_predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_run_id: Mapped[int] = mapped_column(ForeignKey("prediction_runs.id"))
    home_win_probability: Mapped[float] = mapped_column(Float)
    draw_probability: Mapped[float] = mapped_column(Float)
    away_win_probability: Mapped[float] = mapped_column(Float)
    fair_handicap_line: Mapped[float] = mapped_column(Float)
    market_handicap_line: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommended_handicap_side: Mapped[str] = mapped_column(String(40))
    totals_tendency: Mapped[str] = mapped_column(String(40))
    likely_scorelines: Mapped[str] = mapped_column(Text)
    confidence_level: Mapped[str] = mapped_column(String(20))
    summary_conclusion: Mapped[str] = mapped_column(Text)


class PredictionFactor(Base):
    __tablename__ = "prediction_factors"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prediction_run_id: Mapped[int] = mapped_column(ForeignKey("prediction_runs.id"))
    factor_name: Mapped[str] = mapped_column(String(60))
    factor_value: Mapped[float] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text)


class MatchReview(Base):
    __tablename__ = "match_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"))
    national_team_id: Mapped[int] = mapped_column(ForeignKey("national_teams.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime)
    summary_text: Mapped[str] = mapped_column(Text)
    tactical_change_summary: Mapped[str] = mapped_column(Text)
    strength_change_summary: Mapped[str] = mapped_column(Text)
    next_match_impact_summary: Mapped[str] = mapped_column(Text)


class TeamChangeLog(Base):
    __tablename__ = "team_change_logs"
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
