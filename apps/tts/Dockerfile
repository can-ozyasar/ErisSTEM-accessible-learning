FROM python:3.12-slim

# Piper is an offline ONNX runtime.  The voice is deliberately downloaded at
# image build time so the running service has no internet dependency.
RUN pip install --no-cache-dir "piper-tts[http]==1.8.0" \
 && python -m piper.download_voices --data-dir /models tr_TR-dfki-medium

EXPOSE 5000
CMD ["python", "-m", "piper.http_server", "-m", "tr_TR-dfki-medium", "--data-dir", "/models", "--host", "0.0.0.0", "--port", "5000"]
