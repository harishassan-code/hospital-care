# QA tests

Automated smoke cases: `frontend/src/qa/features.qa.test.tsx`

```bash
cd frontend && npm test -- src/qa
```

Full report: [authentication-test-report.md](authentication-test-report.md)

The full report and its `results/` logs are a snapshot from the sprint review. They still name the
per-case files `login.qa.test.tsx` and `staff-workspace.qa.test.tsx` and their TC-xx / LOGIN-Nxx / LAND-Nxx
ids. Those files were replaced by `features.qa.test.tsx` in #87, which checks the same behaviour without
the ids. Its nav checks look for specific links rather than the exact list, so adding a staff module
doesn't break it.
