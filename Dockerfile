# SignalMesh Terminal — ONE image: the web UI is built by node, served by the
# read-only Python adapter. Separate from the SignalMesh image entirely.
# BUILD IDENTITY, computed from the git checkout this image is built from — never typed.
# version = the VERSION file · commit = short hash · build = commit count · dirty = uncommitted
# changes in the checkout. Both the UI bundle and the adapter read this one file.
FROM alpine/git:2.54.0 AS meta
WORKDIR /src
COPY . .
RUN git config --global --add safe.directory /src \
 && if git rev-parse HEAD >/dev/null 2>&1; then \
      SHALLOW=$(git rev-parse --is-shallow-repository); \
      if [ "$SHALLOW" = "true" ]; then BUILD=null; else BUILD=$(git rev-list --count HEAD); fi; \
      if [ -n "$(git status --porcelain --untracked-files=no)" ]; then DIRTY=true; else DIRTY=false; fi; \
      printf '{"version":"%s","commit":"%s","build":%s,"shallow":%s,"dirty":%s,"commit_time":"%s","built_at":"%s"}\n' \
        "$(tr -d ' \n' < VERSION)" "$(git rev-parse --short=7 HEAD)" "$BUILD" "$SHALLOW" "$DIRTY" \
        "$(git log -1 --format=%cI)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /build.json; \
    else \
      printf '{"version":"%s","commit":null,"build":null,"shallow":false,"dirty":false,"commit_time":null,"built_at":"%s"}\n' \
        "$(tr -d ' \n' < VERSION)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > /build.json; \
    fi && cat /build.json

FROM node:22-alpine AS web
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
COPY VERSION /build/VERSION
COPY --from=meta /build.json /build/build.json
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/terminal
COPY adapter/requirements.txt ./adapter/requirements.txt
RUN pip install --no-cache-dir -r adapter/requirements.txt
COPY adapter/ ./adapter/
COPY --from=web /build/web/dist ./web/dist
COPY scripts/ ./scripts/
COPY VERSION ./VERSION
COPY docs/RELEASES.md ./docs/RELEASES.md
COPY --from=meta /build.json ./build.json
# /data = the terminal's OWN forecast journal (docker-compose mounts the named volume here). Not SignalMesh's.
RUN useradd -m terminal && mkdir -p /data && chown -R terminal /srv/terminal /data
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
