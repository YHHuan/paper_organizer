FROM ghcr.io/berriai/litellm:main-latest

# Copy proxy config into the image
COPY litellm_config.yaml /app/config.yaml

# Railway injects $PORT at runtime; default to 8000 for local dev
ENV PORT=8000

# detailed_debug gives full request/response logs in Railway's log viewer
CMD ["--config", "/app/config.yaml", "--port", "8000", "--detailed_debug"]
