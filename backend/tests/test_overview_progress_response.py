from routers.overview import ProgressInfo, _progress_for
from store.research_store import ResearchTask


def test_progress_for_in_progress_task():
    task = ResearchTask(research_id="x", status="in_progress")
    task.progress_pct = 45
    task.progress_label = "Sorting through sources"
    p = _progress_for(task)
    assert isinstance(p, ProgressInfo)
    assert p.pct == 45
    assert p.label == "Sorting through sources"


def test_progress_for_pending_task():
    task = ResearchTask(research_id="x", status="pending")
    p = _progress_for(task)
    assert p is not None
    assert p.pct == 0
    assert p.label == "Getting started"


def test_progress_for_complete_task_is_none():
    task = ResearchTask(research_id="x", status="complete")
    assert _progress_for(task) is None


def test_progress_for_failed_task_is_none():
    task = ResearchTask(research_id="x", status="failed")
    assert _progress_for(task) is None
