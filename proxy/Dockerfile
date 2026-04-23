FROM ghcr.io/berriai/litellm:main-latest

COPY litellm_config.yaml /app/config.yaml

ENV PORT=8000

# Clear base image ENTRYPOINT, then use sh -c so ${PORT} expands
ENTRYPOINT []
CMD ["sh", "-c", "litellm --config /app/config.yaml --port ${PORT:-8000}"]
