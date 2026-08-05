# Local agent test console

Start the dashboard from the repository root:

```powershell
$env:PYTHONPATH = 'src'
& .\.venv\Scripts\python.exe -m dispute_resolution.web
```

Open `http://127.0.0.1:8765` in a browser.

The dashboard runs the existing order/seller, payment, delivery, policy, and
verifier pipeline against the local CSV files. It is read-only and never
overwrites `output/` or `trace.jsonl`.
