# SignalMesh Terminal — ONE image: the web UI is built by node, served by the
# read-only Python adapter. Separate from the SignalMesh image entirely.
FROM node:22-alpine AS web
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/terminal
COPY adapter/requirements.txt ./adapter/requirements.txt
RUN pip install --no-cache-dir -r adapter/requirements.txt
COPY adapter/ ./adapter/
COPY --from=web /build/web/dist ./web/dist
COPY scripts/ ./scripts/
RUN useradd -m terminal && chown -R terminal /srv/terminal
USER terminal
WORKDIR /srv/terminal/adapter
ENV SMT_WEB_DIST=/srv/terminal/web/dist
EXPOSE 8090
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://127.0.0.1:8090/api/terminal/health', timeout=4).raise_for_status()"
# ONE worker on purpose: the adapter's cache is per process, and two processes can hold two
# revisions of the same bar (SignalMesh re-upserts a bar the reporter resends), so a header
# answered by one worker and a list answered by the other could disagree about one minute.
CMD ["uvicorn", "signalmesh_terminal.main:app", "--host", "0.0.0.0", "--port", "8090", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
