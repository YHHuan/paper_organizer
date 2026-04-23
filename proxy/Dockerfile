FROM ghcr.io/berriai/litellm:main-latest

COPY litellm_config.yaml /app/config.yaml

ENV PORT=8000

# Shell form (not JSON array) so $PORT is expanded at runtime
CMD litellm --config /app/config.yaml --port ${PORT}
