# test 1: happy path — все шаги approved
async def test_run_returns_results_when_all_approved():
  # mock: planner → 1 step, executor → result, critic → approved
  # expect: 1 StepResult, retry_count=0

# test 2: reject once then approve — 1 retry
async def test_run_retries_on_reject_then_approves():
  # mock: первый critic → rejected, второй → approved
  # expect: 1 StepResult, planner вызван 2 раза

# test 3: max_retries exhausted
async def test_run_returns_after_max_retries_exceeded():
  # mock: critic всегда rejected
  # max_retries=2
  # expect: возвращает результаты после 2 retry, не зависает