# Build online once; the resulting image runs without network access.
FROM python:3.12.3-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOME=/home/trust1
WORKDIR /app

# Environment layers stay cached when only analyzer source changes.
COPY docker/requirements.lock /opt/trust1/requirements.lock
RUN python -m pip install --no-cache-dir -r /opt/trust1/requirements.lock \
    && python -m pip check
COPY artifacts/docker/solc-0.8.20 /usr/local/bin/solc
RUN echo '0479d44fdf9c501c25337fdc540419f1593b884a87b47f023da4f1c700fda782  /usr/local/bin/solc' | sha256sum -c - \
    && chmod 755 /usr/local/bin/solc \
    && /usr/local/bin/solc --version \
    && python -c "import sys; from slither.slither import Slither; assert sys.version_info[:3] == (3, 12, 3)"

COPY src/ /app/src/
COPY scripts/analyze.py /app/scripts/analyze.py
RUN mkdir -p /home/trust1 \
    && chown 10001:10001 /home/trust1
USER 10001:10001
ENTRYPOINT ["python", "/app/scripts/analyze.py", "--solc", "/usr/local/bin/solc"]
CMD ["/input"]
