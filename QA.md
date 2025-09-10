# QA Notes

## Manual Verification

1. Launch the GUI with `python -m app.ui.main`.
2. Enter a prompt and press **Envoyer**.
3. The button disables while the response is generated.
4. The interface remains responsive and the button re-enables once the reply appears.

## Static Analysis

Run Bandit to scan the codebase while ignoring Git metadata:

```
bandit -q -r . -c bandit.yml
```
