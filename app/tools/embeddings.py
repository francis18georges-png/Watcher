import json, http.client, numpy as np


def embed_ollama(texts, model: str = 'nomic-embed-text'):
    try:
        conn = http.client.HTTPConnection('127.0.0.1', 11434, timeout=30)
        payload = json.dumps({'model': model, 'input': texts})
        conn.request('POST', '/api/embeddings', body=payload, headers={'Content-Type': 'application/json'})
        data = json.loads(conn.getresponse().read())
        return [np.array(v, dtype=np.float32) for v in data['embeddings']]
    except Exception as e:
        raise RuntimeError(f"Embedding request failed: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
