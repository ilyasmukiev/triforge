# Triforge benchmark

A two-scenario sanity comparison used as the release gate for `v0.1.0-alpha`.

```bash
python benchmark/compare.py | tee "benchmark/results/$(date +%Y-%m-%d)-mvp-comparison.json"
```

Run the small Flask app yourself:

```bash
cd benchmark/sandbox-todo-app
pip install -r requirements.txt
python app.py
```

A full LLM-driven 4-task × 2-scenario benchmark with rubric scoring lives in Plan 3 (post-MVP).
