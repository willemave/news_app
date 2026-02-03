from app.services.onboarding import _AudioLane, _AudioPlanOutput, _normalize_audio_lane_plan


def test_audio_lane_plan_preserves_reddit_lane_when_full() -> None:
    plan = _AudioPlanOutput(
        topic_summary="AI news",
        inferred_topics=["AI"],
        lanes=[
            _AudioLane(
                name=f"Lane {idx}",
                goal="Goal",
                target="feeds" if idx % 2 == 0 else "podcasts",
                queries=["query one", "query two"],
            )
            for idx in range(5)
        ],
    )

    normalized = _normalize_audio_lane_plan(plan, "AI news transcript")

    assert len(normalized.lanes) == 5
    assert any(lane.target == "reddit" for lane in normalized.lanes)
